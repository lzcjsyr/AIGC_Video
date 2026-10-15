import os
from pathlib import Path

import pytest


class _FakeVideo:
    def __init__(self, width=1920, height=1080, duration=10.0, fail_first=False, fail_all=False):
        self.w = width
        self.h = height
        self.duration = duration
        self.fail_first = fail_first
        self.fail_all = fail_all
        self.calls = []

    def write_videofile(self, output_path, **kwargs):
        self.calls.append({"output_path": output_path, **kwargs})
        Path(output_path).write_bytes(b"partial")
        if self.fail_all or (self.fail_first and len(self.calls) == 1):
            raise RuntimeError("hardware unavailable")
        Path(output_path).write_bytes(b"video")


def test_export_video_uses_h264_hardware_fixed_bitrate_with_fade_filter(monkeypatch, tmp_path):
    from core.infra.media.exporter import export_video

    monkeypatch.setattr(os, "cpu_count", lambda: 8)
    video = _FakeVideo(width=1920, height=1080, duration=12.0)

    export_video(
        video,
        str(tmp_path / "final.mp4"),
        fps=30,
        video_codec="h264",
        bitrate_mode="auto",
        quality_level=65,
        fade_in_seconds=0.5,
        ending_fade_seconds=2.0,
    )

    assert len(video.calls) == 1
    call = video.calls[0]
    assert call["codec"] == "h264_videotoolbox"
    assert call["audio_codec"] == "aac"
    assert call["audio_bitrate"] == "256k"
    assert call["bitrate"] == "8M"
    assert call["threads"] == 8
    assert call["logger"] == "bar"
    assert call["ffmpeg_params"] == [
        "-nostdin",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-vf", "fade=t=in:st=0:d=0.5,fade=t=out:st=10.0:d=2.0",
        "-profile:v", "main",
        "-level", "4.1",
        "-maxrate", "8M",
        "-bufsize", "12M",
    ]


def test_export_video_uses_hevc_hardware_quality_mode_without_h264_profile(monkeypatch, tmp_path):
    from core.infra.media.exporter import export_video

    monkeypatch.setattr(os, "cpu_count", lambda: None)
    video = _FakeVideo(width=3840, height=2160, duration=6.0)

    export_video(
        video,
        str(tmp_path / "final.mp4"),
        fps=15,
        video_codec="hevc",
        bitrate_mode="quality",
        quality_level=72,
        fade_in_seconds=0.0,
        ending_fade_seconds=0.0,
    )

    call = video.calls[0]
    assert call["codec"] == "hevc_videotoolbox"
    assert call["bitrate"] is None
    assert call["threads"] == 4
    assert call["ffmpeg_params"] == [
        "-tag:v", "hvc1",
        "-nostdin",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-q:v", "72",
    ]


def test_export_video_falls_back_to_libx264_when_hardware_export_fails(monkeypatch, tmp_path):
    from core.infra.media.exporter import export_video

    monkeypatch.setattr(os, "cpu_count", lambda: 6)
    video = _FakeVideo(width=1280, height=720, duration=8.0, fail_first=True)

    export_video(
        video,
        str(tmp_path / "final.mp4"),
        fps=15,
        video_codec="h264",
        bitrate_mode="auto",
        quality_level=65,
        fade_in_seconds=0.0,
        ending_fade_seconds=2.5,
    )

    assert len(video.calls) == 2
    fallback = video.calls[1]
    assert fallback["codec"] == "libx264"
    assert fallback["audio_codec"] == "aac"
    assert fallback["audio_bitrate"] == "256k"
    assert fallback["preset"] == "medium"
    assert fallback["threads"] == 6
    assert fallback["ffmpeg_params"] == [
        "-nostdin",
        "-crf", "25",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-vf", "fade=t=out:st=5.5:d=2.5",
    ]


def test_export_video_moves_the_finished_video_into_place(tmp_path):
    from core.infra.media.exporter import export_video

    destination = tmp_path / "final_video.mp4"
    video = _FakeVideo(width=1280, height=720)

    export_video(video, str(destination))

    assert destination.read_bytes() == b"video"
    assert video.calls[0]["output_path"] != str(destination)
    assert video.calls[0]["temp_audiofile"].startswith(str(tmp_path))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["final_video.mp4"]


def test_interrupted_export_keeps_the_previous_video(tmp_path):
    from core.infra.media.exporter import export_video

    destination = tmp_path / "final_video.mp4"
    destination.write_bytes(b"previous")
    video = _FakeVideo(width=1280, height=720, fail_all=True)

    with pytest.raises(RuntimeError):
        export_video(video, str(destination))

    assert destination.read_bytes() == b"previous"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["final_video.mp4"]
