"""Create a 3:4 distribution copy around an existing landscape master.

The landscape video is the single source of truth. Its pixel dimensions are
never scaled; the 3:4 canvas and both static panels are derived from the
encoded master's actual dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence, TextIO

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


# Each role lists faces from the most to the least preferred; the first installed one is used.
_EDITORIAL_TITLE_FONTS = (
    (Path("/System/Library/Fonts/Supplemental/Songti.ttc"), 1),  # Songti SC Bold
    (Path("C:/Windows/Fonts/simsun.ttc"), 0),
    (Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"), 0),
    (Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"), 0),
)

_EDITORIAL_QUOTE_FONTS = (
    (Path("/System/Library/Fonts/Supplemental/Songti.ttc"), 6),  # Songti SC Regular
    (Path("C:/Windows/Fonts/simsun.ttc"), 0),
    (Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"), 0),
    (Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"), 0),
)

_EDITORIAL_SUBTITLE_FONTS = (
    (Path("/System/Library/Fonts/Hiragino Sans GB.ttc"), 0),  # W3
    (Path("/System/Library/Fonts/STHeiti Medium.ttc"), 1),
    (Path("C:/Windows/Fonts/msyh.ttc"), 0),
    (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), 0),
    (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"), 0),
)

_ACCENT_COLOR = (196, 90, 71)


@dataclass(frozen=True)
class _Palette:
    # Panels shade from the outer edge of the frame towards the video; alpha below 255 lets
    # the blurred picture show through.
    outer: tuple[int, int, int, int]
    inner: tuple[int, int, int, int]
    title: tuple[int, int, int]
    subtitle: tuple[int, int, int]
    # A faint line where a panel meets the video.
    edge: tuple[int, int, int, int]
    # Fine noise keeps the gradients from banding after encoding.
    grain: int
    shadow: bool = False


_PALETTES = {
    "ink": _Palette((10, 12, 16, 255), (24, 28, 35, 255), (244, 240, 232), (168, 162, 152), (255, 255, 255, 20), 2),
    "paper": _Palette((234, 227, 214, 255), (247, 243, 235, 255), (30, 26, 22), (112, 102, 90), (0, 0, 0, 30), 4),
    "blur": _Palette((0, 0, 0, 178), (0, 0, 0, 96), (250, 247, 241), (226, 220, 210), (255, 255, 255, 36), 0, True),
}
THEMES = tuple(_PALETTES)
TOP_CONTENTS = ("title_subtitle", "title", "none")
BOTTOM_CONTENTS = ("ornament", "quote", "text", "none")


# The blurred background is drawn from this upper share of the frame, above burned-in subtitles.
_BLUR_SOURCE_SHARE = 0.68


def _blur_radius(layout: "ThreeByFourLayout") -> int:
    return max(10, layout.canvas_width // 32)


@dataclass(frozen=True)
class PanelOptions:
    """3:4 上下贴片的样式与内容；默认值即原有的深色编辑部风格。"""

    theme: str = "ink"
    # 主画面上方留白占全部留白的比例：0.5 居中，越小主画面越靠上。
    top_share: float = 0.5
    top_content: str = "title_subtitle"
    # 留空时使用选中的封面标题与副标题。
    title_text: str = ""
    subtitle_text: str = ""
    # The opening quote; the ornament stands in when there is none.
    bottom_content: str = "quote"
    bottom_text: str = ""
    accent_color: str = "#C45A47"

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> "PanelOptions":
        """容错读取配置：未知取值回退到默认值，避免一项笔误让整次合成失败。"""
        data = values or {}
        default = cls()

        def choice(key: str, allowed: Sequence[str]) -> str:
            value = str(data.get(key) or getattr(default, key)).strip().lower()
            return value if value in allowed else getattr(default, key)

        try:
            share = float(data.get("top_share", default.top_share))
        except (TypeError, ValueError):
            share = default.top_share
        return cls(
            theme=choice("theme", THEMES),
            top_share=min(0.85, max(0.15, share)),
            top_content=choice("top_content", TOP_CONTENTS),
            title_text=_clean_text(data.get("title_text")),
            subtitle_text=_clean_text(data.get("subtitle_text")),
            bottom_content=choice("bottom_content", BOTTOM_CONTENTS),
            bottom_text=_clean_multiline(data.get("bottom_text")),
            accent_color=str(data.get("accent_color") or default.accent_color),
        )

    @property
    def palette(self) -> _Palette:
        return _PALETTES.get(self.theme, _PALETTES["ink"])

    @property
    def accent(self) -> tuple[int, int, int]:
        return _parse_hex_color(self.accent_color) or _ACCENT_COLOR


@dataclass(frozen=True)
class _VideoMetadata:
    width: int
    height: int
    duration: float


@dataclass(frozen=True)
class ThreeByFourLayout:
    canvas_width: int
    canvas_height: int
    top_panel_height: int
    bottom_panel_height: int
    main_x: int
    main_y: int
    main_width: int
    main_height: int


def calculate_layout(source_width: int, source_height: int, top_share: float = 0.5) -> ThreeByFourLayout:
    """Derive an encoder-safe 3:4 canvas while preserving the source rectangle."""
    width = int(source_width)
    height = int(source_height)
    if width <= 0 or height <= 0:
        raise ValueError("视频尺寸必须为正整数")
    if width <= height:
        raise ValueError("3:4贴片版只支持横屏主视频")
    if width % 2 or height % 2:
        raise ValueError("视频宽高必须为偶数，才能使用 yuv420p 编码")

    # A multiple of four keeps the canvas and both symmetric panels even,
    # while choosing the closest encoder-safe approximation to exact 3:4.
    canvas_height = max(height, int(round((width * 4 / 3) / 4)) * 4)
    remaining_height = canvas_height - height
    if remaining_height <= 0:
        raise ValueError("主视频高度超过了按宽度推导出的3:4画布")
    # Both panels stay even so the overlay offset suits 4:2:0 chroma.
    share = min(1.0, max(0.0, float(top_share)))
    panel_height = 2 * int(round(remaining_height * share / 2))
    panel_height = min(remaining_height, max(0, panel_height))

    return ThreeByFourLayout(
        canvas_width=width,
        canvas_height=canvas_height,
        top_panel_height=panel_height,
        bottom_panel_height=remaining_height - panel_height,
        main_x=0,
        main_y=panel_height,
        main_width=width,
        main_height=height,
    )


def select_panel_copy(
    script_data: Mapping[str, Any] | None, panel: PanelOptions
) -> tuple[str, str, str]:
    """The title, subtitle and bottom text the panels show, after the panel's choices."""
    title, subtitle = select_cover_copy(script_data)
    title = panel.title_text or title
    subtitle = panel.subtitle_text or subtitle
    if panel.top_content == "none":
        title = subtitle = ""
    elif panel.top_content == "title":
        subtitle = ""
    if panel.bottom_content == "quote":
        bottom = _first_multiline((script_data or {}).get("golden_quotes"))
    elif panel.bottom_content == "text":
        bottom = panel.bottom_text
    else:
        bottom = ""
    return title, subtitle, bottom


