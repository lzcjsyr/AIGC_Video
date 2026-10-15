import json
from pathlib import Path

import anyio
from claude_agent_sdk import ResultMessage

from core.infra.ai import claude_agent
from core.pipeline import steps


def _valid_raw() -> dict:
    return {
        "source_name": "正义论",
        "video_titles": ["为什么正义不只是好心"],
        "cover_titles": ["正义之问"],
        "cover_subtitles": ["制度如何塑造命运"],
        "golden_quotes": ["真正的正义，要先问最弱的人站在哪里。"],
        "content": "这是一段没有换行的完整口播终稿。",
        "total_length": 17,
    }


def test_run_step_1_uses_claude_agent_skill_and_loads_raw_json(monkeypatch, tmp_path: Path):
    input_file = tmp_path / "book.md"
    input_file.write_text("source text", encoding="utf-8")

    captured = {}

    def fake_run_step1_agent(
        *,
        input_file,
        output_json,
        extract_path,
        coverage_ledger_path,
        session_log_path,
        text_dir,
        num_segments,
        skill_path,
        repo_root,
        extra_requirements="",
    ):
        captured.update(
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
        Path(output_json).write_text(json.dumps(_valid_raw(), ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(steps, "run_step1_agent", fake_run_step1_agent)
    monkeypatch.setattr(steps, "export_raw_to_docx", lambda *args, **kwargs: None)
    monkeypatch.setattr(steps.config, "STEP1_AGENT_SKILL", "book-video-script_V2")

    result = steps.run_step_1(str(input_file), str(tmp_path / "output"), num_segments=70)

    assert result["success"] is True
    raw_json_path = Path(result["raw"]["raw_json_path"])
    assert raw_json_path.name == "raw.json"
    assert raw_json_path.parent.name == "text"
    assert captured["input_file"] == str(input_file)
    assert captured["output_json"] == str(raw_json_path)
    assert Path(captured["extract_path"]).name == claude_agent.STEP1_EXTRACT_NAME
    assert Path(captured["coverage_ledger_path"]).name == claude_agent.STEP1_COVERAGE_LEDGER_NAME
    assert Path(captured["session_log_path"]).name == claude_agent.STEP1_SESSION_LOG_NAME
    assert captured["num_segments"] == 70
    assert captured["skill_path"].endswith("skills/step1/book-video-script_V2")
    assert captured["repo_root"] == steps._get_project_root()
    assert captured["extra_requirements"] == ""
    assert result["raw"]["total_length"] == 17


def test_run_step_1_passes_extra_requirements_to_agent(monkeypatch, tmp_path: Path):
    input_file = tmp_path / "book.md"
    input_file.write_text("source text", encoding="utf-8")
    captured = {}

    def fake_run_step1_agent(**kwargs):
        captured.update(kwargs)
        Path(kwargs["output_json"]).write_text(json.dumps(_valid_raw(), ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(steps, "run_step1_agent", fake_run_step1_agent)
    monkeypatch.setattr(steps, "export_raw_to_docx", lambda *args, **kwargs: None)
    monkeypatch.setattr(steps.config, "STEP1_AGENT_SKILL", "book-video-script_V2")

    result = steps.run_step_1(
        str(input_file),
        str(tmp_path / "output"),
        num_segments=70,
        extra_requirements="重点突出女性命运，不要写成王朝史摘要",
    )

    assert result["success"] is True
    assert captured["extra_requirements"] == "重点突出女性命运，不要写成王朝史摘要"


def test_step_1_rejects_agent_output_that_does_not_match_raw_contract(tmp_path: Path):
    invalid_path = tmp_path / "raw.json"
    invalid_path.write_text(json.dumps({"content": "缺少字段"}, ensure_ascii=False), encoding="utf-8")

    try:
        steps.load_step1_agent_raw(str(invalid_path))
    except ValueError as exc:
        assert "source_name" in str(exc)
        assert "comment_hook_options" not in str(exc)
        assert "share_hook_options" not in str(exc)
    else:
        raise AssertionError("invalid Step 1 raw JSON should be rejected")


def test_step_1_loads_raw_json_without_adding_target_segments(tmp_path: Path):
    raw_path = tmp_path / "raw.json"
    raw_data = _valid_raw()
    raw_path.write_text(json.dumps(raw_data, ensure_ascii=False), encoding="utf-8")

    loaded = steps.load_step1_agent_raw(str(raw_path))
    persisted = json.loads(raw_path.read_text(encoding="utf-8"))

    assert "target_segments" not in loaded
    assert "target_segments" not in persisted


def test_step_1_preserves_content_newlines_in_raw_json(tmp_path: Path):
    raw_path = tmp_path / "raw.json"
    content = "第一段内容。\n\n第二段内容。\n第三段内容。"
    raw_data = {**_valid_raw(), "content": content, "total_length": len(content)}
    raw_path.write_text(json.dumps(raw_data, ensure_ascii=False), encoding="utf-8")

    loaded = steps.load_step1_agent_raw(str(raw_path))
    persisted = json.loads(raw_path.read_text(encoding="utf-8"))

    assert loaded["content"] == content
    assert persisted["content"] == content
    assert persisted["total_length"] == len(content)


def test_step_1_removes_legacy_target_segments_from_raw_json(tmp_path: Path):
    raw_path = tmp_path / "raw.json"
    raw_data = {**_valid_raw(), "target_segments": 1}
    raw_path.write_text(json.dumps(raw_data, ensure_ascii=False), encoding="utf-8")

    loaded = steps.load_step1_agent_raw(str(raw_path))
    persisted = json.loads(raw_path.read_text(encoding="utf-8"))

    assert "target_segments" not in loaded
    assert "target_segments" not in persisted


def test_build_step1_agent_env_uses_mimo_gateway(monkeypatch):
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_SERVER_STEP1",
        "mimo",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_MODEL_STEP1",
        "mimo-v2.5-pro",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.MIMO_API_KEY",
        "test-mimo-key",
        raising=False,
    )
    env = claude_agent.build_step1_agent_env()
    assert env["ANTHROPIC_BASE_URL"] == "https://api.xiaomimimo.com/anthropic"
    assert env["ANTHROPIC_API_KEY"] == "test-mimo-key"
    assert env["ANTHROPIC_MODEL"] == "mimo-v2.5-pro"


def test_build_step1_agent_env_uses_kimi_cn_gateway(monkeypatch):
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_SERVER_STEP1",
        "kimi",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_MODEL_STEP1",
        "kimi-k2.6",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.KIMI_API_KEY",
        "test-kimi-key",
        raising=False,
    )
    env = claude_agent.build_step1_agent_env()
    assert env["ANTHROPIC_BASE_URL"] == "https://api.moonshot.cn/anthropic"
    assert env["ANTHROPIC_API_KEY"] == "test-kimi-key"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "test-kimi-key"
    assert env["ANTHROPIC_MODEL"] == "kimi-k2.6"


def test_build_step1_agent_env_uses_openrouter_auth_token_only(monkeypatch):
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_SERVER_STEP1",
        "openrouter",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_MODEL_STEP1",
        "tencent/hy3",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.OPENROUTER_API_KEY",
        "test-openrouter-key",
        raising=False,
    )
    env = claude_agent.build_step1_agent_env()
    assert env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["ANTHROPIC_AUTH_TOKEN"] == "test-openrouter-key"
    assert env["ANTHROPIC_MODEL"] == "tencent/hy3"
    assert env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "4096"
    assert env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] == "40"


def test_build_step1_agent_env_uses_volcengine_anthropic_compatible_gateway(monkeypatch):
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_SERVER_STEP1",
        "volcengine",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_MODEL_STEP1",
        "doubao-seed-2.0-code",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.VOLCENGINE_API_KEY",
        "test-volc-key",
        raising=False,
    )
    env = claude_agent.build_step1_agent_env()
    assert env["ANTHROPIC_BASE_URL"] == "https://ark.cn-beijing.volces.com/api/compatible"
    assert env["ANTHROPIC_API_KEY"] == "test-volc-key"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "test-volc-key"
    assert env["ANTHROPIC_MODEL"] == "doubao-seed-2.0-code"


