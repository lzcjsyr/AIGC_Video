from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

import anyio
from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    UserMessage,
    query,
)

from core.config import config
from core.infra.ai.task_context import write_task_context
from core.resources import library_root
from core.infra.motion.skill_loader import (
    build_step4_motion_skill_path_context,
    default_step4_motion_skill_dir,
    step4_motion_skill_dirs,
)
from core.prompts import (
    STEP1_5_SEGMENT_PROMPT_TEMPLATE,
    STEP4_MOTION_AGENT_PROMPT_TEMPLATE,
    STEP4_MOTION_PROMPT_VERSION,
    build_step4_motion_style_context,
    build_step1_agent_prompt,
)

STEP1_AGENT_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill"]
STEP1_5_AGENT_TOOLS = ["Read", "Write"]
STEP1_AGENT_SKILL = config.STEP1_AGENT_SKILL
STEP4_MOTION_AGENT_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]

_STEP1_SUBAGENT_PROMPTS = {
    "title-quote-writer": "第一稿固定后生成标题、封面文案和金句候选，写入 _title_quote_candidates.json。",
    "fact-style-reviewer": "只返回事实、结构、风格和 JSON 契约问题清单；不要写文件。",
}

STEP1_EXTRACT_NAME = "_extract.md"
STEP1_COVERAGE_LEDGER_NAME = "_coverage_ledger.json"
STEP1_SESSION_LOG_NAME = "_agent_session.jsonl"

_MAX_LOG_FIELD_CHARS = 12_000
_OMITTED_BASH_READ_CONTENT = "[omitted: Bash text-window output from extracted source text]"
_OMITTED_SKILL_REFERENCE_CONTENT = "[omitted: skill/reference file content]"
_OMITTED_PERSISTED_FILE_CONTENT = "[omitted: file content already persisted]"
_OMITTED_PERSISTED_READ_CONTENT = "[omitted: persisted draft/raw file read]"
_OMITTED_LEDGER_WRITE_COMMAND = "[omitted: Bash write command for _coverage_ledger.json]"
_BASH_READ_WINDOW_RE = re.compile(r"\b(sed\s+-n|head|tail)\b")


def _step1_agent_add_dirs(input_file: str) -> list[str]:
    input_path = Path(input_file)
    if input_path.is_dir():
        return [str(input_path)]
    return [str(input_path.parent)]


def _load_step1_subagent_prompt(agent_config: dict[str, Any], name: str) -> str:
    prompt_file = agent_config.get("prompt_file")
    if prompt_file:
        path = Path(prompt_file)
        if not path.is_absolute():
            path = library_root() / path
        return path.read_text(encoding="utf-8").strip()
    return _STEP1_SUBAGENT_PROMPTS.get(name, _STEP1_SUBAGENT_PROMPTS["fact-style-reviewer"])


def _build_step1_subagents(skill_name: str | None = None) -> dict[str, AgentDefinition]:
    if skill_name == "book-commerce-video-script":
        return {}
    subagent_config = getattr(config, "STEP1_SUBAGENTS", None) or {}
    if not subagent_config.get("enabled"):
        return {}

    agents: dict[str, AgentDefinition] = {}
    for name, agent_config in (subagent_config.get("agents") or {}).items():
        if not agent_config.get("enabled", True):
            continue
        model = agent_config.get("model")
        agents[name] = AgentDefinition(
            description=agent_config.get("description") or name,
            prompt=_load_step1_subagent_prompt(agent_config, name),
            tools=agent_config.get("tools"),
            model=None if model in {None, "", "inherit"} else str(model),
            maxTurns=agent_config.get("max_turns"),
            background=agent_config.get("background"),
        )
    return agents


def _get_anthropic_compatible_config(server: str, context: str) -> tuple[str, str, str]:
    server = (server or "").strip().lower()
    if server == "mimo":
        return "https://api.xiaomimimo.com/anthropic", (config.MIMO_API_KEY or "").strip(), "MIMO_API_KEY"
    elif server == "kimi":
        return "https://api.moonshot.cn/anthropic", (config.KIMI_API_KEY or "").strip(), "KIMI_API_KEY 或 MOONSHOT_API_KEY"
    elif server == "deepseek":
        return "https://api.deepseek.com/anthropic", (config.DEEPSEEK_API_KEY or "").strip(), "DEEPSEEK_API_KEY"
    elif server == "siliconflow":
        return "https://api.siliconflow.cn/", (config.SILICONFLOW_KEY or "").strip(), "SILICONFLOW_KEY"
    elif server == "openrouter":
        return "https://openrouter.ai/api", (config.OPENROUTER_API_KEY or "").strip(), "OPENROUTER_API_KEY"
    elif server == "volcengine":
        return "https://ark.cn-beijing.volces.com/api/compatible", (config.VOLCENGINE_API_KEY or "").strip(), "VOLCENGINE_API_KEY"
    else:
        labels = {
            "step1": "步骤1",
            "step1_5": "步骤1.5",
            "step4": "步骤4 HTML Motion Agent",
        }
        label = labels.get(context, context)
        raise ValueError(f"不支持的{label} LLM服务商: {server}，支持的服务商: mimo, kimi, deepseek, siliconflow, openrouter, volcengine")