def select_cover_copy(script_data: Mapping[str, Any] | None) -> tuple[str, str]:
    """Select the first usable cover title/subtitle with legacy title fallback."""
    data = script_data or {}
    title = _first_text(data.get("cover_titles"))
    subtitle = _first_text(data.get("cover_subtitles"))
    if not title:
        title = _first_text(data.get("video_titles")) or _clean_text(data.get("source_name"))
    return title, subtitle


def derive_output_path(source_path: str | os.PathLike[str]) -> Path:
    source = Path(source_path)
    return source.with_name(f"{source.stem}_3x4{source.suffix or '.mp4'}")


def build_export_command(
    *,
    ffmpeg_path: str,
    source_path: str | os.PathLike[str],
    background_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    layout: ThreeByFourLayout,
    video_codec: str,
    quality_level: int,
    hardware: bool = False,
    blurred_background: bool = False,
) -> list[str]:
    """Build the post-processing command. The main picture is never scaled."""
    codec_args = _encoder_args(video_codec, quality_level, hardware=hardware)
    if blurred_background:
        # Only the background copy is scaled; the main picture keeps its native pixels.
        radius = _blur_radius(layout)
        filter_graph = (
            "[0:v]split=2[main][source];"
            # The upper part of the frame leaves burned-in subtitles out of the background.
            f"[source]crop=iw:trunc(ih*{_BLUR_SOURCE_SHARE}/2)*2:0:0,"
            f"scale={layout.canvas_width}:{layout.canvas_height}:force_original_aspect_ratio=increase,"
            f"crop={layout.canvas_width}:{layout.canvas_height},boxblur={radius}:3[blurred];"
            f"[blurred][main]overlay={layout.main_x}:{layout.main_y}[padded];"
            "[padded][1:v]overlay=0:0:shortest=1,"
            "format=yuv420p[video]"
        )
    else:
        filter_graph = (
            f"[0:v]pad={layout.canvas_width}:{layout.canvas_height}:"
            f"{layout.main_x}:{layout.main_y}:color=black[padded];"
            "[padded][1:v]overlay=0:0:shortest=1,"
            "format=yuv420p[video]"
        )
    return [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        str(source_path),
        "-loop",
        "1",
        "-i",
        str(background_path),
        "-filter_complex",
        filter_graph,
        "-map",
        "[video]",
        "-map",
        "0:a?",
        *codec_args,
        "-c:a",
        "copy",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output_path),
    ]