def test_build_step1_5_agent_env_uses_dedicated_model(monkeypatch):
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_SERVER_STEP1",
        "mimo",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_MODEL_STEP1",
        "mimo-v2.5-pro",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_SERVER_STEP1_5",
        "kimi",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.LLM_MODEL_STEP1_5",
        "kimi-k2.6",
        raising=False,
    )
    monkeypatch.setattr(
        "core.infra.ai.claude_agent.config.KIMI_API_KEY",
        "test-kimi-key",
        raising=False,
    )

    env = claude_agent.build_step1_5_agent_env()

    assert env["ANTHROPIC_BASE_URL"] == "https://api.moonshot.cn/anthropic"
    assert env["ANTHROPIC_API_KEY"] == "test-kimi-key"
    assert env["ANTHROPIC_MODEL"] == "kimi-k2.6"


def test_build_step1_5_segment_prompt_keeps_json_example():
    prompt = claude_agent._build_step1_5_segment_prompt(
        raw_json_path="/tmp/project/text/raw.json",
        output_json_path="/tmp/project/text/_step1_5_segments.json",
        target_segments=75,
    )

    assert "/tmp/project/text/raw.json" in prompt
    assert "/tmp/project/text/_step1_5_segments.json" in prompt
    assert "75" in prompt
    assert '"segments"' in prompt
    assert '"visualizer": "image"' in prompt


