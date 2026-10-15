import json
from pathlib import Path

from core.cli import ui_helpers
from core.infra.project_paths import ProjectPaths
from core.pipeline import scanner
from core.pipeline import steps
from core.config import VideoGenerationConfig
from importlib import import_module


run_auto_module = import_module("core.pipeline.run_auto")


def _write_script(project_dir: Path, segments: int = 2) -> ProjectPaths:
    paths = ProjectPaths(str(project_dir))
    paths.ensure_dirs_exist()
    script = {
        "actual_segments": segments,
        "total_length": 100,
        "segments": [{"index": idx, "content": f"segment {idx}"} for idx in range(1, segments + 1)],
    }
    Path(paths.script_json()).write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    Path(paths.mini_summary_json()).write_text(
        json.dumps({"summary": "用于测试的整体描述。"}, ensure_ascii=False),
        encoding="utf-8",
    )
    return paths


def test_run_step_2_writes_the_description_summary(monkeypatch, tmp_path: Path):
    paths = _write_script(tmp_path / "project", segments=2)
    Path(paths.raw_json()).write_text(
        json.dumps({"content": "完整原稿内容"}, ensure_ascii=False),
        encoding="utf-8",
    )
    captured = {}

    def fake_generate_description(server, model, base_url, content, max_chars):
        captured.update(
            server=server,
            model=model,
            base_url=base_url,
            content=content,
            max_chars=max_chars,
        )
        return {"summary": "统一的画面背景小结", "total_length": 10}

    monkeypatch.setattr(steps, "generate_description_summary", fake_generate_description)

    result = steps.run_step_2(
        "siliconflow",
        "summary-model",
        "https://api.example.test/v1",
        str(tmp_path / "project"),
    )

    assert result == {"success": True, "mini_summary_path": paths.mini_summary_json()}
    assert json.loads(Path(paths.mini_summary_json()).read_text(encoding="utf-8"))["summary"] == "统一的画面背景小结"
    assert captured == {
        "server": "siliconflow",
        "model": "summary-model",
        "base_url": "https://api.example.test/v1",
        "content": "完整原稿内容",
        "max_chars": 200,
    }


def test_run_step_3_generates_voice_after_swap(monkeypatch, tmp_path: Path):
    paths = _write_script(tmp_path / "project", segments=1)
    captured = {}

    def fake_synthesize(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        voice_path = Path(paths.voice) / "voice_1.wav"
        voice_path.write_bytes(b"voice")
        return {"audio_paths": [str(voice_path)], "missing_segments": []}

    monkeypatch.setattr(steps, "synthesize_voice_for_segments", fake_synthesize)
    monkeypatch.setattr(steps, "_ensure_opening_narration", lambda *args, **kwargs: None)

    result = steps.run_step_3(
        tts_server="bytedance",
        voice="voice-id",
        tts_model="tts-model",
        project_output_dir=str(tmp_path / "project"),
        opening_quote=False,
        target_segments=[1],
    )

    assert result["success"] is True
    assert result["audio_paths"] == [str(Path(paths.voice) / "voice_1.wav")]
    assert captured["args"][:5] == ("bytedance", "voice-id", "tts-model", json.loads(Path(paths.script_json()).read_text()), paths.voice)
    assert captured["kwargs"]["target_segments"] == [1]


def test_run_step_4_generates_visuals_after_swap(monkeypatch, tmp_path: Path):
    paths = _write_script(tmp_path / "project", segments=1)
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
        image_model="image-model",
        image_size="1280x720",
        image_style_preset="style01",
        project_output_dir=str(tmp_path / "project"),
        opening_quote=False,
        target_segments=[1],
        llm_model="some-llm",
        llm_server="siliconflow",
        llm_base_url="https://api.example.test/v1",
    )

    assert result["success"] is True
    assert result["image_paths"] == [str(Path(paths.images) / "segment_1.png")]
    assert captured["args"][:6] == (
        "doubao",
        "image-model",
        json.loads(Path(paths.script_json()).read_text()),
        "style01",
        "1280x720",
        paths.images,
    )
    assert captured["kwargs"]["target_segments"] == [1]
    assert captured["kwargs"]["llm_model"] == "some-llm"


