from __future__ import annotations

import json
import subprocess
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from moviepy import AudioFileClip

from core.infra.ai.claude_agent import run_step4_hyperframes_agent
from core.infra.hyperframes.runtime import hyperframes_command, parse_size, subprocess_env
from core.infra.project_paths import ProjectPaths


def _audio_duration_seconds(audio_path: str) -> float:
    path = Path(audio_path)
    if path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            return round(frames / float(rate), 3)

    clip = AudioFileClip(str(path))
    try:
        return round(float(clip.duration or 0.0), 3)
    finally:
        clip.close()


def _normalize_targets(target_segments: Optional[Iterable[int]], total_segments: int) -> list[int]:
    if target_segments is None:
        return list(range(1, total_segments + 1))
    parsed = []
    for value in target_segments:
        try:
            idx = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= idx <= total_segments:
            parsed.append(idx)
    return sorted(set(parsed))


def _build_payload(
    *,
    segment: Dict[str, Any],
    segment_index: int,
    duration_seconds: float,
    width: int,
    height: int,
    style_preset: str,
    description_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "segmentIndex": segment_index,
        "index": segment_index,
        "title": segment.get("title") or segment.get("header_title") or f"Segment {segment_index}",
        "content": segment.get("content", ""),
        "durationSeconds": duration_seconds,
        "width": width,
        "height": height,
        "stylePreset": style_preset,
        "descriptionSummary": (description_data or {}).get("summary", ""),
    }


def _write_render_log(work_dir: Path, content: str) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "render.log").write_text(content, encoding="utf-8")


def _render_one_segment(
    *,
    project_output_dir: str,
    paths: ProjectPaths,
    script_data: Dict[str, Any],
    segment_index: int,
    image_size: str,
    output_dir: str,
    description_data: Optional[Dict[str, Any]],
    style_preset: str,
    max_turns: int,
    render_fps: int,
    session_log_path: str,
    repo_root: str,
    llm_server: Optional[str],
    llm_model: Optional[str],
    llm_base_url: Optional[str],
) -> Dict[str, Any]:
    audio_path = paths.segment_audio_exists(segment_index)
    if not audio_path:
        return {"success": False, "segment_index": segment_index, "missing_audio": True}

    width, height = parse_size(image_size)
    segments = script_data.get("segments") or []
    segment = segments[segment_index - 1] if 0 <= segment_index - 1 < len(segments) else {}
    duration_seconds = _audio_duration_seconds(audio_path)
    output_dir_path = Path(output_dir)
    work_dir = output_dir_path / "hyperframes" / f"segment_{segment_index}"
    output_path = (output_dir_path / f"segment_{segment_index}.mp4").resolve()
    payload = _build_payload(
        segment=segment,
        segment_index=segment_index,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        style_preset=style_preset,
        description_data=description_data,
    )

    try:
        run_step4_hyperframes_agent(
            work_dir=str(work_dir),
            project_dir=project_output_dir,
            segment_payload=payload,
            duration_seconds=duration_seconds,
            style_preset=style_preset,
            max_turns=max_turns,
            session_log_path=session_log_path,
            llm_server=llm_server,
            llm_model=llm_model,
            llm_base_url=llm_base_url,
        )
        command = [
            *hyperframes_command(),
            "render",
            "--output",
            str(output_path),
            "--fps",
            str(int(render_fps or 30)),
            "--variables",
            json.dumps(payload, ensure_ascii=False),
        ]
        completed = subprocess.run(
            command,
            cwd=work_dir,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=subprocess_env(),
            timeout=max(300, int(duration_seconds * 90)),
        )
        _write_render_log(work_dir, completed.stdout or "render ok")
        return {"success": True, "segment_index": segment_index, "image_path": str(output_path)}
    except subprocess.TimeoutExpired as exc:
        _write_render_log(work_dir, f"渲染超时: {exc}")
        return {"success": False, "segment_index": segment_index, "error": str(exc)}
    except subprocess.CalledProcessError as exc:
        _write_render_log(work_dir, exc.output or str(exc))
        return {"success": False, "segment_index": segment_index, "error": str(exc)}
    except Exception as exc:
        _write_render_log(work_dir, str(exc))
        return {"success": False, "segment_index": segment_index, "error": str(exc)}


def render_hyperframes_segments_with_agent(
    *,
    project_output_dir: str,
    script_data: Dict[str, Any],
    image_size: str,
    output_dir: str,
    target_segments: Optional[Iterable[int]],
    description_data: Optional[Dict[str, Any]],
    style_preset: str,
    max_turns: int,
    render_fps: int,
    concurrency: int,
    session_log_path: str,
    repo_root: str,
    llm_server: Optional[str] = None,
    llm_model: Optional[str] = None,
    llm_base_url: Optional[str] = None,
) -> Dict[str, Any]:
    paths = ProjectPaths(project_output_dir)
    segments = script_data.get("segments") or []
    total_segments = len(segments)
    targets = _normalize_targets(target_segments, total_segments)

    image_paths = ["" for _ in range(total_segments)]
    for idx in range(1, total_segments + 1):
        candidate = Path(output_dir) / f"segment_{idx}.mp4"
        if candidate.exists():
            image_paths[idx - 1] = str(candidate)

    failed_segments: list[int] = []
    processed_segments: list[int] = []
    missing_audio_segments: list[int] = []

    if not targets:
        return {
            "image_paths": image_paths,
            "failed_segments": [],
            "processed_segments": [],
            "missing_audio_segments": [],
        }

    worker_count = max(1, int(concurrency or 1))
    task_kwargs = [
        {
            "project_output_dir": project_output_dir,
            "paths": paths,
            "script_data": script_data,
            "segment_index": idx,
            "image_size": image_size,
            "output_dir": output_dir,
            "description_data": description_data,
            "style_preset": style_preset,
            "max_turns": max_turns,
            "render_fps": render_fps,
            "session_log_path": str(Path(output_dir) / "hyperframes" / f"segment_{idx}" / "_step4_hyperframes_agent_session.jsonl"),
            "repo_root": repo_root,
            "llm_server": llm_server,
            "llm_model": llm_model,
            "llm_base_url": llm_base_url,
        }
        for idx in targets
    ]

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(_render_one_segment, **kwargs) for kwargs in task_kwargs]
        for future in as_completed(futures):
            result = future.result()
            idx = int(result["segment_index"])
            if result.get("success"):
                processed_segments.append(idx)
                image_paths[idx - 1] = result["image_path"]
            else:
                failed_segments.append(idx)
                if result.get("missing_audio"):
                    missing_audio_segments.append(idx)

    return {
        "image_paths": image_paths,
        "failed_segments": sorted(failed_segments),
        "processed_segments": sorted(processed_segments),
        "missing_audio_segments": sorted(missing_audio_segments),
    }