def test_step1_agent_allows_300_turns(monkeypatch, tmp_path: Path):
    captured = {}
    output_json = tmp_path / "text" / "raw.json"

    async def fake_query(*, prompt, options):
        captured["max_turns"] = options.max_turns
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(_valid_raw(), ensure_ascii=False), encoding="utf-8")
        yield ResultMessage(
            subtype="success",
            duration_ms=0,
            duration_api_ms=0,
            is_error=False,
            num_turns=1,
            session_id="test-session",
        )

    monkeypatch.setattr(claude_agent, "query", fake_query)
    monkeypatch.setattr(claude_agent, "build_step1_agent_env", lambda: {})

    async def run_agent():
        await claude_agent._run_step1_agent_async(
            input_file=str(tmp_path / "book.pdf"),
            output_json=str(output_json),
            extract_path=str(tmp_path / "text" / claude_agent.STEP1_EXTRACT_NAME),
            coverage_ledger_path=str(tmp_path / "text" / claude_agent.STEP1_COVERAGE_LEDGER_NAME),
            session_log_path=str(tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME),
            text_dir=str(tmp_path / "text"),
            num_segments=70,
            skill_path=str(tmp_path / "skills" / "book-video-script"),
            repo_root=str(tmp_path),
        )

    anyio.run(run_agent)

    assert captured["max_turns"] == 300


def test_step1_agent_keeps_agent_tool_disabled_without_subagents(monkeypatch, tmp_path: Path):
    captured = {}
    output_json = tmp_path / "text" / "raw.json"

    async def fake_query(*, prompt, options):
        captured["allowed_tools"] = list(options.allowed_tools)
        captured["agents"] = options.agents
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(_valid_raw(), ensure_ascii=False), encoding="utf-8")
        yield ResultMessage(
            subtype="success",
            duration_ms=0,
            duration_api_ms=0,
            is_error=False,
            num_turns=1,
            session_id="test-session",
        )

    monkeypatch.setattr(claude_agent, "query", fake_query)
    monkeypatch.setattr(claude_agent, "build_step1_agent_env", lambda: {})
    monkeypatch.setattr(claude_agent.config, "STEP1_SUBAGENTS", {"enabled": False, "agents": {}}, raising=False)

    async def run_agent():
        await claude_agent._run_step1_agent_async(
            input_file=str(tmp_path / "book.pdf"),
            output_json=str(output_json),
            extract_path=str(tmp_path / "text" / claude_agent.STEP1_EXTRACT_NAME),
            coverage_ledger_path=str(tmp_path / "text" / claude_agent.STEP1_COVERAGE_LEDGER_NAME),
            session_log_path=str(tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME),
            text_dir=str(tmp_path / "text"),
            num_segments=70,
            skill_path=str(tmp_path / "skills" / "book-video-script"),
            repo_root=str(tmp_path),
        )

    anyio.run(run_agent)

    assert "Agent" not in captured["allowed_tools"]
    assert captured["agents"] is None


