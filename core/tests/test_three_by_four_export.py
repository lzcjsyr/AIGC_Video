import json
import io
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from core.infra.media import three_by_four
from core.infra.media.three_by_four import (
    build_export_command,
    calculate_layout,
    derive_output_path,
    export_three_by_four_video,
    select_cover_copy,
)


def _probe(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height,avg_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("source", "canvas_height", "panel_height"),
    [
        ((1280, 720), 1708, 494),
        ((1920, 1080), 2560, 740),
        ((2560, 1440), 3412, 986),
    ],
)
def test_layout_expands_canvas_without_resizing_source(source, canvas_height, panel_height):
    layout = calculate_layout(*source)

    assert layout.canvas_width == source[0]
    assert layout.canvas_height == canvas_height
    assert layout.top_panel_height == panel_height
    assert layout.bottom_panel_height == panel_height
    assert layout.main_x == 0
    assert layout.main_y == panel_height
    assert layout.main_width == source[0]
    assert layout.main_height == source[1]


@pytest.mark.parametrize("source", [(0, 720), (1280, 0), (720, 1280), (1080, 1080)])
def test_layout_rejects_non_landscape_or_invalid_sources(source):
    with pytest.raises(ValueError):
        calculate_layout(*source)


def test_cover_copy_uses_first_nonempty_cover_title_and_subtitle():
    title, subtitle = select_cover_copy(
        {
            "cover_titles": [" ", "第一标题", "第二标题"],
            "cover_subtitles": [None, "第一副标题"],
            "video_titles": ["不应使用"],
        }
    )

    assert title == "第一标题"
    assert subtitle == "第一副标题"


def test_cover_copy_has_stable_fallbacks_for_incomplete_legacy_scripts():
    assert select_cover_copy({"video_titles": ["视频标题"], "source_name": "来源"}) == (
        "视频标题",
        "",
    )
    assert select_cover_copy({"source_name": "来源"}) == ("来源", "")


def test_output_path_is_derived_without_another_size_setting(tmp_path: Path):
    source = tmp_path / "final_video.mp4"
    assert derive_output_path(source) == tmp_path / "final_video_3x4.mp4"


def test_ffmpeg_command_overlays_source_at_native_size_and_copies_audio(tmp_path: Path):
    layout = calculate_layout(1280, 720)
    command = build_export_command(
        ffmpeg_path="/usr/bin/ffmpeg",
        source_path=tmp_path / "source.mp4",
        background_path=tmp_path / "background.png",
        output_path=tmp_path / "output.mp4",
        layout=layout,
        video_codec="h264",
        quality_level=70,
    )
    command_text = " ".join(str(item) for item in command)

    assert "pad=1280:1708:0:494" in command_text
    assert "overlay=0:0:shortest=1" in command_text
    assert "scale=" not in command_text
    assert "-c:a copy" in command_text
    assert "-c:v libx264" in command_text
    assert "-crf 16" in command_text
    assert "-progress pipe:1" in command_text
    assert "-nostats" in command_text
    assert "-shortest" not in command


@pytest.mark.parametrize(
    ("line", "seconds"),
    [
        ("out_time=00:00:12.500000", 12.5),
        ("out_time_us=62500000", 62.5),
        ("out_time_ms=2500000", 2.5),
        ("frame=42", None),
    ],
)
def test_ffmpeg_progress_parser_understands_supported_time_fields(line, seconds):
    assert three_by_four._parse_progress_seconds(line) == seconds


def test_cli_progress_bar_is_visible_and_finishes_at_100_percent():
    stream = io.StringIO()
    progress = three_by_four._CliProgressBar(10.0, stream=stream, width=10)

    progress.update(2.5)
    progress.finish()

    output = stream.getvalue()
    assert "生成3:4贴片版" in output
    assert "25%" in output
    assert "100%" in output
    assert output.endswith("\n")


def test_default_style_is_ink_with_a_restrained_vermilion_accent():
    options = three_by_four.PanelOptions()
    assert options.theme == "ink"
    assert options.accent == (196, 90, 71)
    assert options.bottom_content == "quote"
    # Ink panels are near-black and get lighter towards the video.
    assert max(options.palette.outer[:3]) < 20
    assert sum(options.palette.inner[:3]) > sum(options.palette.outer[:3])


