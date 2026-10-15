import json
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from core.infra.ai import claude_agent


def test_step4_motion_agent_env_uses_step4_base_url_override(monkeypatch):
    monkeypatch.setattr(claude_agent.config, "LLM_SERVER_STEP4", "siliconflow")
    monkeypatch.setattr(claude_agent.config, "LLM_MODEL_STEP4", "custom-model")
    monkeypatch.setattr(claude_agent.config, "SILICONFLOW_KEY", "test-key")
    monkeypatch.setattr(
        claude_agent.config,
        "LLM_BASE_URL_STEP4_OVERRIDE",
        "https://llm-gateway.example.test/anthropic",
        raising=False,
    )

    env = claude_agent.build_step4_motion_agent_env()

    assert env["ANTHROPIC_BASE_URL"] == "https://llm-gateway.example.test/anthropic"
    assert env["ANTHROPIC_MODEL"] == "custom-model"


def test_step4_motion_agent_uses_deepseek_v4_pro_for_claude_code(monkeypatch):
    monkeypatch.setattr(claude_agent.config, "LLM_SERVER_STEP4", "deepseek")
    monkeypatch.setattr(claude_agent.config, "LLM_MODEL_STEP4", "deepseek-v4-pro")
    monkeypatch.setattr(claude_agent.config, "DEEPSEEK_API_KEY", "test-deepseek-key")

    env = claude_agent.build_step4_motion_agent_env()

    assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
    assert env["ANTHROPIC_MODEL"] == "deepseek-v4-pro"
    assert env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "deepseek-v4-pro"
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "deepseek-v4-pro"
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "deepseek-flash"
    assert env["CLAUDE_CODE_SUBAGENT_MODEL"] == "deepseek-flash"
    assert env["CLAUDE_CODE_EFFORT_LEVEL"] == "max"


def test_step4_motion_agent_rewrites_deepseek_openai_base_url(monkeypatch):
    monkeypatch.setattr(claude_agent.config, "LLM_SERVER_STEP4", "deepseek")
    monkeypatch.setattr(claude_agent.config, "LLM_MODEL_STEP4", "deepseek-v4-pro")
    monkeypatch.setattr(claude_agent.config, "DEEPSEEK_API_KEY", "test-deepseek-key")

    env = claude_agent.build_step4_motion_agent_env(
        llm_server="deepseek",
        llm_model="deepseek-v4-pro",
        llm_base_url="https://api.deepseek.com/v1",
    )

    assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"


@pytest.mark.anyio
async def test_step4_motion_agent_omits_explicit_model_for_deepseek(monkeypatch, tmp_path):
    captured = {}

    async def fake_query(*, prompt, options):
        captured["model"] = options.model
        Path(options.cwd, "index.html").write_text("<html></html>", encoding="utf-8")
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            result="ok",
            session_id="session",
            total_cost_usd=0.0,
            usage={},
        )

    monkeypatch.setattr(claude_agent, "query", fake_query)
    await claude_agent._run_step4_motion_agent_async(
        work_dir=str(tmp_path / "images" / "hyperframes" / "segment_1"),
        project_dir=str(tmp_path),
        segment_payload={
            "index": 1,
            "content": "收入增长",
            "durationSeconds": 0.75,
            "width": 1280,
            "height": 720,
        },
        style_preset="data_driven",
        max_turns=1,
        session_log_path=str(tmp_path / "text" / "_step4_motion_agent_session.jsonl"),
        step4_skill_dir=str(tmp_path / "skills" / "step4" / "motion-core"),
        llm_server="deepseek",
        llm_model="deepseek-v4-pro",
    )

    assert captured["model"] is None


@pytest.mark.anyio
async def test_step4_motion_agent_uses_segment_workdir_and_step4_skill_context(monkeypatch, tmp_path):
    captured = {}
    work_dir = tmp_path / "images" / "hyperframes" / "segment_1"
    project_dir = tmp_path / "project"
    skill_dir = tmp_path / "skills" / "step4" / "motion-core"
    session_log = tmp_path / "text" / "_step4_motion_agent_session.jsonl"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\n"
        "name: motion-core\n"
        "description: READ THIS FIRST for HyperFrames tasks.\n"
        "---\n"
        "\n"
        "# Body should not be embedded\n",
        encoding="utf-8",
    )

    async def fake_query(*, prompt, options):
        captured["prompt"] = prompt
        captured["options"] = options
        Path(options.cwd, "index.html").write_text("<html></html>", encoding="utf-8")
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            result="ok",
            session_id="session",
            total_cost_usd=0.0,
            usage={},
        )

    monkeypatch.setattr(claude_agent, "query", fake_query)
    monkeypatch.setattr(claude_agent, "build_step4_motion_agent_env", lambda **_kwargs: {"ANTHROPIC_API_KEY": "key"})
    await claude_agent._run_step4_motion_agent_async(
        work_dir=str(work_dir),
        project_dir=str(project_dir),
        segment_payload={
            "index": 1,
            "content": "收入增长",
            "durationSeconds": 0.75,
            "width": 1280,
            "height": 720,
        },
        style_preset="data_driven",
        max_turns=11,
        session_log_path=str(session_log),
        step4_skill_dir=str(skill_dir),
    )

    options = captured["options"]
    assert options.cwd == str(work_dir)
    assert options.tools == ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
    assert options.allowed_tools == options.tools
    assert options.max_turns == 11
    assert str(project_dir) in options.add_dirs
    assert str(skill_dir) in options.add_dirs
    skills_root = skill_dir.parent
    assert f"STEP4_SKILLS_ROOT={skills_root}" in captured["prompt"]
    assert "直接编写本段 HTML" in captured["prompt"]
    assert "entry_path:" in captured["prompt"]
    assert f"- entry_path: {skills_root / 'motion-core/SKILL.md'}" in captured["prompt"]
    assert "Swiss Pulse" in captured["prompt"]
    assert f"motion-creative/references/data-in-motion.md -> {skills_root / 'motion-creative/references/data-in-motion.md'}" in captured["prompt"]
    assert "只在本段工作目录" in captured["prompt"]
    assert "先根据 name/description 判断本任务需要哪些 skill" not in captured["prompt"]
    assert "必读入口文件绝对路径" not in captured["prompt"]
    assert "官方 skill 包目录映射" not in captured["prompt"]
    assert "常用官方文件绝对路径" not in captured["prompt"]
    assert "HyperFrames embedded skill" not in captured["prompt"]
    assert "Layout Before Animation" not in captured["prompt"]
    assert "不修改其他段落、源码" in captured["prompt"]
    assert '"durationSeconds": 0.75' in captured["prompt"]
    assert session_log.exists()
    log_entry = json.loads(session_log.read_text(encoding="utf-8").splitlines()[0])
    assert log_entry["prompt_version"] == "2026-10-15-agent-render-v2"
    assert log_entry["step4_skill_dir"] == str(skill_dir)
    assert "embedded_skill_dir" not in log_entry