def test_step1_agent_configures_enabled_subagents(monkeypatch, tmp_path: Path):
    captured = {}
    output_json = tmp_path / "text" / "raw.json"
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("写入 _title_quote_candidates.json。", encoding="utf-8")

    async def fake_query(*, prompt, options):
        captured["allowed_tools"] = list(options.allowed_tools)
        captured["agents"] = options.agents
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(_valid_raw(), ensure_ascii=False), encoding="utf-8")
        yield ResultMessage(
            subtype="success",
            duration_ms=0,
            duration_api_ms=0,
            is_error=False,
            num_turns=1,
            session_id="test-session",
        )

    monkeypatch.setattr(claude_agent, "query", fake_query)
    monkeypatch.setattr(claude_agent, "build_step1_agent_env", lambda: {})
    monkeypatch.setattr(
        claude_agent.config,
        "STEP1_SUBAGENTS",
        {
            "enabled": True,
            "agents": {
                "title-quote-writer": {
                    "enabled": True,
                    "description": "生成标题、封面文案和金句",
                    "prompt_file": str(prompt_file),
                    "model": "inherit",
                    "max_turns": 12,
                    "background": True,
                    "tools": ["Read", "Write"],
                },
                "disabled-agent": {"enabled": False, "description": "不应启用"},
            },
        },
        raising=False,
    )

    async def run_agent():
        await claude_agent._run_step1_agent_async(
            input_file=str(tmp_path / "book.pdf"),
            output_json=str(output_json),
            extract_path=str(tmp_path / "text" / claude_agent.STEP1_EXTRACT_NAME),
            coverage_ledger_path=str(tmp_path / "text" / claude_agent.STEP1_COVERAGE_LEDGER_NAME),
            session_log_path=str(tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME),
            text_dir=str(tmp_path / "text"),
            num_segments=70,
            skill_path=str(tmp_path / "skills" / "book-video-script"),
            repo_root=str(tmp_path),
        )

    anyio.run(run_agent)

    agent = captured["agents"]["title-quote-writer"]
    assert "Agent" in captured["allowed_tools"]
    assert set(captured["agents"]) == {"title-quote-writer"}
    assert agent.description == "生成标题、封面文案和金句"
    assert agent.prompt == "写入 _title_quote_candidates.json。"
    assert agent.tools == ["Read", "Write"]
    assert agent.maxTurns == 12
    assert agent.background is True


def test_commerce_skill_disables_agent_tool_even_when_global_subagents_are_enabled(monkeypatch, tmp_path: Path):
    captured = {}
    output_json = tmp_path / "text" / "raw.json"

    async def fake_query(*, prompt, options):
        captured["allowed_tools"] = list(options.allowed_tools)
        captured["agents"] = options.agents
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(_valid_raw(), ensure_ascii=False), encoding="utf-8")
        yield ResultMessage(
            subtype="success",
            duration_ms=0,
            duration_api_ms=0,
            is_error=False,
            num_turns=1,
            session_id="test-session",
        )

    monkeypatch.setattr(claude_agent, "query", fake_query)
    monkeypatch.setattr(claude_agent, "build_step1_agent_env", lambda: {})
    monkeypatch.setattr(
        claude_agent.config,
        "STEP1_SUBAGENTS",
        {
            "enabled": True,
            "agents": {
                "title-quote-writer": {
                    "enabled": True,
                    "description": "通用标题写手",
                    "tools": ["Read"],
                }
            },
        },
        raising=False,
    )

    async def run_agent():
        await claude_agent._run_step1_agent_async(
            input_file=str(tmp_path / "book.epub"),
            output_json=str(output_json),
            extract_path=str(tmp_path / "text" / claude_agent.STEP1_EXTRACT_NAME),
            coverage_ledger_path=str(tmp_path / "text" / claude_agent.STEP1_COVERAGE_LEDGER_NAME),
            session_log_path=str(tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME),
            text_dir=str(tmp_path / "text"),
            num_segments=50,
            skill_path=str(tmp_path / "skills" / "book-commerce-video-script"),
            repo_root=str(tmp_path),
        )

    anyio.run(run_agent)

    assert "Agent" not in captured["allowed_tools"]
    assert captured["agents"] is None