def test_title_and_subtitle_are_drawn_in_the_top_panel_only(monkeypatch, tmp_path):
    layout = calculate_layout(1280, 720)
    calls = []
    original = three_by_four._draw_tracked_line

    def capture(draw, text, x, y, *args):
        calls.append((text, y))
        original(draw, text, x, y, *args)

    monkeypatch.setattr(three_by_four, "_draw_tracked_line", capture)
    three_by_four._render_static_background(
        tmp_path / "panels.png", layout, "主标题", "副标题", font_path=None, font_ttc_index=0,
    )

    assert [text for text, _y in calls] == ["主标题", "副标题"]
    assert all(y < layout.top_panel_height for _text, y in calls)


def test_bottom_panel_without_a_quote_shows_a_crisp_ornament(tmp_path):
    layout = calculate_layout(1280, 720)
    output = tmp_path / "panels.png"
    three_by_four._render_static_background(output, layout, "主标题", "副标题", font_path=None, font_ttc_index=0)

    bottom_y = layout.main_y + layout.main_height
    centre_y = bottom_y + int(layout.bottom_panel_height * 0.47)
    with Image.open(output).convert("RGB") as image:
        corner = image.getpixel((20, layout.canvas_height - 20))
        diamond = image.getpixel((layout.canvas_width // 2, centre_y))
        beside = image.getpixel((layout.canvas_width // 2, centre_y + 40))

    assert max(corner) < 30
    assert diamond[0] > 150 and diamond[0] > diamond[2] + 60
    assert max(beside) < 45


def test_quote_breaks_at_a_phrase_and_never_starts_a_line_with_punctuation():
    from PIL import ImageDraw

    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font = three_by_four._load_font(None, 40, 0)
    width = three_by_four._tracked_width(draw, "故事由谁来讲，谁就决定了谁是怪物。", font, 0)
    lines = three_by_four._balanced_lines(draw, "故事由谁来讲，谁就决定了谁是怪物。", font, 0, int(width * 0.7), max_lines=3)

    assert lines == ["故事由谁来讲，", "谁就决定了谁是怪物。"]
    lines = three_by_four._balanced_lines(draw, "甲乙丙丁戊己庚辛壬癸。子丑寅卯", font, 0, int(width * 0.35), max_lines=3)
    assert all(line[0] not in three_by_four._NO_LINE_START for line in lines)


def test_hardware_command_reuses_existing_codec_and_quality_setting(tmp_path: Path):
    command = build_export_command(
        ffmpeg_path="/usr/bin/ffmpeg",
        source_path=tmp_path / "source.mp4",
        background_path=tmp_path / "background.png",
        output_path=tmp_path / "output.mp4",
        layout=calculate_layout(1280, 720),
        video_codec="hevc",
        quality_level=70,
        hardware=True,
    )
    command_text = " ".join(str(item) for item in command)

    assert "-c:v hevc_videotoolbox" in command_text
    assert "-q:v 70" in command_text
    assert "-tag:v hvc1" in command_text


def test_export_prefers_hardware_encoder_and_falls_back_to_software_without_touching_the_master(
    monkeypatch, tmp_path: Path
):
    source = tmp_path / "final_video.mp4"
    destination = tmp_path / "final_video_3x4.mp4"
    source.write_bytes(b"landscape-master")
    commands = []

    monkeypatch.setattr(three_by_four.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        three_by_four,
        "_probe_video_metadata",
        lambda *_args: three_by_four._VideoMetadata(1280, 720, 10.0),
    )
    monkeypatch.setattr(
        three_by_four,
        "_render_static_background",
        lambda output_path, *_args, **_kwargs: output_path.write_bytes(b"background"),
    )

    def fake_run(command, *_args, **_kwargs):
        commands.append(command)
        if len(commands) == 1:
            raise subprocess.CalledProcessError(1, command, stderr="hardware unavailable")
        Path(command[-1]).write_bytes(b"framed-video")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(three_by_four, "_run_export_command", fake_run)

    result = export_three_by_four_video(source, destination, {})

    assert result == destination
    assert source.read_bytes() == b"landscape-master"
    assert destination.read_bytes() == b"framed-video"
    assert "h264_videotoolbox" in commands[0]
    assert commands[0][commands[0].index("-q:v") + 1] == "86"
    assert "libx264" in commands[1]


def test_failed_export_is_atomic_and_preserves_an_existing_variant(monkeypatch, tmp_path: Path):
    source = tmp_path / "final_video.mp4"
    destination = tmp_path / "final_video_3x4.mp4"
    source.write_bytes(b"landscape-master")
    destination.write_bytes(b"previous-good-variant")

    monkeypatch.setattr(three_by_four.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        three_by_four,
        "_probe_video_metadata",
        lambda *_args: three_by_four._VideoMetadata(1280, 720, 10.0),
    )
    monkeypatch.setattr(
        three_by_four,
        "_render_static_background",
        lambda output_path, *_args, **_kwargs: output_path.write_bytes(b"background"),
    )

    def always_fail(command, *_args, **_kwargs):
        Path(command[-1]).write_bytes(b"partial")
        raise subprocess.CalledProcessError(1, command, stderr="encoder failed")

    monkeypatch.setattr(three_by_four, "_run_export_command", always_fail)

    with pytest.raises(RuntimeError, match="硬件编码.*软件编码"):
        export_three_by_four_video(source, destination, {})

    assert source.read_bytes() == b"landscape-master"
    assert destination.read_bytes() == b"previous-good-variant"
    assert not (tmp_path / ".final_video_3x4.tmp.mp4").exists()


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg is required for the real media smoke test",
)
def test_short_real_video_keeps_native_main_frame_and_adds_symmetric_panels(
    tmp_path: Path, capsys
):
    source = tmp_path / "short.mp4"
    output = tmp_path / "short_3x4.mp4"
    frame = tmp_path / "frame.png"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=320x180:r=10:d=0.6",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=0.6",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
    )

    result = export_three_by_four_video(
        source,
        output,
        {"cover_titles": ["TITLE"], "cover_subtitles": ["SUBTITLE"]},
        video_codec="h264",
        quality_level=70,
    )
    progress_output = capsys.readouterr().out

    assert result == output
    assert "生成3:4贴片版" in progress_output
    assert "100%" in progress_output
    streams = _probe(output)["streams"]
    video_stream = next(stream for stream in streams if stream["codec_type"] == "video")
    assert (video_stream["width"], video_stream["height"]) == (320, 428)
    assert video_stream["avg_frame_rate"] == "10/1"
    assert any(stream["codec_type"] == "audio" for stream in streams)

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "0.2",
            "-i",
            str(output),
            "-frames:v",
            "1",
            str(frame),
        ],
        check=True,
    )
    with Image.open(frame) as image:
        # The source remains 320x180 at y=124; the sampled centre stays red.
        centre = image.getpixel((160, 214))
        top_panel = image.getpixel((10, 10))
        bottom_panel = image.getpixel((10, 418))

    assert centre[0] > 220 and centre[1] < 40 and centre[2] < 40
    assert top_panel[2] > top_panel[0]
    assert bottom_panel[2] > bottom_panel[0]


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg is required for the real media quality test",
)
def test_short_silent_video_preserves_frame_rate_and_visual_quality(tmp_path: Path):
    source = tmp_path / "quality-source.mp4"
    output = tmp_path / "quality-source_3x4.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=12:duration=0.6",
            "-c:v",
            "libx264",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
    )

    export_three_by_four_video(
        source,
        output,
        {"cover_titles": ["TITLE"], "cover_subtitles": ["SUBTITLE"]},
        video_codec="h264",
        quality_level=70,
    )

    streams = _probe(output)["streams"]
    video_stream = next(stream for stream in streams if stream["codec_type"] == "video")
    assert video_stream["avg_frame_rate"] == "12/1"
    assert not any(stream["codec_type"] == "audio" for stream in streams)

    comparison = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(source),
            "-i",
            str(output),
            "-lavfi",
            "[1:v]crop=320:180:0:124[centre];[0:v][centre]ssim",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"All:([0-9.]+)", comparison.stderr)
    assert match is not None
    assert float(match.group(1)) >= 0.98