def export_three_by_four_video(
    source_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str] | None,
    script_data: Mapping[str, Any] | None,
    *,
    font_path: str | os.PathLike[str] | None = None,
    font_ttc_index: int = 0,
    video_codec: str = "h264",
    quality_level: int = 86,
    panel: PanelOptions | Mapping[str, Any] | None = None,
) -> Path:
    """Add static 3:4 panels to an already-rendered landscape master."""
    options = panel if isinstance(panel, PanelOptions) else PanelOptions.from_mapping(panel)
    source = Path(source_path)
    destination = Path(output_path) if output_path is not None else derive_output_path(source)
    if not source.is_file():
        raise FileNotFoundError(f"横屏母版不存在: {source}")
    if source.resolve() == destination.resolve():
        raise ValueError("3:4输出路径不能覆盖横屏母版")

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if not ffmpeg_path or not ffprobe_path:
        raise RuntimeError("生成3:4贴片版需要 FFmpeg 和 FFprobe")

    metadata = _probe_video_metadata(source, ffprobe_path)
    layout = calculate_layout(metadata.width, metadata.height, options.top_share)
    title, subtitle, bottom = select_panel_copy(script_data, options)
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary_output = destination.with_name(f".{destination.stem}.tmp{destination.suffix or '.mp4'}")
    with tempfile.TemporaryDirectory(prefix="aigc-video-3x4-") as temporary_dir:
        background_path = Path(temporary_dir) / "background.png"
        _render_static_background(
            background_path,
            layout,
            title,
            subtitle,
            font_path=Path(font_path) if font_path else None,
            font_ttc_index=int(font_ttc_index or 0),
            panel=options,
            bottom_text=bottom,
        )
        blurred = options.theme == "blur"
        hardware_command = build_export_command(
            ffmpeg_path=ffmpeg_path,
            source_path=source,
            background_path=background_path,
            output_path=temporary_output,
            layout=layout,
            video_codec=video_codec,
            quality_level=quality_level,
            hardware=True,
            blurred_background=blurred,
        )
        try:
            try:
                _run_export_command(
                    hardware_command,
                    metadata.duration,
                    label="生成3:4贴片版（硬件高质量编码）",
                )
            except subprocess.CalledProcessError as hardware_error:
                temporary_output.unlink(missing_ok=True)
                print("⚠️ 硬件编码不可用，切换软件高质量编码…")
                software_command = build_export_command(
                    ffmpeg_path=ffmpeg_path,
                    source_path=source,
                    background_path=background_path,
                    output_path=temporary_output,
                    layout=layout,
                    video_codec=video_codec,
                    quality_level=quality_level,
                    hardware=False,
                    blurred_background=blurred,
                )
                try:
                    _run_export_command(
                        software_command,
                        metadata.duration,
                        label="生成3:4贴片版（软件高质量编码）",
                    )
                except subprocess.CalledProcessError as software_error:
                    hardware_detail = _process_error_detail(hardware_error)
                    software_detail = _process_error_detail(software_error)
                    raise RuntimeError(
                        "3:4贴片版硬件编码和软件编码均失败: "
                        f"硬件编码: {hardware_detail}; 软件编码: {software_detail}"
                    ) from software_error

            if not temporary_output.is_file():
                raise RuntimeError("3:4贴片版编码完成但未生成输出文件")
            os.replace(temporary_output, destination)
        finally:
            temporary_output.unlink(missing_ok=True)

    return destination


def _probe_video_metadata(source_path: Path, ffprobe_path: str) -> _VideoMetadata:
    result = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height:format=duration",
            "-of",
            "json",
            str(source_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        return _VideoMetadata(
            width=int(stream["width"]),
            height=int(stream["height"]),
            duration=float(payload["format"]["duration"]),
        )
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"无法读取横屏母版尺寸: {source_path}") from exc