def test_step1_prompt_uses_available_subagents_only_for_specific_problems():
    prompt = Path("prompts/step1_agent.md").read_text(encoding="utf-8")
    assert "如果当前会话存在可调用的 subagent" in prompt
    assert "只告知输入稿件路径和需要保存的输出文件路径" in prompt
    assert "title-quote-writer" in prompt and "fact-style-reviewer" in prompt
    assert "不为凑轮次反复起草或审稿" in prompt
    assert "必须先调用" not in prompt
    assert "不要转发整个对话或整本来源" in prompt


def test_step1_agent_adds_input_directory_to_options(monkeypatch, tmp_path: Path):
    captured = {}
    output_json = tmp_path / "text" / "raw.json"
    input_dir = tmp_path / "input" / "book_folder"
    input_dir.mkdir(parents=True)

    async def fake_query(*, prompt, options):
        captured["add_dirs"] = [str(path) for path in options.add_dirs]
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(_valid_raw(), ensure_ascii=False), encoding="utf-8")
        yield ResultMessage(
            subtype="success",
            duration_ms=0,
            duration_api_ms=0,
            is_error=False,
            num_turns=1,
            session_id="test-session",
        )

    monkeypatch.setattr(claude_agent, "query", fake_query)
    monkeypatch.setattr(claude_agent, "build_step1_agent_env", lambda: {})

    async def run_agent():
        await claude_agent._run_step1_agent_async(
            input_file=str(input_dir),
            output_json=str(output_json),
            extract_path=str(tmp_path / "text" / claude_agent.STEP1_EXTRACT_NAME),
            coverage_ledger_path=str(tmp_path / "text" / claude_agent.STEP1_COVERAGE_LEDGER_NAME),
            session_log_path=str(tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME),
            text_dir=str(tmp_path / "text"),
            num_segments=70,
            skill_path=str(tmp_path / "skills" / "book-video-script"),
            repo_root=str(tmp_path),
        )

    anyio.run(run_agent)

    assert str(input_dir) in captured["add_dirs"]


def test_step1_agent_prompt_includes_absolute_skill_path(tmp_path: Path):
    from core.prompts import build_step1_agent_prompt

    skill_path = tmp_path / "skills" / "book-video-script"
    skill_path.mkdir(parents=True)

    prompt = build_step1_agent_prompt(
        input_file=str(tmp_path / "book.pdf"),
        output_json=str(tmp_path / "output" / "text" / "raw.json"),
        text_dir=str(tmp_path / "output" / "text"),
        skill_path=str(skill_path),
    )

    assert str(skill_path) in prompt
    assert str(skill_path).startswith("/")
    assert "target_segments" not in prompt
    assert str(tmp_path / "output" / "text") in prompt
    assert "_coverage_ledger.json" not in prompt
    assert "_extract.md" not in prompt
    assert "不要绕过" in prompt
    assert "使用已启用的原生 skill" not in prompt
    assert "json.loads" in prompt