def _normalize_anthropic_agent_model(server: str, model: str | None) -> str:
    return (model or "").strip()


def _anthropic_agent_options_model(server: str, model: str | None) -> str | None:
    if (server or "").strip().lower() == "deepseek":
        return None
    return _normalize_anthropic_agent_model(server, model)


def _normalize_anthropic_agent_base_url(server: str, base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if (server or "").strip().lower() == "deepseek" and normalized in {
        "https://api.deepseek.com",
        "https://api.deepseek.com/v1",
    }:
        return "https://api.deepseek.com/anthropic"
    return normalized


def _build_anthropic_agent_env(*, server: str, model: str, context: str, config_name: str) -> dict[str, str]:
    server = (server or "").strip().lower()
    if not server:
        raise RuntimeError(f"{config_name} 不能为空（mimo/kimi/siliconflow/openrouter/volcengine/deepseek）")

    base_url, api_key, key_name = _get_anthropic_compatible_config(server, context)
    base_url = _normalize_anthropic_agent_base_url(server, base_url)

    if not api_key:
        raise RuntimeError(f"{config_name}={server} 需要 {key_name}（.env），用于驱动 Claude Agent SDK")

    env = {
        "ANTHROPIC_BASE_URL": base_url,
        # OpenRouter's Claude Code integration requires the API key to be
        # supplied only as the auth token. A non-empty ANTHROPIC_API_KEY can
        # conflict with ANTHROPIC_AUTH_TOKEN and produce misleading 401s.
        "ANTHROPIC_API_KEY": "" if server == "openrouter" else api_key,
        "ANTHROPIC_AUTH_TOKEN": api_key,
        "ANTHROPIC_MODEL": _normalize_anthropic_agent_model(server, model),
    }
    if server == "deepseek":
        env.update(
            {
                "ANTHROPIC_DEFAULT_OPUS_MODEL": _normalize_anthropic_agent_model(server, model),
                "ANTHROPIC_DEFAULT_SONNET_MODEL": _normalize_anthropic_agent_model(server, model),
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-flash",
                "CLAUDE_CODE_SUBAGENT_MODEL": "deepseek-flash",
                "CLAUDE_CODE_EFFORT_LEVEL": "max",
            }
        )
    elif server == "openrouter":
        # Claude Code otherwise reserves up to 32k output tokens per turn.
        # Long tool-driven workflows can be rejected by OpenRouter budget
        # limits even though individual tool calls need far less output.
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "4096"
        # Trigger compaction before long reading workflows accumulate a
        # six-figure prompt that OpenRouter may reject on key budget limits.
        env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] = "40"
    return env


def build_step1_agent_env() -> dict[str, str]:
    return _build_anthropic_agent_env(
        server=config.LLM_SERVER_STEP1,
        model=config.LLM_MODEL_STEP1,
        context="step1",
        config_name="LLM_SERVER_STEP1",
    )


def build_step1_5_agent_env(
    llm_server: str | None = None,
    llm_model: str | None = None,
) -> dict[str, str]:
    return _build_anthropic_agent_env(
        server=llm_server or config.LLM_SERVER_STEP1_5,
        model=llm_model or config.LLM_MODEL_STEP1_5,
        context="step1_5",
        config_name="LLM_SERVER_STEP1_5",
    )


