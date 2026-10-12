import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import config
from core.domain.composer import VideoComposer
from core.domain.metadata import get_primary_golden_quote, parse_marked_focus_text
from core.infra.hyperframes.runtime import hyperframes_command, parse_size, subprocess_env
from core.shared import logger


_QUOTE_BREAK_PUNCTUATION = {"。", "！", "？", "!", "?", "；", ";", "，", ",", "：", ":"}


def _hyperframes_app_dir() -> Path:
    return Path(__file__).resolve().parent / "app"


def _split_quote_fragments(quote: str) -> List[str]:
    fragments: List[str] = []
    normalized = (quote or "").replace("\r\n", "\n").replace("\r", "\n")

    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        current = ""
        for char in line:
            current += char
            if char in _QUOTE_BREAK_PUNCTUATION:
                cleaned = current.strip()
                if cleaned:
                    fragments.append(cleaned)
                current = ""

        cleaned = current.strip()
        if cleaned:
            fragments.append(cleaned)

    return fragments


def _split_quote_lines(quote: str) -> List[str]:
    max_chars = int(getattr(config, "OPENING_HYPERFRAMES_MAX_CHARS_PER_LINE", 20))
    max_lines = int(getattr(config, "OPENING_HYPERFRAMES_MAX_LINES", 6))
    composer = VideoComposer()
    lines: List[str] = []

    for fragment in _split_quote_fragments(quote):
        if len(fragment) <= max_chars:
            lines.append(fragment)
            continue

        lines.extend(composer.split_text_for_subtitle(fragment, max_chars, max_lines or 999))

    if max_lines > 0 and len(lines) > max_lines:
        return lines[: max_lines - 1] + ["".join(lines[max_lines - 1 :])]
    return lines


def _pick_focus_words(lines: List[str]) -> List[str]:
    for candidate in ("系统", "规则", "机制", "权力", "金钱", "认知"):
        if any(candidate in line for line in lines):
            return [candidate]
    return []


def _build_line_appear_times(
    line_count: int,
    first_line_seconds: float,
    last_line_seconds: float,
) -> List[float]:
    if line_count <= 0:
        return []
    if line_count == 1:
        return [round(first_line_seconds, 3)]

    step = (last_line_seconds - first_line_seconds) / (line_count - 1)
    return [round(first_line_seconds + step * index, 3) for index in range(line_count)]


def _resolve_timeline_config() -> tuple[float, int, int]:
    duration_seconds = float(getattr(config, "OPENING_HYPERFRAMES_DURATION_SECONDS", 4.0) or 4.0)
    fps = int(getattr(config, "OPENING_HYPERFRAMES_FPS", 30) or 30)

    duration_seconds = max(0.1, duration_seconds)
    fps = max(1, fps)
    duration_in_frames = max(1, round(duration_seconds * fps))
    return duration_seconds, fps, duration_in_frames


def _resolve_line_timing(duration_seconds: float, fps: int) -> tuple[float, float]:
    first_line_seconds = float(getattr(config, "OPENING_HYPERFRAMES_FIRST_LINE_SECONDS", 0.5) or 0.5)
    last_line_seconds = float(getattr(config, "OPENING_HYPERFRAMES_LAST_LINE_SECONDS", 2.0) or 2.0)

    max_visible_time = max(0.0, duration_seconds - (1.0 / fps))
    first_line_seconds = min(max(0.0, first_line_seconds), max_visible_time)
    last_line_seconds = min(max(first_line_seconds, last_line_seconds), max_visible_time)
    return first_line_seconds, last_line_seconds


def render_opening_video(
    *,
    image_size: str,
    output_dir: str,
    script_data: Optional[Dict[str, Any]],
    opening_quote: bool = True,
    opening_bg_path: Optional[str] = None,
) -> Optional[str]:
    if not opening_quote:
        return None

    quote = get_primary_golden_quote(script_data or {}, "").strip()
    if not quote:
        return None

    clean_quote, marked_focus_words = parse_marked_focus_text(quote)
    if not clean_quote:
        return None

    # The opening template is authored on a 2560×1440 canvas.  Rendering it
    # at a smaller image-generation size changes its fixed-pixel layout; the
    # final composer is responsible for scaling this video to the target size.
    parse_size(image_size)
    width, height = 2560, 1440
    quote_lines = _split_quote_lines(clean_quote)
    app_dir = _hyperframes_app_dir()
    output_path = Path(output_dir).resolve() / "opening.mp4"
    duration_seconds, fps, _ = _resolve_timeline_config()
    first_line_seconds, last_line_seconds = _resolve_line_timing(duration_seconds, fps)
    raw_source_name = (script_data or {}).get("source_name")
    book_title = raw_source_name.strip() if isinstance(raw_source_name, str) else ""
    if not book_title:
        book_title = "未命名作品"
    book_title = f"——{book_title}——"

    # 构建注入给 HyperFrames index.html 的 variables 字典
    props = {
        "bookTitle": book_title,
        "quoteLines": quote_lines,
        "focusWords": marked_focus_words or _pick_focus_words(quote_lines),
        "ipName": str(getattr(config, "OPENING_HYPERFRAMES_IP_NAME", "") or "").strip(),
        "lineAppearTimes": _build_line_appear_times(
            len(quote_lines),
            first_line_seconds=first_line_seconds,
            last_line_seconds=last_line_seconds,
        ),
        "width": width,
        "height": height,
        "durationSeconds": duration_seconds,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="aigc-opening-") as temporary:
        work_dir = Path(temporary) / "app"
        shutil.copytree(app_dir, work_dir)
        if opening_bg_path and os.path.exists(opening_bg_path):
            try:
                shutil.copy2(opening_bg_path, work_dir / "opening_bg.png")
                props["backgroundImage"] = "opening_bg.png"
            except OSError as e:
                logger.warning(f"Failed to copy opening background: {e}")

        # 运行 hyperframes 渲染命令
        command = [
            *hyperframes_command(),
            "render",
            "--output",
            str(output_path),
            "--variables",
            json.dumps(props, ensure_ascii=False),
        ]

        try:
            print("🎬 正在生成 HyperFrames 开场视频，这通常需要 10-15 秒左右...")
            subprocess.run(
                command,
                cwd=work_dir,
                check=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=subprocess_env(),
            )
            logger.info("Opening HyperFrames video rendered: %s", output_path)
            return str(output_path)
        except subprocess.CalledProcessError as exc:
            logger.warning("Opening HyperFrames render failed: %s", exc)
            if exc.output:
                print(f"❌ 渲染日志:\n{exc.output}")
            return None