def render_layout_preview(
    frame_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    script_data: Mapping[str, Any] | None,
    *,
    panel: PanelOptions | Mapping[str, Any] | None = None,
    font_path: str | os.PathLike[str] | None = None,
    font_ttc_index: int = 0,
) -> Path:
    """A still of the 3:4 copy: one landscape frame inside the panels, as the export draws them."""
    options = panel if isinstance(panel, PanelOptions) else PanelOptions.from_mapping(panel)
    destination = Path(output_path)
    with Image.open(frame_path) as source:
        frame = source.convert("RGB")
    # The export needs even dimensions; a preview frame may come from any image.
    frame = frame.crop((0, 0, frame.width - frame.width % 2, frame.height - frame.height % 2))
    layout = calculate_layout(frame.width, frame.height, options.top_share)
    title, subtitle, bottom = select_panel_copy(script_data, options)
    canvas = Image.new("RGBA", (layout.canvas_width, layout.canvas_height), (0, 0, 0, 255))
    if options.theme == "blur":
        source = frame.crop((0, 0, frame.width, max(2, int(frame.height * _BLUR_SOURCE_SHARE) // 2 * 2)))
        scale = max(layout.canvas_width / source.width, layout.canvas_height / source.height)
        size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
        cover = source.resize(size, Image.Resampling.BILINEAR)
        left = (cover.width - layout.canvas_width) // 2
        top = (cover.height - layout.canvas_height) // 2
        cover = cover.crop((left, top, left + layout.canvas_width, top + layout.canvas_height))
        # Three box-blur passes approximate a Gaussian with this sigma.
        canvas.paste(cover.filter(ImageFilter.GaussianBlur(_blur_radius(layout) * 0.95)).convert("RGBA"))
    canvas.paste(frame.convert("RGBA"), (layout.main_x, layout.main_y))
    canvas.alpha_composite(
        _draw_panels(
            layout,
            title,
            subtitle,
            font_path=Path(font_path) if font_path else None,
            font_ttc_index=int(font_ttc_index or 0),
            panel=options,
            bottom_text=bottom,
        )
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(destination, format="PNG")
    return destination


def _render_static_background(
    output_path: Path,
    layout: ThreeByFourLayout,
    title: str,
    subtitle: str,
    *,
    font_path: Path | None,
    font_ttc_index: int,
    panel: PanelOptions | None = None,
    bottom_text: str = "",
) -> None:
    image = _draw_panels(
        layout,
        title,
        subtitle,
        font_path=font_path,
        font_ttc_index=font_ttc_index,
        panel=panel,
        bottom_text=bottom_text,
    )
    image.save(output_path, format="PNG", optimize=True)


def _draw_panels(
    layout: ThreeByFourLayout,
    title: str,
    subtitle: str,
    *,
    font_path: Path | None,
    font_ttc_index: int,
    panel: PanelOptions | None = None,
    bottom_text: str = "",
) -> Image.Image:
    """The panels as one transparent overlay: backgrounds, then the copy above and below the video."""
    options = panel or PanelOptions()
    palette = options.palette
    accent = options.accent
    fonts = {
        role: _resolve_editorial_font(candidates, font_path, font_ttc_index)
        for role, candidates in (
            ("title", _EDITORIAL_TITLE_FONTS),
            ("quote", _EDITORIAL_QUOTE_FONTS),
            ("sans", _EDITORIAL_SUBTITLE_FONTS),
        )
    }
    width = layout.canvas_width
    bottom_y = layout.main_y + layout.main_height
    image = Image.new("RGBA", (width, layout.canvas_height), (0, 0, 0, 0))
    if layout.top_panel_height:
        image.paste(_panel_fill(width, layout.top_panel_height, palette, towards_video="down"), (0, 0))
    if layout.bottom_panel_height:
        image.paste(_panel_fill(width, layout.bottom_panel_height, palette, towards_video="up"), (0, bottom_y))
    draw = ImageDraw.Draw(image)
    edge = max(1, width // 1280)
    if layout.top_panel_height > edge:
        draw.rectangle((0, layout.main_y - edge, width - 1, layout.main_y - 1), fill=palette.edge)
    if layout.bottom_panel_height > edge:
        draw.rectangle((0, bottom_y, width - 1, bottom_y + edge - 1), fill=palette.edge)

    text = Image.new("RGBA", image.size, (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text)
    # Too thin a panel cannot carry legible text.
    minimum = max(24, width // 40)
    if layout.top_panel_height >= minimum and (title or subtitle):
        _draw_top_copy(text_draw, layout, title, subtitle, palette=palette, accent=accent, fonts=fonts)
    if layout.bottom_panel_height >= minimum:
        if bottom_text and options.bottom_content in {"quote", "text"}:
            _draw_bottom_copy(text_draw, layout, bottom_text, quote=options.bottom_content == "quote",
                              palette=palette, accent=accent, fonts=fonts)
        elif options.bottom_content in {"ornament", "quote"}:
            _draw_bottom_ornament(text_draw, layout, palette=palette, accent=accent)
    if palette.shadow:
        # Over a moving picture the copy needs a soft shadow to stay legible.
        alpha = text.getchannel("A").filter(ImageFilter.GaussianBlur(max(2, width // 320)))
        shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        shadow.putalpha(alpha.point(lambda value: int(value * 0.55)))
        image.alpha_composite(shadow)
    image.alpha_composite(text)
    return image


def _panel_fill(width: int, height: int, palette: _Palette, *, towards_video: str) -> Image.Image:
    """A panel background: a vertical gradient from the frame's edge to the video, with fine grain."""
    rows = [
        tuple(round(o + (i - o) * (y / max(1, height - 1))) for o, i in zip(palette.outer, palette.inner))
        for y in range(height)
    ]
    if towards_video == "up":
        rows.reverse()
    column = Image.new("RGBA", (1, height))
    column.putdata(rows)
    fill = column.resize((width, height), Image.Resampling.NEAREST)
    if palette.grain:
        # Gaussian noise centred on 128; adding it with offset -128 shifts each pixel by a few levels.
        noise = Image.effect_noise((width, height), palette.grain)
        r, g, b, a = fill.split()
        r, g, b = (ImageChops.add(channel, noise, offset=-128) for channel in (r, g, b))
        fill = Image.merge("RGBA", (r, g, b, a))
    return fill


def _draw_top_copy(draw, layout: ThreeByFourLayout, title: str, subtitle: str, *, palette: _Palette,
                   accent: tuple[int, int, int], fonts) -> None:
    """The title (up to two balanced lines) over a subtitle set between two short accent rules."""
    width = layout.canvas_width
    panel_height = layout.top_panel_height
    max_width = int(width * 0.84)
    title_path, title_index = fonts["title"]
    sans_path, sans_index = fonts["sans"]

    sub_size = max(12, int(width * 0.034))
    sub_tracking = 0.16
    sub_font = _load_font(sans_path, sub_size, sans_index)
    rule_length = max(18, int(width * 0.05))
    rule_gap = max(8, int(width * 0.022))
    if subtitle:
        # The rules take room beside the subtitle; shrink it before letting it crowd them.
        while sub_size > 12 and _tracked_width(draw, subtitle, sub_font, int(sub_size * sub_tracking)) > max_width - 2 * (rule_length + rule_gap):
            sub_size -= 1
            sub_font = _load_font(sans_path, sub_size, sans_index)
    sub_height = int(sub_size * 1.3) if subtitle else 0
    gap = 0

    lines: list[str] = []
    size = 0
    line_height = 0
    if title:
        available = panel_height * 0.74 - sub_height
        for size in range(max(16, int(width * 0.082)), 13, -2):
            font = _load_font(title_path, size, title_index)
            tracking = int(size * 0.04)
            lines = _balanced_lines(draw, title, font, tracking, max_width, max_lines=2)
            line_height = int(size * 1.28)
            gap = int(size * 0.62) if subtitle else 0
            if len(lines) <= 2 and line_height * len(lines) + gap <= available:
                break
        title_font = _load_font(title_path, size, title_index)
        title_tracking = int(size * 0.04)

    block = line_height * len(lines) + gap + sub_height
    # Optically centred, a touch towards the video so the copy belongs to the picture.
    top = max(0, int(panel_height * 0.53 - block / 2))
    y = top
    for line in lines:
        _draw_centred_line(draw, line, y, line_height, width, title_font, title_tracking, palette.title)
        y += line_height
    y += gap
    if subtitle:
        tracking = int(sub_size * sub_tracking)
        text_width = _tracked_width(draw, subtitle, sub_font, tracking)
        _draw_centred_line(draw, subtitle, y, sub_height, width, sub_font, tracking, palette.subtitle)
        centre_y = y + sub_height // 2
        line_width = max(1, width // 900)
        for direction in (-1, 1):
            inner = width / 2 + direction * (text_width / 2 + rule_gap)
            outer = inner + direction * rule_length
            draw.line((min(inner, outer), centre_y, max(inner, outer), centre_y), fill=(*accent, 255), width=line_width)
    elif lines:
        # A title alone ends with a small accent mark.
        _draw_rule(draw, centre=(width // 2, int(y + line_height * 0.42)), half_width=max(16, int(width * 0.035)),
                   gap=max(6, int(width * 0.008)), line_width=max(1, width // 900), diamond=max(3, int(width * 0.0035)),
                   line_fill=(*accent, 255), diamond_fill=(*accent, 255))


def _draw_bottom_copy(draw, layout: ThreeByFourLayout, text: str, *, quote: bool, palette: _Palette,
                      accent: tuple[int, int, int], fonts) -> None:
    """The opening quote as a pull quote under a large accent quotation mark, or a custom line."""
    width = layout.canvas_width
    panel_height = layout.bottom_panel_height
    bottom_y = layout.main_y + layout.main_height
    max_width = int(width * (0.76 if quote else 0.8))
    path, index = fonts["quote" if quote else "sans"]
    mark_font = _load_font(fonts["title"][0], max(20, int(width * 0.125)), fonts["title"][1])
    # The mark's ink, not its em box: a quotation mark sits high in a mostly empty square.
    mark_bounds = draw.textbbox((0, 0), "\u201c", font=mark_font) if quote else (0, 0, 0, 0)
    mark_height = (mark_bounds[3] - mark_bounds[1]) + int(width * 0.01) if quote else 0
    available = panel_height * 0.78 - mark_height
    lines: list[str] = []
    size = line_height = tracking = 0
    for size in range(max(14, int(width * (0.056 if quote else 0.04))), 11, -2):
        font = _load_font(path, size, index)
        tracking = int(size * (0.06 if quote else 0.12))
        lines = _balanced_lines(draw, text, font, tracking, max_width, max_lines=3)
        line_height = int(size * 1.5)
        if line_height * len(lines) <= available:
            break
    font = _load_font(path, size, index)
    block = mark_height + line_height * len(lines)
    y = bottom_y + max(0, int(panel_height * 0.47 - block / 2))
    if quote:
        # A large opening mark in the accent colour, set in the serif.
        draw.text(((width - (mark_bounds[2] - mark_bounds[0])) / 2 - mark_bounds[0], y - mark_bounds[1]),
                  "\u201c", font=mark_font, fill=(*accent, 255))
    else:
        _draw_rule(draw, centre=(width // 2, y + mark_height // 2), half_width=max(16, int(width * 0.03)),
                   gap=max(6, int(width * 0.007)), line_width=max(1, width // 900), diamond=max(3, int(width * 0.003)),
                   line_fill=(*accent, 255), diamond_fill=(*accent, 255))
        y += max(10, int(size * 0.9))
    # The first line's half-leading would otherwise open a gap under the mark.
    y += mark_height - (int((line_height - size) / 2) if quote else 0)
    # Custom text sits between the title and subtitle in emphasis.
    color = palette.title if quote else tuple(round((t + u) / 2) for t, u in zip(palette.title, palette.subtitle))
    for line in lines:
        _draw_centred_line(draw, line, y, line_height, width, font, tracking, color)
        y += line_height


def _draw_bottom_ornament(draw, layout: ThreeByFourLayout, *, palette: _Palette, accent: tuple[int, int, int]) -> None:
    """A quiet close when the bottom panel has no copy: a hairline broken by an accent diamond."""
    width = layout.canvas_width
    centre_y = layout.main_y + layout.main_height + int(layout.bottom_panel_height * 0.47)
    faint = (*palette.subtitle, 110)
    _draw_rule(draw, centre=(width // 2, centre_y), half_width=max(30, int(width * 0.16)), gap=max(12, int(width * 0.018)),
               line_width=max(1, width // 1100), diamond=max(3, int(width * 0.0045)), line_fill=faint,
               diamond_fill=(*accent, 255))
    for direction in (-1, 1):
        x = width // 2 + direction * max(30, int(width * 0.16))
        r = max(1, width // 700)
        draw.ellipse((x - r, centre_y - r, x + r, centre_y + r), fill=faint)


def _draw_rule(
    draw: ImageDraw.ImageDraw,
    *,
    centre: tuple[int, int],
    half_width: int,
    gap: int,
    line_width: int,
    diamond: int,
    line_fill: tuple[int, ...],
    diamond_fill: tuple[int, ...],
) -> None:
    """A short horizontal rule broken by a small diamond."""
    x, y = centre
    draw.line((x - half_width, y, x - gap, y), fill=line_fill, width=line_width)
    draw.line((x + gap, y, x + half_width, y), fill=line_fill, width=line_width)
    draw.polygon(
        ((x, y - diamond), (x + diamond, y), (x, y + diamond), (x - diamond, y)),
        fill=diamond_fill,
    )


# Chinese typesetting: these never start a line, and these never end one.
_NO_LINE_START = set("，。、！？；：,.!?;:)）】」』》〉”’…—·")
_NO_LINE_END = set("(（【「『《〈“‘")


def _balanced_lines(draw: ImageDraw.ImageDraw, text: str, font, tracking: int, max_width: int,
                    max_lines: int) -> list[str]:
    """Break text into the fewest lines that fit, then even their lengths (no long line over a stub)."""
    paragraphs = [p for p in text.splitlines() if p.strip()] or [text]
    lines: list[str] = []
    for paragraph in paragraphs:
        tokens = re.findall(r"[A-Za-z0-9'’\-]+|\s+|.", paragraph)
        count = max(1, len(_wrap_tokens(draw, tokens, font, tracking, max_width)))
        # Narrow the measure until one more line would be needed; that width breaks most evenly.
        total = _tracked_width(draw, paragraph, font, tracking)
        target = max(1.0, total / count)
        best = _wrap_tokens(draw, tokens, font, tracking, max_width)
        for step in range(0, 40):
            measure = min(max_width, target * (1 + step * 0.02))
            candidate = _wrap_tokens(draw, tokens, font, tracking, measure)
            if len(candidate) == count:
                best = candidate
                break
        lines.extend(_phrase_lines(draw, paragraph, count, font, tracking, max_width) or best)
    if len(lines) > max_lines:
        kept = lines[:max_lines]
        kept[-1] = kept[-1].rstrip("，。、；：,.;: ") + "…"
        return kept
    return lines


# A line may end after these, so a phrase stays whole.
_PHRASE_ENDS = set("，、；：,;:")


def _phrase_lines(draw, paragraph: str, count: int, font, tracking: int, max_width: int) -> list[str] | None:
    """The most even way to split at phrase boundaries into `count` lines that fit, if one exists
    and is not much less even than a free split (a stub of a line reads worse than a broken phrase)."""
    if count < 2 or count > 3:
        return None
    breaks = [i + 1 for i, c in enumerate(paragraph[:-1]) if c in _PHRASE_ENDS]
    best: tuple[float, list[str]] | None = None
    from itertools import combinations

    for cuts in combinations(breaks, count - 1):
        bounds = [0, *cuts, len(paragraph)]
        lines = [paragraph[a:b].strip() for a, b in zip(bounds, bounds[1:])]
        widths = [_tracked_width(draw, line, font, tracking) for line in lines]
        if not all(lines) or max(widths) > max_width:
            continue
        spread = max(widths) / max(1.0, min(widths))
        if best is None or spread < best[0]:
            best = (spread, lines)
    return best[1] if best and best[0] <= 2.2 else None


def _wrap_tokens(draw, tokens: list[str], font, tracking: int, measure: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = current + token
        if not current.strip() or _tracked_width(draw, candidate.rstrip(), font, tracking) <= measure or token in _NO_LINE_START:
            current = candidate
            continue
        # Carry an opening bracket down with the word it belongs to.
        carried = ""
        while current and current[-1] in _NO_LINE_END:
            carried = current[-1] + carried
            current = current[:-1]
        lines.append(current.strip())
        current = carried + token.lstrip()
    if current.strip():
        lines.append(current.strip())
    return lines or [""]


def _tracked_width(draw: ImageDraw.ImageDraw, text: str, font, tracking: int) -> float:
    return sum(float(draw.textlength(c, font=font)) for c in text) + tracking * max(0, len(text) - 1)


def _draw_centred_line(draw, text: str, top: float, line_height: int, width: int, font, tracking: int, fill) -> None:
    """One line centred across the frame and vertically within its line box."""
    ascent, descent = font.getmetrics()
    y = top + (line_height - (ascent + descent)) / 2
    _draw_tracked_line(draw, text, (width - _tracked_width(draw, text, font, tracking)) / 2, y, font, tracking, fill)


def _draw_tracked_line(draw, text: str, x: float, y: float, font, tracking: int, fill) -> None:
    color = fill if len(fill) == 4 else (*fill, 255)
    for character in text:
        draw.text((round(x), round(y)), character, font=font, fill=color)
        x += float(draw.textlength(character, font=font)) + tracking


def _resolve_editorial_font(
    candidates: Sequence[tuple[Path, int]],
    fallback_path: Path | None,
    fallback_index: int,
) -> tuple[Path | None, int]:
    for candidate_path, candidate_index in candidates:
        if candidate_path.is_file():
            return candidate_path, candidate_index
    if fallback_path and fallback_path.is_file():
        return fallback_path, fallback_index
    return None, 0


def _load_font(font_path: Path | None, size: int, font_ttc_index: int):
    if font_path and font_path.is_file():
        return ImageFont.truetype(str(font_path), size=size, index=font_ttc_index)
    return ImageFont.load_default(size=size)


def _encoder_args(video_codec: str, quality_level: int, *, hardware: bool) -> list[str]:
    quality = max(0, min(100, int(quality_level)))
    is_hevc = str(video_codec or "h264").strip().lower() == "hevc"
    if hardware:
        args = [
            "-c:v",
            "hevc_videotoolbox" if is_hevc else "h264_videotoolbox",
            "-q:v",
            str(quality),
        ]
        if is_hevc:
            args.extend(["-tag:v", "hvc1"])
        return args
    if is_hevc:
        crf = max(0, min(32, round(32 - quality * 0.2)))
        return ["-c:v", "libx265", "-preset", "fast", "-crf", str(crf), "-tag:v", "hvc1"]
    crf = max(0, min(30, round(30 - quality * 0.2)))
    return ["-c:v", "libx264", "-preset", "fast", "-crf", str(crf)]


class _CliProgressBar:
    def __init__(
        self,
        total_seconds: float,
        *,
        label: str = "生成3:4贴片版",
        stream: TextIO | None = None,
        width: int = 28,
    ) -> None:
        self.total_seconds = max(0.001, float(total_seconds))
        self.label = label
        self.stream = stream or sys.stdout
        self.width = max(10, int(width))
        self._last_percent = -1
        self.update(0.0)

    def update(self, completed_seconds: float) -> None:
        completed = max(0.0, min(float(completed_seconds), self.total_seconds))
        ratio = completed / self.total_seconds
        percent = min(100, int(ratio * 100))
        if percent == self._last_percent:
            return
        self._last_percent = percent
        filled = min(self.width, int(round(ratio * self.width)))
        bar = "█" * filled + "·" * (self.width - filled)
        self.stream.write(
            f"\r🎞️ {self.label} [{bar}] {percent:3d}% "
            f"{_format_clock(completed)}/{_format_clock(self.total_seconds)}"
        )
        self.stream.flush()

    def finish(self) -> None:
        self.update(self.total_seconds)
        self.stream.write("\n")
        self.stream.flush()

    def abort(self) -> None:
        self.stream.write("\n")
        self.stream.flush()


def _run_export_command(command: list[str], total_duration: float, *, label: str) -> None:
    progress = _CliProgressBar(total_duration, label=label)
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as error_file:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=error_file,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for raw_line in process.stdout:
            completed_seconds = _parse_progress_seconds(raw_line.strip())
            if completed_seconds is not None:
                progress.update(completed_seconds)
        return_code = process.wait()
        if return_code == 0:
            progress.finish()
            return

        progress.abort()
        error_file.seek(0)
        detail = error_file.read().strip()
        raise subprocess.CalledProcessError(
            return_code,
            command,
            stderr=detail,
        )


def _parse_progress_seconds(line: str) -> float | None:
    key, separator, value = line.partition("=")
    if not separator:
        return None
    try:
        if key in {"out_time_us", "out_time_ms"}:
            return float(value) / 1_000_000
        if key == "out_time":
            hours, minutes, seconds = value.split(":", 2)
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (TypeError, ValueError):
        return None
    return None


def _format_clock(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _process_error_detail(exc: subprocess.CalledProcessError) -> str:
    return (exc.stderr or exc.stdout or str(exc)).strip()


def _first_text(value: Any) -> str:
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, Sequence):
        for item in value:
            cleaned = _clean_text(item)
            if cleaned:
                return cleaned
    return ""


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _clean_multiline(value: Any) -> str:
    """Like _clean_text, but a deliberate line break survives."""
    if not isinstance(value, str):
        return ""
    lines = (" ".join(line.split()) for line in value.splitlines())
    return "\n".join(line for line in lines if line)


def _first_multiline(value: Any) -> str:
    if isinstance(value, str):
        return _clean_multiline(value)
    if isinstance(value, Sequence):
        for item in value:
            cleaned = _clean_multiline(item)
            if cleaned:
                return cleaned
    return ""


def _parse_hex_color(value: Any) -> tuple[int, int, int] | None:
    text = str(value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", text):
        return None
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


__all__ = [
    "BOTTOM_CONTENTS",
    "PanelOptions",
    "THEMES",
    "TOP_CONTENTS",
    "ThreeByFourLayout",
    "build_export_command",
    "calculate_layout",
    "derive_output_path",
    "export_three_by_four_video",
    "render_layout_preview",
    "select_cover_copy",
    "select_panel_copy",
]
