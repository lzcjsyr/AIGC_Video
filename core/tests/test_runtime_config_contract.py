from pathlib import Path


def test_generation_params_match_cli_entrypoint_signature():
    from core.cli.ui_helpers import run_cli_main
    from core.config import get_generation_params

    params = get_generation_params()
    accepted = set(run_cli_main.__code__.co_varnames[:run_cli_main.__code__.co_argcount])

    assert set(params) <= accepted


def test_config_loads_step1_subagents(tmp_path):
    from core.config import _load_yaml_overrides

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
step1:
  llm_server: deepseek
  llm_model: deepseek-v4-pro
  agent_skill: book-video-script
  subagents:
    enabled: true
    agents:
      title-quote-writer:
        enabled: true
        description: 生成标题和金句
        prompt_file: prompts/step1_subagents/title-quote-writer.md
        model: inherit
        max_turns: 12
        background: true
        tools: [Read]
""",
        encoding="utf-8",
    )

    subagents = _load_yaml_overrides(config_path)["STEP1_SUBAGENTS"]

    assert subagents["enabled"] is True
    assert "auto_instructions" not in subagents
    assert subagents["agents"]["title-quote-writer"]["prompt_file"] == "prompts/step1_subagents/title-quote-writer.md"
    assert subagents["agents"]["title-quote-writer"]["tools"] == ["Read"]
    assert subagents["agents"]["title-quote-writer"]["max_turns"] == 12
    assert subagents["agents"]["title-quote-writer"]["background"] is True


def test_example_subagent_descriptions_are_triggerable():
    from core.config import _load_yaml_overrides

    subagents = _load_yaml_overrides("config.example.yaml")["STEP1_SUBAGENTS"]["agents"]
    title_description = subagents["title-quote-writer"]["description"]
    reviewer_description = subagents["fact-style-reviewer"]["description"]

    for marker in ["必须", "第一稿完成并达标后", "立即调用", "标题", "封面", "金句"]:
        assert marker in title_description
    for marker in ["必须", "第一稿完成并达标后", "第二稿完成并达标后", "传播钩子", "JSON 契约"]:
        assert marker in reviewer_description


def test_example_subagents_declare_background_mode():
    from core.config import _load_yaml_overrides

    subagents = _load_yaml_overrides("config.example.yaml")["STEP1_SUBAGENTS"]["agents"]

    assert subagents["title-quote-writer"]["background"] is True
    assert subagents["fact-style-reviewer"]["background"] is False


def test_config_loads_step1_5_agent_split_mode(tmp_path):
    from core.config import _load_yaml_overrides

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
step1_5:
  num_segments: 12
  split_mode: agent
  llm_server: kimi
  llm_model: kimi-k2.6
""",
        encoding="utf-8",
    )

    overrides = _load_yaml_overrides(config_path)

    assert overrides["NUM_SEGMENTS"] == 12
    assert overrides["STEP1_5_SPLIT_MODE"] == "agent"
    assert overrides["LLM_SERVER_STEP1_5"] == "kimi"
    assert overrides["LLM_MODEL_STEP1_5"] == "kimi-k2.6"


def test_title_quote_subagent_prompt_persists_candidates():
    prompt = Path("prompts/step1_subagents/title-quote-writer.md").read_text(encoding="utf-8")

    assert "_title_quote_candidates.json" in prompt
    assert "raw.json" in prompt
    assert "早期稳定稿" in prompt
    assert "json.loads" in prompt
    assert "中文引号" in prompt
    assert "先生成 20 条金句" in prompt
    assert "选出最强 3 条" in prompt
    assert "只读取主 agent 已生成的终稿" not in prompt


def test_reviewer_prompt_treats_comment_and_share_signals_as_revision_dimensions():
    prompt = Path("prompts/step1_subagents/fact-style-reviewer.md").read_text(encoding="utf-8")

    assert "评论点" in prompt
    assert "转发理由" in prompt
    assert "结构和措辞" in prompt
    assert "不要替主 agent 直接生成最终字段" not in prompt


def test_step1_subagent_prompts_do_not_depend_on_book_video_script_internals():
    prompt_dir = Path("prompts/step1_subagents")
    prompts = "\n".join(path.read_text(encoding="utf-8") for path in prompt_dir.glob("*.md"))

    forbidden = [
        "_extract.md",
        "_coverage_ledger.json",
        "_draft_v1.txt",
        "_draft_v2_structure.txt",
        "_draft_final.txt",
        "_revision_audit.json",
        "skills/step1/book-video-script",
    ]
    for marker in forbidden:
        assert marker not in prompts


def test_config_exposes_current_runtime_params():
    from core.config import config, get_generation_params, _load_yaml_overrides

    example = Path(__file__).resolve().parents[2] / "config.example.yaml"
    defaults = _load_yaml_overrides(example)
    params = get_generation_params(example)

    assert params["llm_server_step2"] == defaults["LLM_SERVER_STEP2"]
    assert params["llm_base_url_step2"] == config.LLM_SERVER_URLS[params["llm_server_step2"]]
    assert params["llm_server_step4"] == defaults["LLM_SERVER_STEP4"]
    assert params["llm_base_url_step4"] == config.LLM_SERVER_URLS[params["llm_server_step4"]]
    assert "volcengine" in config.SUPPORTED_LLM_SERVERS
    assert "kimi" in config.SUPPORTED_LLM_SERVERS
    assert config.LLM_SERVER_URLS["kimi"] == "https://api.moonshot.cn/v1"
    assert defaults["IMAGE_STYLE_PRESET"] == params["image_style_preset"]
    assert params["cover_image_server"] == "google_adc"

    config.validate_parameters(
        params["num_segments"],
        params["llm_server_step2"],
        params["image_server"],
        "bytedance",
        params["image_model"],
        params["image_size"],
        llm_model=params["llm_model_step2"],
    )


