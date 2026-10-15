import json
import wave
from pathlib import Path

from core.config import get_generation_params
from core.cli import ui_helpers
from core.infra.project_paths import ProjectPaths
from core.pipeline import steps


def _write_project(project_dir: Path, *, with_voice: bool = True) -> ProjectPaths:
    paths = ProjectPaths(str(project_dir))
    paths.ensure_dirs_exist()
    script = {
        "actual_segments": 2,
        "segments": [
            {"index": 1, "content": "第一段口播", "title": "第一段"},
            {"index": 2, "content": "第二段口播", "title": "第二段"},
        ],
    }
    Path(paths.script_json()).write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    Path(paths.mini_summary_json()).write_text(
        json.dumps({"summary": "增长与风险并存的商业分析。"}, ensure_ascii=False),
        encoding="utf-8",
    )
    if with_voice:
        _write_wav(Path(paths.voice) / "voice_1.wav", seconds=0.25)
        _write_wav(Path(paths.voice) / "voice_2.wav", seconds=0.5)
    return paths


def _write_wav(path: Path, *, seconds: float) -> None:
    frame_rate = 8000
    frame_count = int(frame_rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(frame_rate)
        handle.writeframes(b"\x00\x00" * frame_count)


def test_generation_params_include_hyperframes_visual_mode(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
step4:
  visual_mode: motion_agent
  motion_style_preset: data_driven
  motion_max_turns: 12
  motion_render_fps: 60
  motion_concurrency: 2
""",
        encoding="utf-8",
    )

    params = get_generation_params(config_path)

    assert params["visual_mode"] == "motion_agent"
    assert params["motion_style_preset"] == "data_driven"
    assert params["motion_max_turns"] == 12
    assert params["motion_render_fps"] == 60
    assert params["motion_concurrency"] == 2


def test_generation_params_include_mixed_visual_mode(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
step4:
  visual_mode: mixed
""",
        encoding="utf-8",
    )

    params = get_generation_params(config_path)

    assert params["visual_mode"] == "mixed"


def test_prompt_visual_mode_choice_offers_mixed_mode(monkeypatch):
    captured = {}

    def fake_prompt_choice(message, options, default_index=0):
        captured["message"] = message
        captured["options"] = options
        captured["default_index"] = default_index
        return options[2]

    monkeypatch.setattr(ui_helpers, "prompt_choice", fake_prompt_choice)

    selected = ui_helpers.prompt_visual_mode_choice("mixed")

    assert selected == "mixed"
    assert any(option.startswith("mixed:") for option in captured["options"])
    assert captured["default_index"] == 2


def test_cli_step_4_mixed_mode_prompts_both_style_choices(monkeypatch, tmp_path):
    style_calls = []
    captured = {}

    monkeypatch.setattr(ui_helpers, "prompt_visual_mode_choice", lambda *_args, **_kwargs: "mixed")
    monkeypatch.setattr(
        ui_helpers,
        "prompt_image_style_choice",
        lambda *_args, **_kwargs: style_calls.append("image") or "style08",
    )
    monkeypatch.setattr(
        ui_helpers,
        "prompt_motion_style_choice",
        lambda *_args, **_kwargs: style_calls.append("hf") or "dark_premium",
    )
    monkeypatch.setattr(
        ui_helpers,
        "_prompt_segment_generation_scope",
        lambda *_args, **_kwargs: {"mode": "full", "segments": []},
    )

    def fake_run_step_4(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"success": True}

    monkeypatch.setattr(steps, "run_step_4", fake_run_step_4)

    result = ui_helpers._run_specific_step(
        target_step=4,
        project_output_dir=str(tmp_path),
        llm_server_step1_5="llm2",
        llm_model_step1_5="model2",
        llm_server_step2="base2",
        llm_model_step2="llm4",
        llm_base_url_step2="model4",
        llm_server_step4="base4",
        llm_model_step4="doubao",
        llm_base_url_step4="image-model",
        image_server="1280x720",
        image_model="1280x720",
        image_size="style01",
        video_size="1280x720",
        image_style_preset="bytedance",
        tts_server="tts-model",
        voice=0,
        tts_model=0,
        speech_rate="neutral",
        loudness_rate=4,
        emotion=2,
        emotion_scale=True,
        num_segments=None,
        enable_subtitles="1280x720",
        bgm_filename="doubao",
        cover_image_size="cover-model",
        cover_image_server="cover01",
        cover_image_model=1,
        cover_image_style=False,
        cover_image_count=400,
        opening_quote=True,
        mute_cut_threshold=200,
        mute_cut_min_silence_ms=100,
        mute_cut_remain_ms="static_image",
        visual_mode="mixed",
        motion_style_preset="dark_premium",  # Wait, let's keep it "data_driven" or let prompt choice override it
        motion_max_turns=20,
        motion_render_fps=30,
        motion_concurrency=1,
        image_prompt_template="pure_images",
    )

    assert result["success"] is True
    assert style_calls == ["image", "hf"]
    assert captured["args"][3] == "style08"
    assert captured["kwargs"]["visual_mode"] == "mixed"
    assert captured["kwargs"]["motion_style_preset"] == "dark_premium"
    assert captured["kwargs"]["image_prompt_template"] == "pure_images"


def test_cli_step_4_allows_zero_for_opening_video_even_when_opening_disabled(monkeypatch, tmp_path):
    captured_scope = {}
    captured_run = {}

    monkeypatch.setattr(ui_helpers, "prompt_visual_mode_choice", lambda *_args, **_kwargs: "static_image")
    monkeypatch.setattr(ui_helpers, "prompt_image_style_choice", lambda *_args, **_kwargs: "style07")

    def fake_scope(*args, **kwargs):
        captured_scope["kwargs"] = kwargs
        return {"mode": "partial", "segments": [], "regenerate_opening": True}

    def fake_run_step_4(*args, **kwargs):
        captured_run["args"] = args
        captured_run["kwargs"] = kwargs
        return {"success": True}

    monkeypatch.setattr(ui_helpers, "_prompt_segment_generation_scope", fake_scope)
    monkeypatch.setattr(steps, "run_step_4", fake_run_step_4)

    result = ui_helpers._run_specific_step(
        target_step=4,
        project_output_dir=str(tmp_path),
        llm_server_step1_5="llm2",
        llm_model_step1_5="model2",
        llm_server_step2="base2",
        llm_model_step2="llm4",
        llm_base_url_step2="model4",
        llm_server_step4="base4",
        llm_model_step4="doubao",
        llm_base_url_step4="image-model",
        image_server="1280x720",
        image_model="1280x720",
        image_size="style01",
        video_size="1280x720",
        image_style_preset="bytedance",
        tts_server="tts-model",
        voice=0,
        tts_model=0,
        speech_rate="neutral",
        loudness_rate=4,
        emotion=2,
        emotion_scale=True,
        num_segments=None,
        enable_subtitles="1280x720",
        bgm_filename="doubao",
        cover_image_size="cover-model",
        cover_image_server="cover01",
        cover_image_model=1,
        cover_image_style=False,
        cover_image_count=400,
        opening_quote=True,
        mute_cut_threshold=200,
        mute_cut_min_silence_ms=100,
        mute_cut_remain_ms="static_image",
        visual_mode="static_image",
        motion_style_preset="data_driven",
        motion_max_turns=20,
        motion_render_fps=30,
        motion_concurrency=1,
    )

    assert result["success"] is True
    assert captured_scope["kwargs"]["allow_opening"] is True
    assert captured_run["args"][5] is True
    assert captured_run["kwargs"]["target_segments"] == []
    assert captured_run["kwargs"]["regenerate_opening"] is True


def test_run_step_4_static_image_mode_keeps_existing_generator(monkeypatch, tmp_path):
    paths = _write_project(tmp_path / "project")
    captured = {}

    def fake_generate_images(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        image_path = Path(paths.images) / "segment_1.png"
        image_path.write_bytes(b"image")
        return {"image_paths": [str(image_path)], "failed_segments": [], "processed_segments": [1]}

    monkeypatch.setattr(steps, "generate_images_for_segments", fake_generate_images)
    monkeypatch.setattr(steps, "render_opening_video", lambda *args, **kwargs: None)

    result = steps.run_step_4(
        image_server="doubao",
        image_model="model",
        image_size="1280x720",
        image_style_preset="style01",
        project_output_dir=str(tmp_path / "project"),
        opening_quote=False,
        target_segments=[1],
        visual_mode="static_image",
    )

    assert result["success"] is True
    assert captured["args"][0] == "doubao"
    assert captured["kwargs"]["target_segments"] == [1]


def test_run_step_4_mixed_mode_dispatches_by_segment_visualizer(monkeypatch, tmp_path):
    paths = _write_project(tmp_path / "project")
    script_path = Path(paths.script_json())
    script = json.loads(script_path.read_text(encoding="utf-8"))
    script["segments"][0]["visualizer"] = "image"
    script["segments"][1]["visualizer"] = "hf"
    script_path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")

    captured = {"static_targets": None, "hyper_targets": None}

    def fake_generate_images(*args, **kwargs):
        captured["static_targets"] = kwargs["target_segments"]
        image_path = Path(paths.images) / "segment_1.png"
        image_path.write_bytes(b"image")
        return {"image_paths": [str(image_path), ""], "failed_segments": [], "processed_segments": [1]}

    def fake_hyperframes_renderer(**kwargs):
        captured["hyper_targets"] = kwargs["target_segments"]
        video_path = Path(paths.images) / "segment_2.mp4"
        video_path.write_bytes(b"video")
        return {"image_paths": ["", str(video_path)], "failed_segments": [], "processed_segments": [2]}

    monkeypatch.setattr(steps, "generate_images_for_segments", fake_generate_images)
    monkeypatch.setattr(steps, "render_motion_segments_with_agent", fake_hyperframes_renderer, raising=False)
    monkeypatch.setattr(steps, "render_opening_video", lambda *args, **kwargs: None)

    result = steps.run_step_4(
        image_server="doubao",
        image_model="model",
        image_size="1280x720",
        image_style_preset="style01",
        project_output_dir=str(tmp_path / "project"),
        opening_quote=False,
        visual_mode="mixed",
    )

    assert result["success"] is True
    assert captured["static_targets"] == [1]
    assert captured["hyper_targets"] == [2]
    assert result["image_paths"][0].endswith("segment_1.png")
    assert result["image_paths"][1].endswith("segment_2.mp4")
    assert result["processed_segments"] == [1, 2]


def test_run_step_4_hyperframes_mode_dispatches_to_renderer(monkeypatch, tmp_path):
    paths = _write_project(tmp_path / "project")
    captured = {}

    def fake_hyperframes_renderer(**kwargs):
        captured.update(kwargs)
        video_path = Path(paths.images) / "segment_2.mp4"
        video_path.write_bytes(b"video")
        return {"image_paths": ["", str(video_path)], "failed_segments": [], "processed_segments": [2]}

    monkeypatch.setattr(steps, "render_opening_video", lambda *args, **kwargs: None)
    monkeypatch.setattr(steps, "render_motion_segments_with_agent", fake_hyperframes_renderer, raising=False)

    result = steps.run_step_4(
        image_server="doubao",
        image_model="model",
        image_size="1280x720",
        image_style_preset="style01",
        project_output_dir=str(tmp_path / "project"),
        opening_quote=False,
        target_segments=[2],
        visual_mode="motion_agent",
        motion_style_preset="data_driven",
        motion_max_turns=9,
        motion_render_fps=60,
        motion_concurrency=1,
        llm_server="siliconflow",
        llm_model="step4-model",
        llm_base_url="https://llm-gateway.example.test/anthropic",
    )

    assert result["success"] is True
    assert result["image_paths"][1].endswith("segment_2.mp4")
    assert captured["target_segments"] == [2]
    assert captured["style_preset"] == "data_driven"
    assert captured["max_turns"] == 9
    assert captured["render_fps"] == 60
    assert captured["llm_server"] == "siliconflow"
    assert captured["llm_model"] == "step4-model"
    assert captured["llm_base_url"] == "https://llm-gateway.example.test/anthropic"


def test_run_step_4_hyperframes_mode_requires_step3_voice(tmp_path):
    _write_project(tmp_path / "project", with_voice=False)

    result = steps.run_step_4(
        image_server="doubao",
        image_model="model",
        image_size="1280x720",
        image_style_preset="style01",
        project_output_dir=str(tmp_path / "project"),
        opening_quote=False,
        visual_mode="motion_agent",
    )

    assert result["success"] is False
    assert result["failed_segments"] == [1, 2]
    assert "步骤3" in result["message"]


def test_legacy_yaml_options_migrate_without_requiring_a_framework(tmp_path):
    path = tmp_path / "legacy.yaml"
    path.write_text("step4:\n  visual_mode: hyperframes_agent\n  hyperframes_style_preset: dark_premium\n  hyperframes_render_fps: 60\n  motion_render_fps: 24\nhyperframes_opening:\n  ip_name: My channel\n")
    params = get_generation_params(path)
    assert params["visual_mode"] == "motion_agent"
    assert params["motion_style_preset"] == "dark_premium"
    assert params["motion_render_fps"] == 24
    assert not any(key.startswith("hyperframes_") for key in params)