def test_step1_agent_prompt_includes_extra_requirements(tmp_path: Path):
    from core.prompts import build_step1_agent_prompt

    prompt = build_step1_agent_prompt(
        input_file=str(tmp_path / "book.pdf"),
        output_json=str(tmp_path / "output" / "text" / "raw.json"),
        text_dir=str(tmp_path / "output" / "text"),
        skill_path=str(tmp_path / "skills" / "book-video-script"),
        extra_requirements="重点突出女性命运，不要写成王朝史摘要",
    )

    assert "用户额外要求" in prompt
    assert "重点突出女性命运，不要写成王朝史摘要" in prompt


def test_agent_session_log_appends_jsonl_records(tmp_path: Path):
    log_path = tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME
    session_log = claude_agent.AgentSessionLog(log_path)
    session_log.append("session_start", {"step": "step_1"})
    session_log.append("message", {"message": {"kind": "UserMessage", "content": "hi"}})

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["event"] == "session_start"
    assert first["seq"] == 1
    assert second["event"] == "message"
    assert second["seq"] == 2
    assert "ts" in first


def test_agent_session_log_skips_thinking_token_progress_events(tmp_path: Path):
    log_path = tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME
    session_log = claude_agent.AgentSessionLog(log_path)

    session_log.append(
        "message",
        {
            "message": {
                "kind": "SystemMessage",
                "subtype": "thinking_tokens",
                "data": {
                    "type": "system",
                    "subtype": "thinking_tokens",
                    "estimated_tokens": 30,
                    "estimated_tokens_delta": 5,
                },
            }
        },
    )
    session_log.append("message", {"message": {"kind": "UserMessage", "content": "hi"}})

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert len(records) == 1
    assert records[0]["seq"] == 1
    assert records[0]["message"]["kind"] == "UserMessage"


def test_agent_session_log_omits_bash_extract_window_output(tmp_path: Path):
    log_path = tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME
    session_log = claude_agent.AgentSessionLog(log_path)
    large_stdout = "正文" * 10000
    session_log.append(
        "message",
        {
            "message": {
                "kind": "AssistantMessage",
                "content": [
                    {
                        "id": "call_read_window",
                        "name": "Bash",
                        "input": {
                            "command": 'EXTRACT="/tmp/output/text/_extract.md"\nsed -n \'1,120p\' "$EXTRACT"',
                            "description": "Read window 1 (lines 1-120)",
                        },
                    }
                ],
            }
        },
    )
    session_log.append(
        "message",
        {
            "message": {
                "kind": "UserMessage",
                "content": [
                    {
                        "tool_use_id": "call_read_window",
                        "content": large_stdout,
                        "is_error": False,
                    }
                ],
                "tool_use_result": {
                    "tool_use_id": "call_read_window",
                    "stdout": large_stdout,
                    "stderr": "",
                    "is_error": False,
                },
            }
        },
    )

    first, second = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assistant_item = first["message"]["content"][0]
    user_item = second["message"]["content"][0]
    assert "_extract.md" in assistant_item["input"]["command"]
    assert assistant_item["input"]["command_length"] == len('EXTRACT="/tmp/output/text/_extract.md"\nsed -n \'1,120p\' "$EXTRACT"')
    assert assistant_item["log_omitted"] == "bash_extract_window_read"
    assert user_item["content"].startswith("[omitted:")
    assert user_item["content_length"] == len("正文" * 10000)
    assert user_item["log_omitted"] == "bash_extract_window_output"
    tool_result = second["message"]["tool_use_result"]
    assert tool_result["stdout"].startswith("[omitted:")
    assert tool_result["stdout_length"] == len(large_stdout)
    assert tool_result["log_omitted"] == "bash_extract_window_output"