def build_step4_motion_agent_env(
    llm_server: str | None = None,
    llm_model: str | None = None,
    llm_base_url: str | None = None,
) -> dict[str, str]:
    server = (llm_server or getattr(config, "LLM_SERVER_STEP4", "") or "").strip().lower()
    if not server:
        raise RuntimeError("步骤4 HTML Motion Agent 需要配置 LLM_SERVER_STEP4")

    base_url, api_key, key_name = _get_anthropic_compatible_config(server, "step4")

    base_url = (
        (llm_base_url or "").strip()
        or (getattr(config, "LLM_BASE_URL_STEP4_OVERRIDE", "") or "").strip()
        or base_url
    )
    base_url = _normalize_anthropic_agent_base_url(server, base_url)

    if not api_key:
        raise RuntimeError(f"步骤4 HTML Motion Agent 需要 {key_name}（.env）")

    env = {
        "ANTHROPIC_BASE_URL": base_url,
        "ANTHROPIC_API_KEY": api_key,
        "ANTHROPIC_AUTH_TOKEN": api_key,
        "ANTHROPIC_MODEL": _normalize_anthropic_agent_model(server, llm_model or config.LLM_MODEL_STEP4),
    }
    if server == "deepseek":
        env.update(
            {
                "ANTHROPIC_DEFAULT_OPUS_MODEL": _normalize_anthropic_agent_model(
                    server, llm_model or config.LLM_MODEL_STEP4
                ),
                "ANTHROPIC_DEFAULT_SONNET_MODEL": _normalize_anthropic_agent_model(
                    server, llm_model or config.LLM_MODEL_STEP4
                ),
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-flash",
                "CLAUDE_CODE_SUBAGENT_MODEL": "deepseek-flash",
                "CLAUDE_CODE_EFFORT_LEVEL": "max",
            }
        )
    return env


def _truncate_for_log(value: Any, *, max_chars: int = _MAX_LOG_FIELD_CHARS) -> Any:
    if isinstance(value, str) and len(value) > max_chars:
        return {
            "_truncated": True,
            "length": len(value),
            "preview": value[:max_chars],
        }
    if isinstance(value, dict):
        return {key: _truncate_for_log(item, max_chars=max_chars) for key, item in value.items()}
    if isinstance(value, list):
        return [_truncate_for_log(item, max_chars=max_chars) for item in value]
    return value


def _serialize_sdk_message(message: object) -> dict[str, Any]:
    if isinstance(message, UserMessage):
        payload = asdict(message)
        payload["kind"] = "UserMessage"
        return _truncate_for_log(payload)
    if isinstance(message, AssistantMessage):
        payload = asdict(message)
        payload["kind"] = "AssistantMessage"
        return _truncate_for_log(payload)
    if isinstance(message, SystemMessage):
        payload = asdict(message)
        payload["kind"] = "SystemMessage"
        return _truncate_for_log(payload)
    if isinstance(message, ResultMessage):
        payload = asdict(message)
        payload["kind"] = "ResultMessage"
        return payload
    if isinstance(message, StreamEvent):
        payload = asdict(message)
        payload["kind"] = "StreamEvent"
        return _truncate_for_log(payload)
    if is_dataclass(message):
        payload = asdict(message)
        payload["kind"] = type(message).__name__
        return _truncate_for_log(payload)
    return {"kind": type(message).__name__, "repr": repr(message)}