def test_google_adc_image_server_is_inherited_by_gemini_cover_defaults():
    from core.config import VideoGenerationConfig

    config = VideoGenerationConfig(
        input_file="input.pdf",
        output_dir="output",
        image_server="google_adc",
        image_model="gemini-3.1-flash-image",
        cover_image_server="",
        cover_image_model=None,
    )

    assert config.cover_image_model == "gemini-3.1-flash-image"
    assert config.cover_image_server == "google_adc"


def test_config_rejects_unsupported_llm_server():
    import pytest

    from core.config import config

    with pytest.raises(ValueError, match="不支持的LLM服务商"):
        config.validate_parameters(
            num_segments=5,
            llm_server="unknown",
            image_server="google",
            tts_server="bytedance",
            image_model="gemini-3.1-flash-image",
            image_size="1280x720",
            llm_model="model",
        )


def test_generation_params_resolve_kimi_base_url(tmp_path):
    from core.config import get_generation_params

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
step2:
  llm_server: kimi
  llm_model: kimi-k2.6
step4:
  llm_server: kimi
  llm_model: kimi-k2.6
""",
        encoding="utf-8",
    )

    params = get_generation_params(config_path)

    assert params["llm_server_step2"] == "kimi"
    assert params["llm_base_url_step2"] == "https://api.moonshot.cn/v1"
    assert params["llm_server_step4"] == "kimi"
    assert params["llm_base_url_step4"] == "https://api.moonshot.cn/v1"


def test_step4_llm_base_url_can_be_configured_independently(tmp_path):
    from core.config import get_generation_params

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
step4:
  llm_server: siliconflow
  llm_model: custom-claude-compatible-model
  llm_base_url: https://llm-gateway.example.test/anthropic
""",
        encoding="utf-8",
    )

    params = get_generation_params(config_path)

    assert params["llm_server_step4"] == "siliconflow"
    assert params["llm_model_step4"] == "custom-claude-compatible-model"
    assert params["llm_base_url_step4"] == "https://llm-gateway.example.test/anthropic"


def test_recovered_config_keeps_cover_validation_usable(monkeypatch, tmp_path):
    from core.pipeline import steps

    captured = {}

    def fake_generate_cover_images(
        project_output_dir,
        cover_image_server,
        cover_image_model,
        cover_image_size,
        cover_image_style,
        cover_image_count,
        cover_title,
        cover_subtitle,
    ):
        captured.update(
            server=cover_image_server,
            model=cover_image_model,
            size=cover_image_size,
            style=cover_image_style,
            count=cover_image_count,
            title=cover_title,
            subtitle=cover_subtitle,
        )
        return {"success": True, "cover_images": []}

    monkeypatch.setattr(steps, "generate_cover_images", fake_generate_cover_images)

    result = steps._run_cover_generation(
        str(tmp_path),
        cover_image_size=None,
        cover_image_server="google",
        cover_image_model=None,
        cover_image_style=None,
        cover_image_count=1,
        script_data={"title": "测试标题", "segments": []},
    )

    assert result["success"] is True
    assert captured["server"] == "google"
    assert captured["model"]


def test_step6_makes_every_requested_size(monkeypatch, tmp_path):
    import json

    from core.pipeline import steps

    sizes = []

    def fake_run_cover_generation(project_output_dir, cover_image_size, *args):
        sizes.append(cover_image_size)
        if cover_image_size == "bad":
            raise ValueError("封面参数校验失败")
        return {"success": True, "cover_paths": [f"cover_{cover_image_size}.png"], "failures": [], "style_id": "cover01"}

    monkeypatch.setattr(steps, "_run_cover_generation", fake_run_cover_generation)
    (tmp_path / "text").mkdir()
    (tmp_path / "text" / "raw.json").write_text(json.dumps({"title": "测试标题"}), encoding="utf-8")

    result = steps.run_step_6(str(tmp_path), ["16:9", "bad", "3:4", "16:9"], "google", None, "cover01", 1)

    assert sizes == ["16:9", "bad", "3:4"]
    assert result["success"] is True
    assert result["cover_paths"] == ["cover_16:9.png", "cover_3:4.png"]
    assert result["failures"] == ["bad: 封面参数校验失败"]

    single = steps.run_step_6(str(tmp_path), "bad", "google", None, "cover01", 1)
    assert single == {"success": False, "message": "封面参数校验失败", "failures": ["封面参数校验失败"]}


def test_default_config_makes_covers_in_several_sizes_with_style_one():
    from core import config

    assert config.COVER_IMAGE_SIZE_KEYS == ["16:9", "3:4"]
    assert set(config.COVER_IMAGE_SIZE_KEYS) <= set(config.COVER_IMAGE_SIZE_PRESETS)
    assert config.COVER_IMAGE_STYLE == "cover01"


def test_retired_cover_size_key_loads_and_is_ignored(tmp_path):
    from core.config import _load_yaml_overrides

    path = tmp_path / "config.yaml"
    path.write_text('step6:\n  default_cover_image_size_key: "1:1"\n', encoding="utf-8")

    assert _load_yaml_overrides(path) == {}


def test_retired_step5_settings_load_and_are_ignored(tmp_path):
    from core.config import _load_yaml_overrides

    path = tmp_path / "config.yaml"
    path.write_text(
        "step5:\n"
        "  image_material_target_fps: 15\n"
        "  video_material_duration_adjust: stretch\n"
        "  video_material_resize_method: crop\n"
        "  video_material_longer_than_audio_mode: compress\n",
        encoding="utf-8",
    )

    assert _load_yaml_overrides(path) == {"VIDEO_MATERIAL_LONGER_THAN_AUDIO_MODE": "compress"}