def test_video_position_moves_the_main_picture_and_keeps_panels_even():
    higher = calculate_layout(1280, 720, 0.25)
    lower = calculate_layout(1280, 720, 0.75)

    assert higher.canvas_height == lower.canvas_height == 1708
    assert higher.main_y < 494 < lower.main_y
    for layout in (higher, lower):
        assert layout.top_panel_height % 2 == 0
        assert layout.bottom_panel_height % 2 == 0
        assert layout.top_panel_height + layout.main_height + layout.bottom_panel_height == layout.canvas_height


def test_panel_options_fall_back_to_defaults_for_unknown_values():
    options = three_by_four.PanelOptions.from_mapping(
        {"theme": "neon", "top_share": "x", "top_content": "TITLE", "bottom_content": None, "accent_color": "red"}
    )

    assert options.theme == "ink"
    assert options.top_share == 0.5
    assert options.top_content == "title"
    assert options.bottom_content == "quote"
    assert options.accent == three_by_four._ACCENT_COLOR
    assert three_by_four.PanelOptions.from_mapping({"top_share": 3}).top_share == 0.85


def test_panel_copy_follows_overrides_and_content_choices():
    script = {"cover_titles": ["封面标题"], "cover_subtitles": ["封面副标题"], "golden_quotes": ["", "第一句\n第二句"]}
    options = three_by_four.PanelOptions

    assert three_by_four.select_panel_copy(script, options()) == ("封面标题", "封面副标题", "第一句\n第二句")
    assert three_by_four.select_panel_copy(script, options(bottom_content="ornament")) == ("封面标题", "封面副标题", "")
    assert three_by_four.select_panel_copy(script, options(title_text="自定义", top_content="title")) == ("自定义", "", "第一句\n第二句")
    assert three_by_four.select_panel_copy(script, options(top_content="none", bottom_content="quote")) == ("", "", "第一句\n第二句")
    assert three_by_four.select_panel_copy(script, options(bottom_content="text", bottom_text="关注我")) == (
        "封面标题",
        "封面副标题",
        "关注我",
    )