def test_auto_mode_runs_voice_before_visual_after_swap(monkeypatch, tmp_path: Path):
    project_dir = tmp_path / "project"
    paths = _write_script(project_dir, segments=5)
    Path(paths.raw_json()).write_text(
        json.dumps(
            {
                "source_name": "source",
                "content": "x" * 100,
                "total_length": 100,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    order = []

    monkeypatch.setattr(
        run_auto_module,
        "_run_step_1",
        lambda *_args, **_kwargs: {"success": True, "project_output_dir": str(project_dir), "raw": {"total_length": 100}},
    )
    monkeypatch.setattr(
        run_auto_module,
        "_run_step_1_5",
        lambda *_args, **_kwargs: {
            "success": True,
            "script_data": json.loads(Path(paths.script_json()).read_text()),
            "script_path": paths.script_json(),
        },
    )
    monkeypatch.setattr(
        run_auto_module,
        "_run_step_2",
        lambda *_args, **_kwargs: {"success": True, "mini_summary_path": paths.mini_summary_json()},
    )

    def fake_step3(*_args, **_kwargs):
        order.append("step3-audio")
        return {"success": True, "audio_paths": [f"voice_{idx}.wav" for idx in range(1, 6)]}

    def fake_step4(*_args, **_kwargs):
        order.append("step4-visual")
        return {"success": True, "image_paths": [f"image_{idx}.png" for idx in range(1, 6)]}

    monkeypatch.setattr(run_auto_module, "_run_step_3", fake_step3)
    monkeypatch.setattr(run_auto_module, "_run_step_4", fake_step4)
    monkeypatch.setattr(run_auto_module, "_run_step_5", lambda *_args, **_kwargs: {"success": True, "final_video": paths.final_video()})
    monkeypatch.setattr(run_auto_module, "_run_cover_generation", lambda *_args, **_kwargs: {"success": True, "cover_paths": []})

    result = run_auto_module.run_auto(
        VideoGenerationConfig(
            input_file="input.pdf",
            output_dir=str(tmp_path),
            num_segments=5,
            llm_server_step2="siliconflow",
            llm_base_url_step2="https://example.test/v1",
            image_server="google",
            image_model="gemini-3.1-flash-image",
            image_size="1280x720",
            cover_image_server="google",
            cover_image_model="gemini-3.1-flash-image",
        )
    )

    assert result["success"] is True
    assert order == ["step3-audio", "step4-visual"]
    assert result["audio_files"] == [f"voice_{idx}.wav" for idx in range(1, 6)]
    assert result["images"] == [f"image_{idx}.png" for idx in range(1, 6)]


def test_scanner_maps_step3_to_audio_and_step4_to_visual_after_swap(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(scanner, "OPENING_QUOTE", False)
    paths = _write_script(tmp_path / "project", segments=1)

    Path(paths.voice, "voice_1.wav").write_bytes(b"voice")
    progress = scanner.detect_project_progress(str(tmp_path / "project"))
    assert progress["audio_ok"] is True
    assert progress["images_ok"] is False
    assert progress["current_step"] == 3
    assert progress["current_step_name"] == "3"

    Path(paths.images, "segment_1.mp4").write_bytes(b"video")
    progress = scanner.detect_project_progress(str(tmp_path / "project"))
    assert progress["images_ok"] is True
    assert progress["current_step"] == 4
    assert progress["current_step_name"] == "4"


def test_cli_specific_step_3_runs_voice_and_step_4_runs_visual(monkeypatch, tmp_path: Path):
    calls = []

    monkeypatch.setattr(ui_helpers, "_prompt_segment_generation_scope", lambda *_args, **_kwargs: {"mode": "full", "segments": []})
    monkeypatch.setattr(ui_helpers, "prompt_visual_mode_choice", lambda *_args, **_kwargs: "static_image")
    monkeypatch.setattr(ui_helpers, "prompt_image_style_choice", lambda *_args, **_kwargs: "style01")

    def fake_voice(*_args, **_kwargs):
        calls.append("voice")
        return {"success": True}

    def fake_visual(*_args, **_kwargs):
        calls.append("visual")
        return {"success": True}

    monkeypatch.setattr(steps, "run_step_3", fake_voice)
    monkeypatch.setattr(steps, "run_step_4", fake_visual)

    common_args = (
        str(tmp_path),
        "llm2",
        "model2",
        "base2",
        "llm3",
        "model3",
        "base3",
        "doubao",
        "image-model",
        "1280x720",
        "1280x720",
        "style01",
        "bytedance",
        "voice-id",
        "tts-model",
        0,
        0,
        "neutral",
        4,
        1,
        True,
        None,
        "1280x720",
        "doubao",
        "cover-model",
        "style01",
        1,
        False,
        400,
        200,
        100,
    )

    assert ui_helpers._run_specific_step(3, *common_args)["success"] is True
    assert ui_helpers._run_specific_step(4, *common_args)["success"] is True
    assert calls == ["voice", "visual"]