def test_agent_session_log_omits_bash_extract_txt_window_output_after_truncation(tmp_path: Path):
    log_path = tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME
    session_log = claude_agent.AgentSessionLog(log_path)
    truncated_stdout = {
        "_truncated": True,
        "length": 22885,
        "preview": "JONATHAN SPENCE\nGOD'S CHINESE SON\n" + ("正文" * 1000),
    }
    command = 'EXTRACT="/tmp/output/text/_extract.txt"\nsed -n \'1,120p\' "$EXTRACT"'
    session_log.append(
        "message",
        {
            "message": {
                "kind": "AssistantMessage",
                "content": [
                    {
                        "id": "call_read_window_txt",
                        "name": "Bash",
                        "input": {
                            "command": command,
                            "description": "Read window 1 (lines 1-120)",
                        },
                    }
                ],
            }
        },
    )
    session_log.append(
        "message",
        {
            "message": {
                "kind": "UserMessage",
                "content": [
                    {
                        "tool_use_id": "call_read_window_txt",
                        "content": truncated_stdout,
                        "is_error": False,
                    }
                ],
                "tool_use_result": {
                    "tool_use_id": "call_read_window_txt",
                    "stdout": truncated_stdout,
                    "stderr": "",
                    "is_error": False,
                },
            }
        },
    )

    first, second = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assistant_item = first["message"]["content"][0]
    user_item = second["message"]["content"][0]
    assert assistant_item["input"]["command"] == command
    assert assistant_item["log_omitted"] == "bash_extract_window_read"
    assert user_item["content"].startswith("[omitted:")
    assert user_item["content_length"] == 22885
    assert "JONATHAN SPENCE" not in json.dumps(second, ensure_ascii=False)
    tool_result = second["message"]["tool_use_result"]
    assert tool_result["stdout"].startswith("[omitted:")
    assert tool_result["stdout_length"] == 22885


def test_agent_session_log_omits_skill_reference_read_content(tmp_path: Path):
    log_path = tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME
    session_log = claude_agent.AgentSessionLog(log_path)
    skill_content = "# Direct Large-Block Reading Strategy\n" + ("规则\n" * 2000)
    session_log.append(
        "message",
        {
            "message": {
                "kind": "UserMessage",
                "content": [
                    {
                        "tool_use_id": "call_read_skill",
                        "content": skill_content,
                        "is_error": False,
                    }
                ],
                "tool_use_result": {
                    "type": "text",
                    "file": {
                        "filePath": "/repo/skills/step1/book-video-script/references/reading-strategy.md",
                        "content": skill_content,
                        "numLines": 2001,
                    },
                },
            }
        },
    )

    record = json.loads(log_path.read_text(encoding="utf-8"))
    item = record["message"]["content"][0]
    assert item["content"].startswith("[omitted:")
    assert item["content_length"] == len(skill_content)
    assert item["log_omitted"] == "skill_reference_read"
    file_result = record["message"]["tool_use_result"]["file"]
    assert file_result["content"].startswith("[omitted:")
    assert file_result["content_length"] == len(skill_content)
    assert "Direct Large-Block" not in json.dumps(record, ensure_ascii=False)


def test_agent_session_log_omits_large_write_content(tmp_path: Path):
    log_path = tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME
    session_log = claude_agent.AgentSessionLog(log_path)
    draft = "稿件" * 2000
    session_log.append(
        "message",
        {
            "message": {
                "kind": "AssistantMessage",
                "content": [
                    {
                        "id": "call_write_draft",
                        "name": "Write",
                        "input": {
                            "file_path": "/tmp/output/text/_draft_v1.txt",
                            "content": draft,
                        },
                    }
                ],
            }
        },
    )

    record = json.loads(log_path.read_text(encoding="utf-8"))
    input_payload = record["message"]["content"][0]["input"]
    assert input_payload["content"].startswith("[omitted:")
    assert input_payload["content_length"] == len(draft)
    assert input_payload["log_omitted"] == "persisted_file_content"
    assert "稿件稿件" not in json.dumps(record, ensure_ascii=False)


def test_agent_session_log_omits_coverage_ledger_write_command(tmp_path: Path):
    log_path = tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME
    session_log = claude_agent.AgentSessionLog(log_path)
    command = 'cat > "/tmp/output/text/_coverage_ledger.json" << "JSONEOF"\n' + ("窗口\n" * 2000)
    session_log.append(
        "message",
        {
            "message": {
                "kind": "AssistantMessage",
                "content": [
                    {
                        "id": "call_write_ledger",
                        "name": "Bash",
                        "input": {"command": command},
                    }
                ],
            }
        },
    )

    record = json.loads(log_path.read_text(encoding="utf-8"))
    item = record["message"]["content"][0]
    assert item["input"]["command"].startswith("[omitted:")
    assert item["input"]["command_length"] == len(command)
    assert item["log_omitted"] == "coverage_ledger_write"
    assert "窗口窗口" not in json.dumps(record, ensure_ascii=False)


