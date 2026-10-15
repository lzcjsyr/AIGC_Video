import json
from pathlib import Path
from types import SimpleNamespace

from core.config import config
from core.pipeline import steps


def test_run_step_5_skips_duplicate_opening_text_for_video_asset(monkeypatch, tmp_path: Path):
    project = tmp_path / "project"
    text_dir = project / "text"
    images_dir = project / "images"
    voice_dir = project / "voice"
    text_dir.mkdir(parents=True)
    images_dir.mkdir()
    voice_dir.mkdir()

    script = {
        "segments": [{"content": "segment 1"}],
        "actual_segments": 1,
        "golden_quotes": ["真正拉开差距的，不是努力，而是系统。"],
        "source_name": "系统思维",
    }
    (text_dir / "script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    (images_dir / "segment_1.png").write_bytes(b"segment-image")
    (images_dir / "opening.mp4").write_bytes(b"opening-video")
    (voice_dir / "voice_1.mp3").write_bytes(b"segment-audio")
    (voice_dir / "opening.mp3").write_bytes(b"opening-audio")

    captured = {}

    class FakeComposer:
        def compose_video(self, image_paths, audio_paths, output_path, **kwargs):
            captured["kwargs"] = kwargs
            Path(output_path).write_bytes(b"final-video")
            return output_path

    monkeypatch.setattr(steps, "_get_project_root", lambda: str(tmp_path))
    monkeypatch.setattr(steps, "_resolve_bgm_audio_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(steps, "_ensure_opening_narration", lambda *args, **kwargs: str(voice_dir / "opening.mp3"))
    monkeypatch.setattr(steps, "VideoComposer", FakeComposer)

    result = steps.run_step_5(
        project_output_dir=str(project),
        image_size="1280x720",
        enable_subtitles=False,
        bgm_filename=None,
        voice="voice-id",
        tts_model="tts-model",
        opening_quote=True,
    )

    assert result["success"] is True
    assert captured["kwargs"]["opening_image_path"].endswith("opening.mp4")
    assert "opening_golden_quote" not in captured["kwargs"]


def test_compose_video_uses_configured_output_fps(monkeypatch, tmp_path: Path):
    from core.domain.composer import VideoComposer

    composer = VideoComposer()
    captured = {}

    monkeypatch.setattr(composer, "_parse_image_size", lambda _size: (1280, 720))
    monkeypatch.setattr(composer, "_create_opening_segment", lambda *args, **kwargs: 0.0)
    monkeypatch.setattr(composer, "_create_main_segments", lambda *args, **kwargs: None)
    monkeypatch.setattr(composer, "_adjust_narration_volume", lambda clip, _volume: clip)
    monkeypatch.setattr(composer, "_add_visual_effects", lambda clip, _paths, _size: clip)
    monkeypatch.setattr(composer, "_add_background_music", lambda clip, _bgm, _volume, _root, *args, **kwargs: clip)
    monkeypatch.setattr(composer, "_cleanup_resources", lambda *args, **kwargs: None)
    monkeypatch.setattr(composer, "_has_video_materials", lambda _paths: False)
    monkeypatch.setattr(composer, "resolve_subtitle_font", lambda *_args: ("/fonts/cjk.ttc", 2))

    class _FakeFinalVideo:
        duration = 1.0
        w = 1280
        h = 720

    monkeypatch.setattr(
        "core.domain.composer.concatenate_videoclips",
        lambda clips, method="compose", padding=0: _FakeFinalVideo(),
    )

    def fake_export(final_video, output_path, fps):
        captured["fps"] = fps
        Path(output_path).write_bytes(b"final-video")

    def fake_export_three_by_four(source_path, output_path, script_data, **kwargs):
        captured["three_by_four"] = {
            "source_path": source_path,
            "output_path": output_path,
            "script_data": script_data,
            "kwargs": kwargs,
        }
        Path(output_path).write_bytes(b"three-by-four-video")
        return Path(output_path)

    monkeypatch.setattr(composer, "_export_video", fake_export)
    monkeypatch.setattr("core.domain.composer.export_three_by_four_video", fake_export_three_by_four)
    monkeypatch.setattr(config, "VIDEO_OUTPUT_FPS", 30)

    output_path = tmp_path / "final_video.mp4"
    result = composer.compose_video(
        image_paths=["segment_1.png"],
        audio_paths=["voice_1.mp3"],
        output_path=str(output_path),
        script_data={"cover_titles": ["主标题"], "cover_subtitles": ["副标题"]},
        image_size="1280x720",
        opening_quote=False,
    )

    assert result == str(output_path)
    assert captured["fps"] == 30
    assert captured["three_by_four"]["source_path"] == str(output_path)
    assert captured["three_by_four"]["output_path"] == tmp_path / "final_video_3x4.mp4"
    assert captured["three_by_four"]["script_data"]["cover_titles"] == ["主标题"]
    assert captured["three_by_four"]["kwargs"]["font_path"] == "/fonts/cjk.ttc"
    assert captured["three_by_four"]["kwargs"]["font_ttc_index"] == 2


def test_apply_audio_effects_respects_ducking_enabled_switch(monkeypatch):
    from core.domain.composer import VideoComposer

    composer = VideoComposer()
    bgm_clip = object()
    final_video = object()
    captured = {"called": 0}

    def fake_apply_ducking_effect(_bgm_clip, _final_video):
        captured["called"] += 1
        return "ducked-bgm"

    monkeypatch.setattr(composer, "_apply_ducking_effect", fake_apply_ducking_effect)

    monkeypatch.setattr(config, "AUDIO_DUCKING_ENABLED", False)
    result_disabled = composer._apply_audio_effects(bgm_clip, final_video)

    monkeypatch.setattr(config, "AUDIO_DUCKING_ENABLED", True)
    result_enabled = composer._apply_audio_effects(bgm_clip, final_video)

    assert result_disabled is bgm_clip
    assert result_enabled == "ducked-bgm"
    assert captured["called"] == 1


def test_bgm_loudness_fallback_uses_project_root_when_analysis_json_missing(monkeypatch, tmp_path: Path):
    from core.domain.composer import VideoComposer

    bgm_path = tmp_path / "bgm.mp3"
    bgm_path.write_bytes(b"fake audio")
    composer = VideoComposer()
    calls = []

    monkeypatch.setattr(config, "BGM_NORMALIZE_LOUDNESS", True)
    monkeypatch.setattr("core.infra.media.ffmpeg.shutil.which", lambda _name: "/usr/bin/ffmpeg")

    def fake_run(command, **_kwargs):
        calls.append(command)
        if len(calls) == 1:
            return SimpleNamespace(stderr="no loudnorm json here")
        return SimpleNamespace(stderr="")

    monkeypatch.setattr("core.infra.media.ffmpeg.subprocess.run", fake_run)

    result = composer._normalize_bgm_loudness(str(bgm_path), str(tmp_path))

    expected_path = str(tmp_path / "bgm_normalized.wav")
    assert result == expected_path
    assert calls[1][-1] == expected_path