class AgentSessionLog:
    """Append-only JSONL trace for a single Claude Agent invocation."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = 0
        self._omitted_bash_read_tool_ids: set[str] = set()
        self._omitted_persisted_read_tool_ids: set[str] = set()

    @staticmethod
    def _is_extract_window_read_command(command: str) -> bool:
        return bool(re.search(r"(?:^|[/\\])_extract\.(?:txt|md)\b", command)) and bool(
            _BASH_READ_WINDOW_RE.search(command)
        )

    @staticmethod
    def _value_length(value: Any) -> int | None:
        if isinstance(value, str):
            return len(value)
        if isinstance(value, dict) and value.get("_truncated") is True and isinstance(value.get("length"), int):
            return value["length"]
        return None

    @staticmethod
    def _is_skill_reference_path(path: str) -> bool:
        return "/skills/" in path and (
            path.endswith("/SKILL.md") or "/references/" in path
        )

    @staticmethod
    def _is_large_persisted_file_write(item: dict[str, Any]) -> bool:
        if item.get("name") != "Write":
            return False
        input_payload = item.get("input")
        if not isinstance(input_payload, dict):
            return False
        content = input_payload.get("content")
        return isinstance(content, str) and len(content) > 1000

    @staticmethod
    def _is_coverage_ledger_write_command(command: str) -> bool:
        return "_coverage_ledger.json" in command and "cat >" in command

    @staticmethod
    def _is_persisted_read_path(path: str) -> bool:
        return Path(path).name in {
            "_draft_v1.txt",
            "_draft_v2_structure.txt",
            "_draft_final.txt",
            "_data_check_ledger.json",
            "_revision_audit.json",
            "raw.json",
        }

    def _compact_message_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = payload.get("message")
        if not isinstance(message, dict):
            return payload

        content = message.get("content")
        if not isinstance(content, list):
            return payload

        changed = False
        omitted_tool_result_ids: set[str] = set()
        omit_skill_reference_result = False
        tool_use_result = message.get("tool_use_result")
        if isinstance(tool_use_result, dict):
            file_result = tool_use_result.get("file")
            if isinstance(file_result, dict):
                file_path = file_result.get("filePath")
                omit_skill_reference_result = isinstance(file_path, str) and self._is_skill_reference_path(file_path)

        compacted_content: list[Any] = []
        for item in content:
            if not isinstance(item, dict):
                compacted_content.append(item)
                continue

            if self._is_large_persisted_file_write(item):
                compacted_item = dict(item)
                compacted_input = dict(item.get("input") or {})
                content_value = compacted_input.get("content")
                compacted_input["content"] = _OMITTED_PERSISTED_FILE_CONTENT
                compacted_input["content_length"] = len(content_value) if isinstance(content_value, str) else None
                compacted_input["log_omitted"] = "persisted_file_content"
                compacted_item["input"] = compacted_input
                compacted_content.append(compacted_item)
                changed = True
                continue

            if item.get("name") == "Read":
                input_payload = item.get("input")
                file_path = input_payload.get("file_path") if isinstance(input_payload, dict) else None
                if isinstance(file_path, str) and self._is_persisted_read_path(file_path):
                    tool_id = item.get("id")
                    if isinstance(tool_id, str):
                        self._omitted_persisted_read_tool_ids.add(tool_id)
                    compacted_item = dict(item)
                    compacted_item["log_omitted"] = "persisted_file_read"
                    compacted_content.append(compacted_item)
                    changed = True
                    continue

            if item.get("name") == "Bash":
                input_payload = item.get("input")
                command = input_payload.get("command") if isinstance(input_payload, dict) else None
                if isinstance(command, str) and self._is_extract_window_read_command(command):
                    tool_id = item.get("id")
                    if isinstance(tool_id, str):
                        self._omitted_bash_read_tool_ids.add(tool_id)
                    compacted_item = dict(item)
                    compacted_input = dict(input_payload or {})
                    compacted_input["command_length"] = len(command)
                    compacted_item["input"] = compacted_input
                    compacted_item["log_omitted"] = "bash_extract_window_read"
                    compacted_content.append(compacted_item)
                    changed = True
                    continue
                if isinstance(command, str) and self._is_coverage_ledger_write_command(command):
                    compacted_item = dict(item)
                    compacted_input = dict(input_payload or {})
                    compacted_input["command"] = _OMITTED_LEDGER_WRITE_COMMAND
                    compacted_input["command_length"] = len(command)
                    compacted_item["input"] = compacted_input
                    compacted_item["log_omitted"] = "coverage_ledger_write"
                    compacted_content.append(compacted_item)
                    changed = True
                    continue

            tool_use_id = item.get("tool_use_id")
            is_error = item.get("is_error") is True
            if isinstance(tool_use_id, str) and tool_use_id in self._omitted_bash_read_tool_ids and not is_error:
                content_value = item.get("content")
                compacted_item = dict(item)
                compacted_item["content"] = _OMITTED_BASH_READ_CONTENT
                compacted_item["content_length"] = self._value_length(content_value)
                compacted_item["log_omitted"] = "bash_extract_window_output"
                omitted_tool_result_ids.add(tool_use_id)
                compacted_content.append(compacted_item)
                changed = True
                continue

            if isinstance(tool_use_id, str) and tool_use_id in self._omitted_persisted_read_tool_ids and not is_error:
                content_value = item.get("content")
                compacted_item = dict(item)
                compacted_item["content"] = _OMITTED_PERSISTED_READ_CONTENT
                compacted_item["content_length"] = len(content_value) if isinstance(content_value, str) else None
                compacted_item["log_omitted"] = "persisted_file_read"
                compacted_content.append(compacted_item)
                changed = True
                continue

            if omit_skill_reference_result and not is_error:
                content_value = item.get("content")
                compacted_item = dict(item)
                compacted_item["content"] = _OMITTED_SKILL_REFERENCE_CONTENT
                compacted_item["content_length"] = len(content_value) if isinstance(content_value, str) else None
                compacted_item["log_omitted"] = "skill_reference_read"
                compacted_content.append(compacted_item)
                changed = True
                continue

            compacted_content.append(item)

        if not changed:
            return payload

        compacted_message = dict(message)
        compacted_message["content"] = compacted_content
        tool_use_result = compacted_message.get("tool_use_result")
        if isinstance(tool_use_result, dict):
            file_result = tool_use_result.get("file")
            if omit_skill_reference_result and isinstance(file_result, dict):
                compacted_file = dict(file_result)
                file_content = compacted_file.get("content")
                if isinstance(file_content, str):
                    compacted_file["content"] = _OMITTED_SKILL_REFERENCE_CONTENT
                    compacted_file["content_length"] = len(file_content)
                    compacted_file["log_omitted"] = "skill_reference_read"
                    compacted_result = dict(tool_use_result)
                    compacted_result["file"] = compacted_file
                    compacted_message["tool_use_result"] = compacted_result
                    tool_use_result = compacted_result
            if isinstance(file_result, dict):
                file_path = file_result.get("filePath")
                if isinstance(file_path, str) and self._is_persisted_read_path(file_path):
                    compacted_file = dict(file_result)
                    file_content = compacted_file.get("content")
                    if isinstance(file_content, str):
                        compacted_file["content"] = _OMITTED_PERSISTED_READ_CONTENT
                        compacted_file["content_length"] = len(file_content)
                        compacted_file["log_omitted"] = "persisted_file_read"
                        compacted_result = dict(tool_use_result)
                        compacted_result["file"] = compacted_file
                        compacted_message["tool_use_result"] = compacted_result
                        tool_use_result = compacted_result
            tool_use_id = tool_use_result.get("tool_use_id")
            is_error = tool_use_result.get("is_error") is True
            should_omit_result = (
                isinstance(tool_use_id, str) and tool_use_id in self._omitted_bash_read_tool_ids
            ) or (not isinstance(tool_use_id, str) and bool(omitted_tool_result_ids))
            if should_omit_result and not is_error:
                compacted_result = dict(tool_use_result)
                stdout = compacted_result.get("stdout")
                stdout_length = self._value_length(stdout)
                if stdout is not None:
                    compacted_result["stdout"] = _OMITTED_BASH_READ_CONTENT
                    compacted_result["stdout_length"] = stdout_length
                    compacted_result["log_omitted"] = "bash_extract_window_output"
                    compacted_message["tool_use_result"] = compacted_result
        return {**payload, "message": compacted_message}

    @staticmethod
    def _is_thinking_token_progress(payload: dict[str, Any]) -> bool:
        message = payload.get("message")
        if not isinstance(message, dict) or message.get("kind") != "SystemMessage":
            return False
        data = message.get("data")
        data_subtype = data.get("subtype") if isinstance(data, dict) else None
        return message.get("subtype") == "thinking_tokens" or data_subtype == "thinking_tokens"

    def append(self, event: str, payload: dict[str, Any]) -> None:
        if event == "message" and self._is_thinking_token_progress(payload):
            return
        self._seq += 1
        if event == "message":
            payload = self._compact_message_payload(payload)
        record = {
            "seq": self._seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **payload,
        }
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str))
            handle.write("\n")


async def _run_step1_agent_async(
    *,
    input_file: str,
    output_json: str,
    extract_path: str,
    coverage_ledger_path: str,
    session_log_path: str,
    text_dir: str,
    num_segments: int,
    skill_path: str,
    repo_root: str,
    extra_requirements: str = "",
) -> None:
    # Remove stale raw.json files to ensure the latest generation is captured
    for path_str in [output_json, output_json.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")]:
        try:
            p = Path(path_str)
            if p.exists():
                p.unlink()
        except Exception:
            pass

    actual_skill = Path(skill_path).name if skill_path else STEP1_AGENT_SKILL
    subagents = _build_step1_subagents(actual_skill)
    prompt = build_step1_agent_prompt(
        input_file=input_file,
        output_json=output_json,
        text_dir=text_dir,
        skill_path=skill_path,
        extra_requirements=extra_requirements,
    )
    prompt = write_task_context(Path(session_log_path).with_suffix('.task.json'),
        stage='1', objective='根据选定来源和用户要求写作，只产出本项目 raw.json 与必要写作中间文件。',
        cwd=repo_root, inputs=[input_file, skill_path], writable=[text_dir],
        protected=[Path(repo_root)/'core', Path(repo_root)/'prompts', Path(repo_root)/'skills', input_file],
        done=['raw.json 可被 json.loads 读取，正文非空，元数据符合输出契约；不生成分段、配音、画面或视频。'],
        facts={'skill': actual_skill, 'subagents': list(subagents)}) + '\n' + prompt
    tools = STEP1_AGENT_TOOLS + (["Agent"] if subagents else [])
    options = ClaudeAgentOptions(
        cwd=repo_root,
        model=_anthropic_agent_options_model(config.LLM_SERVER_STEP1, config.LLM_MODEL_STEP1),
        tools=tools,
        allowed_tools=tools,
        agents=subagents or None,
        skills=[actual_skill],
        permission_mode="acceptEdits",
        max_turns=300,
        add_dirs=_step1_agent_add_dirs(input_file),
        env=build_step1_agent_env(),
        setting_sources=["project", "local"],
    )
    session_log = AgentSessionLog(session_log_path)
    session_log.append(
        "session_start",
        {
            "step": "step_1",
            "input_file": input_file,
            "output_json": output_json,
            "extract_path": extract_path,
            "coverage_ledger_path": coverage_ledger_path,
            "text_dir": text_dir,
            "num_segments": num_segments,
            "skill_path": skill_path,
            "repo_root": repo_root,
            "extra_requirements": extra_requirements,
            "add_dirs": _step1_agent_add_dirs(input_file),
            "model": config.LLM_MODEL_STEP1,
            "tools": tools,
            "skill": actual_skill,
            "subagents_enabled": bool(subagents),
            "subagents": {
                name: {
                    "description": agent.description,
                    "tools": agent.tools,
                    "model": agent.model,
                    "max_turns": agent.maxTurns,
                    "background": agent.background,
                }
                for name, agent in subagents.items()
            },
            "prompt": prompt,
        },
    )

    result_message: ResultMessage | None = None
    try:
        async for message in query(prompt=prompt, options=options):
            session_log.append("message", {"message": _serialize_sdk_message(message)})
            if isinstance(message, ResultMessage):
                result_message = message
                if message.is_error:
                    raise RuntimeError(message.result or "Claude Agent Step 1 failed")
    except Exception as exc:
        session_log.append(
            "session_error",
            {"error_type": type(exc).__name__, "error": str(exc)},
        )
        raise
    finally:
        if result_message is not None:
            session_log.append(
                "session_end",
                {
                    "success": not result_message.is_error,
                    "result": _serialize_sdk_message(result_message),
                },
            )
        else:
            session_log.append(
                "session_end",
                {"success": False, "result": None, "note": "no ResultMessage received"},
            )

    if not Path(output_json).exists():
        # Fallback: check if the agent normalized quotes in paths and wrote to a parallel directory
        normalized_str = str(output_json).replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")
        normalized_path = Path(normalized_str)
        if normalized_path.exists() and normalized_path != Path(output_json):
            import shutil
            Path(output_json).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(normalized_path, output_json)
            # Copy other text files written by the agent in text_dir
            text_path = Path(output_json).parent
            normalized_text_path = normalized_path.parent
            if normalized_text_path.exists() and normalized_text_path != text_path:
                for item in normalized_text_path.glob("*"):
                    if item.is_file():
                        shutil.copy2(item, text_path / item.name)

    if not Path(output_json).exists():
        raise FileNotFoundError(f"Claude Agent未生成raw.json: {output_json}")


def run_step1_agent(
    *,
    input_file: str,
    output_json: str,
    extract_path: str,
    coverage_ledger_path: str,
    session_log_path: str,
    text_dir: str,
    num_segments: int,
    skill_path: str,
    repo_root: str,
    extra_requirements: str = "",
) -> None:
    runner = partial(
        _run_step1_agent_async,
        input_file=input_file,
        output_json=output_json,
        extract_path=extract_path,
        coverage_ledger_path=coverage_ledger_path,
        session_log_path=session_log_path,
        text_dir=text_dir,
        num_segments=num_segments,
        skill_path=skill_path,
        repo_root=repo_root,
        extra_requirements=extra_requirements,
    )
    anyio.run(runner)


def _build_step1_5_segment_prompt(
    *,
    raw_json_path: str,
    output_json_path: str,
    target_segments: int,
) -> str:
    return (
        STEP1_5_SEGMENT_PROMPT_TEMPLATE
        .replace("{raw_json_path}", raw_json_path)
        .replace("{output_json_path}", output_json_path)
        .replace("{target_segments}", str(target_segments))
    )


async def _run_step1_5_segment_agent_async(
    *,
    raw_json_path: str,
    output_json_path: str,
    target_segments: int,
    session_log_path: str,
    repo_root: str,
    llm_server: str | None = None,
    llm_model: str | None = None,
) -> list[dict[str, Any]]:
    output_path = Path(output_json_path)
    try:
        if output_path.exists():
            output_path.unlink()
    except Exception:
        pass

    prompt = _build_step1_5_segment_prompt(
        raw_json_path=raw_json_path,
        output_json_path=output_json_path,
        target_segments=target_segments,
    )
    prompt = write_task_context(Path(session_log_path).with_suffix('.task.json'),
        stage='2', objective='只做语义分段并选择 image/hf，不修改正文或生成素材。', cwd=output_path.parent,
        inputs=[raw_json_path], writable=[output_path], protected=[raw_json_path],
        done=['只写 segments JSON；按顺序拼接内容与原文一致（忽略空白），visualizer 只能为 image/hf。'],
        facts={'target_segments': target_segments}) + '\n' + prompt
    tools = list(STEP1_5_AGENT_TOOLS)
    effective_llm_server = llm_server or config.LLM_SERVER_STEP1_5
    effective_llm_model = llm_model or config.LLM_MODEL_STEP1_5
    options = ClaudeAgentOptions(
        cwd=str(output_path.parent.resolve()),
        model=_anthropic_agent_options_model(effective_llm_server, effective_llm_model),
        tools=tools,
        allowed_tools=tools,
        permission_mode="acceptEdits",
        max_turns=80,
        add_dirs=[str(Path(raw_json_path).parent)],
        env=build_step1_5_agent_env(llm_server=llm_server, llm_model=llm_model),
        setting_sources=[],
    )
    session_log = AgentSessionLog(session_log_path)
    session_log.append(
        "session_start",
        {
            "step": "step_1_5_segment_visualizer",
            "raw_json_path": raw_json_path,
            "output_json_path": output_json_path,
            "target_segments": target_segments,
            "repo_root": repo_root,
            "llm_server": llm_server,
            "llm_model": llm_model,
            "tools": tools,
            "prompt": prompt,
        },
    )

    result_message: ResultMessage | None = None
    try:
        async for message in query(prompt=prompt, options=options):
            session_log.append("message", {"message": _serialize_sdk_message(message)})
            if isinstance(message, ResultMessage):
                result_message = message
                if message.is_error:
                    raise RuntimeError(message.result or "Claude Agent Step 1.5 failed")
    except Exception as exc:
        session_log.append("session_error", {"error_type": type(exc).__name__, "error": str(exc)})
        raise
    finally:
        session_log.append(
            "session_end",
            {
                "success": bool(result_message and not result_message.is_error),
                "result": _serialize_sdk_message(result_message) if result_message else None,
            },
        )

    if not output_path.exists():
        raise FileNotFoundError(f"Claude Agent未生成分段文件: {output_json_path}")

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    segments = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(segments, list):
        raise ValueError("Claude Agent分段文件缺少 segments 数组")
    return segments


def run_step1_5_segment_agent(
    *,
    raw_json_path: str,
    output_json_path: str,
    target_segments: int,
    session_log_path: str,
    repo_root: str,
    llm_server: str | None = None,
    llm_model: str | None = None,
) -> list[dict[str, Any]]:
    runner = partial(
        _run_step1_5_segment_agent_async,
        raw_json_path=raw_json_path,
        output_json_path=output_json_path,
        target_segments=target_segments,
        session_log_path=session_log_path,
        repo_root=repo_root,
        llm_server=llm_server,
        llm_model=llm_model,
    )
    return anyio.run(runner)


def _build_step4_motion_prompt(
    *,
    segment_payload: dict[str, Any],
    style_preset: str,
    skill_path_context: str,
    skills_root: str | Path | None = None,
    target_index_html_path: str = "",
) -> str:
    payload_json = json.dumps(segment_payload, ensure_ascii=False, indent=2)
    style_context = build_step4_motion_style_context(style_preset, skills_root=skills_root)
    return STEP4_MOTION_AGENT_PROMPT_TEMPLATE.format(
        skill_path_context=skill_path_context,
        style_preset=style_preset,
        style_context=style_context,
        payload_json=payload_json,
        target_index_html_path=target_index_html_path,
    )


async def _run_step4_motion_agent_async(
    *,
    work_dir: str,
    project_dir: str,
    segment_payload: dict[str, Any],
    duration_seconds: float | None = None,
    style_preset: str,
    max_turns: int,
    session_log_path: str,
    step4_skill_dir: str | None = None,
    llm_server: str | None = None,
    llm_model: str | None = None,
    llm_base_url: str | None = None,
) -> None:
    work_path = Path(work_dir)
    work_path.mkdir(parents=True, exist_ok=True)

    # Remove stale index.html files in both actual and normalized paths to ensure fresh copy fallback trigger
    for parent_path in [work_path, Path(str(work_path).replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'"))]:
        try:
            stale_file = parent_path / "index.html"
            if stale_file.exists():
                stale_file.unlink()
        except Exception:
            pass
    from core.infra.motion.runtime import prepare
    prepare(work_path, segment_payload)
    skill_dir = Path(step4_skill_dir) if step4_skill_dir else default_step4_motion_skill_dir()
    skill_path_context = build_step4_motion_skill_path_context(skill_dir)
    skill_add_dirs = [str(path) for path in step4_motion_skill_dirs(skill_dir.parent)]
    prompt = _build_step4_motion_prompt(
        segment_payload=segment_payload,
        style_preset=style_preset,
        skill_path_context=skill_path_context,
        skills_root=skill_dir.parent,
        target_index_html_path=str(work_path / "index.html"),
    )
    prompt = write_task_context(Path(session_log_path).with_suffix('.task.json'),
        stage='4', objective='只制作当前段落 HTML 动画，完成预览、修复和静音视频验证。', cwd=work_path,
        inputs=[work_path/'studio-payload.json', work_path/'index.html'], optional_inputs=[work_path/'index.html'], writable=[work_path],
        protected=[work_path/'studio-payload.json', work_path/'render.py', work_path/'vendor', Path(project_dir)/'text', Path(project_dir)/'voice'],
        done=['video.mp4 与当前 HTML 一致，render-report.json 的 verified 为 true；如实报告视觉检查限制。'],
        facts={'segment': segment_payload.get('segmentIndex', segment_payload.get('index')), 'fps': segment_payload.get('fps', 30)}) + '\n' + prompt
    tools = list(STEP4_MOTION_AGENT_TOOLS)
    effective_llm_server = llm_server or config.LLM_SERVER_STEP4
    effective_llm_model = llm_model or config.LLM_MODEL_STEP4
    options = ClaudeAgentOptions(
        cwd=str(work_path),
        model=_anthropic_agent_options_model(effective_llm_server, effective_llm_model),
        tools=tools,
        allowed_tools=tools,
        permission_mode="acceptEdits",
        max_turns=max(1, int(max_turns or 1)),
        add_dirs=[str(Path(project_dir)), *skill_add_dirs],
        env=build_step4_motion_agent_env(
            llm_server=llm_server,
            llm_model=llm_model,
            llm_base_url=llm_base_url,
        ),
        setting_sources=["project", "local"],
    )
    session_log = AgentSessionLog(session_log_path)
    session_log.append(
        "session_start",
        {
            "step": "step_4_motion",
            "work_dir": str(work_path),
            "project_dir": project_dir,
            "style_preset": style_preset,
            "prompt_version": STEP4_MOTION_PROMPT_VERSION,
            "max_turns": max_turns,
            "step4_skill_dir": str(skill_dir),
            "segment_payload": segment_payload,
            "duration_seconds": duration_seconds,
            "llm_server": llm_server,
            "llm_model": llm_model,
            "llm_base_url": llm_base_url,
            "tools": tools,
            "prompt": prompt,
        },
    )

    result_message: ResultMessage | None = None
    try:
        async for message in query(prompt=prompt, options=options):
            session_log.append("message", {"message": _serialize_sdk_message(message)})
            if isinstance(message, ResultMessage):
                result_message = message
                if message.is_error:
                    raise RuntimeError(message.result or "Claude Agent Step 4 HTML 动画 failed")
    except Exception as exc:
        session_log.append(
            "session_error",
            {"error_type": type(exc).__name__, "error": str(exc)},
        )
        raise
    finally:
        if result_message is not None:
            session_log.append(
                "session_end",
                {
                    "success": not result_message.is_error,
                    "result": _serialize_sdk_message(result_message),
                },
            )
        else:
            session_log.append(
                "session_end",
                {"success": False, "result": None, "note": "no ResultMessage received"},
            )

    if not (work_path / "index.html").exists():
        # Fallback: check if the agent normalized quotes in paths and wrote to a parallel directory
        normalized_str = str(work_path).replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")
        normalized_work_path = Path(normalized_str)
        if normalized_work_path.exists() and normalized_work_path != work_path:
            import shutil
            work_path.mkdir(parents=True, exist_ok=True)
            for item in normalized_work_path.glob("*"):
                if item.is_file():
                    shutil.copy2(item, work_path / item.name)

    if not (work_path / "index.html").exists():
        raise FileNotFoundError(f"Claude Agent未生成HTML 动画 index.html: {work_path / 'index.html'}")


def run_step4_motion_agent(
    *,
    work_dir: str,
    project_dir: str,
    segment_payload: dict[str, Any],
    duration_seconds: float | None = None,
    style_preset: str,
    max_turns: int,
    session_log_path: str,
    step4_skill_dir: str | None = None,
    llm_server: str | None = None,
    llm_model: str | None = None,
    llm_base_url: str | None = None,
) -> None:
    runner = partial(
        _run_step4_motion_agent_async,
        work_dir=work_dir,
        project_dir=project_dir,
        segment_payload=segment_payload,
        duration_seconds=duration_seconds,
        style_preset=style_preset,
        max_turns=max_turns,
        session_log_path=session_log_path,
        step4_skill_dir=step4_skill_dir,
        llm_server=llm_server,
        llm_model=llm_model,
        llm_base_url=llm_base_url,
    )
    anyio.run(runner)