def test_agent_session_log_omits_persisted_read_content(tmp_path: Path):
    log_path = tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME
    session_log = claude_agent.AgentSessionLog(log_path)
    draft_content = "子贵母死" * 1200
    session_log.append(
        "message",
        {
            "message": {
                "kind": "AssistantMessage",
                "content": [
                    {
                        "id": "call_read_draft",
                        "name": "Read",
                        "input": {"file_path": "/tmp/output/text/_draft_final.txt"},
                    }
                ],
            }
        },
    )
    session_log.append(
        "message",
        {
            "message": {
                "kind": "UserMessage",
                "content": [
                    {
                        "tool_use_id": "call_read_draft",
                        "content": draft_content,
                        "is_error": False,
                    }
                ],
                "tool_use_result": {
                    "type": "text",
                    "file": {
                        "filePath": "/tmp/output/text/_draft_final.txt",
                        "content": draft_content,
                        "numLines": 20,
                    },
                },
            }
        },
    )

    first, second = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert first["message"]["content"][0]["log_omitted"] == "persisted_file_read"
    assert second["message"]["content"][0]["content"].startswith("[omitted:")
    assert second["message"]["content"][0]["content_length"] == len(draft_content)
    file_result = second["message"]["tool_use_result"]["file"]
    assert file_result["content"].startswith("[omitted:")
    assert file_result["content_length"] == len(draft_content)
    assert "子贵母死子贵母死" not in json.dumps(second, ensure_ascii=False)


def test_agent_session_log_keeps_bash_extract_window_errors(tmp_path: Path):
    log_path = tmp_path / "text" / claude_agent.STEP1_SESSION_LOG_NAME
    session_log = claude_agent.AgentSessionLog(log_path)
    session_log.append(
        "message",
        {
            "message": {
                "kind": "AssistantMessage",
                "content": [
                    {
                        "id": "call_read_window",
                        "name": "Bash",
                        "input": {"command": "sed -n '1,120p' /tmp/output/text/_extract.md"},
                    }
                ],
            }
        },
    )
    session_log.append(
        "message",
        {
            "message": {
                "kind": "UserMessage",
                "content": [
                    {
                        "tool_use_id": "call_read_window",
                        "content": "sed: file not found",
                        "is_error": True,
                    }
                ],
                "tool_use_result": {
                    "tool_use_id": "call_read_window",
                    "stdout": "",
                    "stderr": "sed: file not found",
                    "is_error": True,
                },
            }
        },
    )

    second = json.loads(log_path.read_text(encoding="utf-8").splitlines()[1])
    assert second["message"]["content"][0]["content"] == "sed: file not found"
    assert second["message"]["tool_use_result"]["stderr"] == "sed: file not found"


def test_run_step_1_skill_path_fallback(monkeypatch, tmp_path: Path):
    input_file = tmp_path / "book.md"
    input_file.write_text("source text", encoding="utf-8")

    captured = {}

    def fake_run_step1_agent(**kwargs):
        captured.update(kwargs)
        Path(kwargs["output_json"]).write_text(json.dumps(_valid_raw(), ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(steps, "run_step1_agent", fake_run_step1_agent)
    monkeypatch.setattr(steps, "export_raw_to_docx", lambda *args, **kwargs: None)
    
    monkeypatch.setattr(steps.config, "STEP1_AGENT_SKILL", "non-existent-skill-name")

    result = steps.run_step_1(str(input_file), str(tmp_path / "output"), num_segments=70)

    assert result["success"] is True
    assert captured["skill_path"].endswith("skills/step1/sample_writer")