def test_blurred_theme_fills_panels_from_the_video_without_scaling_the_main_picture(tmp_path: Path):
    layout = calculate_layout(1280, 720)
    command = build_export_command(
        ffmpeg_path="/usr/bin/ffmpeg",
        source_path=tmp_path / "source.mp4",
        background_path=tmp_path / "background.png",
        output_path=tmp_path / "output.mp4",
        layout=layout,
        video_codec="h264",
        quality_level=70,
        blurred_background=True,
    )
    graph = command[command.index("-filter_complex") + 1]

    assert "split=2[main][source]" in graph
    # Only the caption-free upper part of the frame feeds the blurred background.
    assert "[source]crop=iw:trunc(ih*0.68/2)*2:0:0,scale=1280:1708" in graph
    assert "boxblur" in graph
    assert "[blurred][main]overlay=0:494" in graph
    assert "[main]scale" not in graph


def test_paper_theme_and_bottom_text_are_drawn(monkeypatch, tmp_path):
    layout = calculate_layout(1280, 720)
    lines = []
    original = three_by_four._draw_tracked_line

    def capture(draw, text, *args):
        lines.append(text)
        original(draw, text, *args)

    monkeypatch.setattr(three_by_four, "_draw_tracked_line", capture)
    output = tmp_path / "panels.png"
    three_by_four._render_static_background(
        output,
        layout,
        "标题",
        "",
        font_path=None,
        font_ttc_index=0,
        panel=three_by_four.PanelOptions(theme="paper", bottom_content="text"),
        bottom_text="关注我，读更多好书",
    )

    assert "".join(lines) == "标题关注我，读更多好书"
    with Image.open(output).convert("RGB") as image:
        assert min(image.getpixel((20, 20))) > 190


def test_blurred_theme_leaves_panels_translucent(tmp_path):
    layout = calculate_layout(1280, 720)
    output = tmp_path / "panels.png"
    three_by_four._render_static_background(
        output, layout, "", "", font_path=None, font_ttc_index=0,
        panel=three_by_four.PanelOptions(theme="blur", top_content="none", bottom_content="none"),
    )
    with Image.open(output) as image:
        alpha = image.getpixel((20, 20))[3]

    assert 0 < alpha < 255


def test_layout_preview_places_the_frame_inside_the_panels(tmp_path):
    frame = tmp_path / "frame.png"
    Image.new("RGB", (321, 180), (220, 20, 20)).save(frame)
    output = three_by_four.render_layout_preview(
        frame, tmp_path / "preview.png", {"cover_titles": ["T"]}, panel={"top_share": 0.3}
    )

    with Image.open(output) as image:
        layout = calculate_layout(320, 180, 0.3)
        assert image.size == (layout.canvas_width, layout.canvas_height)
        assert image.getpixel((160, layout.main_y + 90))[0] > 200
        assert max(image.getpixel((5, 5))) < 30
