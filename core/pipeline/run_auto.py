"""自动模式流程编排模块。

本文件实现“从原始文档到最终视频”的全链路自动执行逻辑，核心职责包括：
1. 参数与模型配置校验，提前拦截不合法输入。
2. 依次编排步骤 1.5/2/3/4/5（脚本、描述小结、图片、配音、合成视频）。
3. 在主流程失败或部分失败时进行必要兜底（如视频合成兜底）。
4. 补充封面图生成，并汇总统计信息与产物路径作为统一结果返回。

该模块关注“流程控制与结果汇总”，具体单步业务由 steps 模块实现。
"""

import datetime
import json
import os
from typing import Any, Dict, List, Optional

from core.pipeline.steps import (
    _get_project_root,
    _ensure_opening_narration,
    _resolve_bgm_audio_path,
    _run_cover_generation,
    run_step_1 as _run_step_1,
    run_step_1_5 as _run_step_1_5,
    run_step_2 as _run_step_2,
    run_step_3 as _run_step_3,
    run_step_4 as _run_step_4,
    run_step_5 as _run_step_5,
)
from core.config import Config, config as global_config
from core.domain.composer import VideoComposer
from core.config import VideoGenerationConfig
from core.infra.project_paths import ProjectPaths
from core.shared import load_json_file, logger


def _validate_auto_mode_config(config: VideoGenerationConfig) -> None:
    """Validate runtime config while preserving legacy small-segment behavior."""
    num_segments = int(config.num_segments)
    if num_segments <= 0:
        raise ValueError("num_segments必须大于0")
    validated_segments = max(Config.MIN_NUM_SEGMENTS, num_segments)

    Config.validate_parameters(
        num_segments=validated_segments,
        llm_server=config.llm_server_step2,
        image_server=config.image_server,
        tts_server=config.tts_server,
        image_model=config.image_model,
        image_size=config.image_size,
        image_prompt_template=config.image_prompt_template,
        llm_model=config.llm_model_step2,
    )
    Config.validate_model_provider_pair("image", config.get_effective_cover_server(), config.get_effective_cover_model())


def run_auto(config: VideoGenerationConfig) -> Dict[str, Any]:
    """Run full end-to-end video generation flow."""
    start_time = datetime.datetime.now()
    try:
        _validate_auto_mode_config(config)
    except Exception as exc:
        return {"success": False, "message": f"参数验证失败: {exc}"}

    step1 = _run_step_1(
        config.input_file,
        config.output_dir,
        config.num_segments,
        extra_requirements=config.extra_requirements,
    )
    if not step1.get("success"):
        return {"success": False, "message": step1.get("message", "步骤1处理失败")}
    project_output_dir = step1["project_output_dir"]
    paths = ProjectPaths(project_output_dir)
    raw_data = load_json_file(paths.raw_json()) if os.path.exists(paths.raw_json()) else {}
    original_length = int(
        (step1.get("raw") or {}).get("total_length")
        or raw_data.get("total_length")
        or len(raw_data.get("content") or "")
        or 0
    )

    step15 = _run_step_1_5(
        project_output_dir,
        config.num_segments,
        is_new_project=True,
        auto_mode=True,
        split_mode=config.step1_5_split_mode,
        llm_server_step1_5=config.llm_server_step1_5,
        llm_model_step1_5=config.llm_model_step1_5,
    )
    if not step15.get("success"):
        return {"success": False, "message": step15.get("message", "步骤1.5处理失败")}
    script_data = step15.get("script_data")
    script_path = step15.get("script_path")

    canonical_script_path = paths.script_json()
    if script_data and (not os.path.exists(canonical_script_path)):
        try:
            with open(canonical_script_path, "w", encoding="utf-8") as handle:
                json.dump(script_data, handle, ensure_ascii=False, indent=2)
            script_path = canonical_script_path
        except Exception:
            pass

    step2 = _run_step_2(
        config.llm_server_step2,
        config.llm_model_step2,
        config.llm_base_url_step2,
        project_output_dir,
        script_path=script_path if script_path and os.path.exists(script_path) else None,
    )
    if not step2.get("success"):
        return {"success": False, "message": step2.get("message", "步骤2处理失败")}

    description_data: Optional[Dict[str, Any]] = None
    description_path: Optional[str] = step2.get("mini_summary_path")

    if description_path and os.path.exists(description_path):
        description_data = load_json_file(description_path)

    step3 = _run_step_3(
        tts_server=config.tts_server,
        voice=config.voice,
        tts_model=config.tts_model,
        project_output_dir=project_output_dir,
        opening_quote=config.opening_quote,
        speech_rate=config.speech_rate,
        loudness_rate=config.loudness_rate,
        emotion=config.emotion,
        emotion_scale=config.emotion_scale,
        mute_cut_remain_ms=config.mute_cut_remain_ms,
        mute_cut_threshold=config.mute_cut_threshold,
    )
    if not step3.get("success"):
        return {"success": False, "message": step3.get("message", "步骤3处理失败")}
    audio_paths = step3.get("audio_paths", [])

    step4 = _run_step_4(
        image_server=config.image_server,
        image_model=config.image_model,
        image_size=config.image_size,
        image_style_preset=config.image_style_preset,
        project_output_dir=project_output_dir,
        opening_quote=config.opening_quote,
        llm_model=config.llm_model_step4,
        llm_server=config.llm_server_step4,
        llm_base_url=config.llm_base_url_step4,
        visual_mode=config.visual_mode,
        motion_style_preset=config.motion_style_preset,
        motion_max_turns=config.motion_max_turns,
        motion_render_fps=config.motion_render_fps,
        motion_concurrency=config.motion_concurrency,
        image_prompt_template=config.image_prompt_template,
    )
    if not step4.get("success"):
        failed_image_segments = step4.get("failed_segments") or step4.get("failed_image_segments") or []
        return {
            "success": False,
            "message": step4.get("message", "步骤4处理失败"),
            "failed_image_segments": failed_image_segments,
            "needs_retry": True,
            "stage": 4,
            "image_paths": step4.get("image_paths", []),
        }
    image_paths: List[str] = step4.get("image_paths", [])
    failed_image_segments: List[int] = []

    step5 = _run_step_5(
        project_output_dir=project_output_dir,
        image_size=config.get_effective_video_size(),
        enable_subtitles=config.enable_subtitles,
        bgm_filename=config.bgm_filename,
        voice=config.voice,
        tts_model=config.tts_model,
        opening_quote=config.opening_quote,
        speech_rate=config.speech_rate,
        loudness_rate=config.loudness_rate,
        emotion=config.emotion,
        emotion_scale=config.emotion_scale,
        mute_cut_remain_ms=config.mute_cut_remain_ms,
        mute_cut_threshold=config.mute_cut_threshold,
    )
    if step5.get("success"):
        final_video_path = step5.get("final_video")
    else:
        try:
            bgm_audio_path = _resolve_bgm_audio_path(config.bgm_filename, _get_project_root())
            opening_image_path = step4.get("opening_image_path")
            opening_narration_audio_path = _ensure_opening_narration(
                script_data,
                paths.voice,
                config.voice,
                config.tts_model,
                config.opening_quote,
                speech_rate=config.speech_rate,
                loudness_rate=config.loudness_rate,
                emotion=config.emotion,
                emotion_scale=config.emotion_scale,
                mute_cut_remain_ms=config.mute_cut_remain_ms,
                mute_cut_threshold=config.mute_cut_threshold,
            )
            composer = VideoComposer()
            final_video_path = composer.compose_video(
                image_paths,
                audio_paths,
                paths.final_video(),
                script_data=script_data,
                enable_subtitles=config.enable_subtitles,
                bgm_audio_path=bgm_audio_path,
                opening_image_path=opening_image_path,
                opening_narration_audio_path=opening_narration_audio_path,
                bgm_volume=float(getattr(global_config, "BGM_DEFAULT_VOLUME", 0.2)),
                narration_volume=float(getattr(global_config, "NARRATION_DEFAULT_VOLUME", 1.0)),
                image_size=config.get_effective_video_size(),
                opening_quote=config.opening_quote,
                project_root=project_output_dir,
            )
        except Exception:
            return {"success": False, "message": step5.get("message", "步骤5处理失败")}

    cover_result = None
    try:
        cover_result = _run_cover_generation(
            project_output_dir,
            config.get_effective_cover_size(),
            config.get_effective_cover_server(),
            config.get_effective_cover_model(),
            config.cover_image_style,
            max(1, int(config.cover_image_count)),
            script_data,
            raw_data,
        )
    except Exception as exc:
        logger.warning(f"封面生成失败: {exc}")

    end_time = datetime.datetime.now()
    execution_time = (end_time - start_time).total_seconds()
    compression_ratio = (1 - (script_data["total_length"] / original_length)) * 100 if original_length > 0 else 0.0

    result: Dict[str, Any] = {
        "success": True,
        "message": "视频制作完成",
        "execution_time": execution_time,
        "script": {
            "file_path": script_path,
            "total_length": script_data["total_length"],
            "segments_count": script_data["actual_segments"],
        },
        "images": image_paths,
        "audio_files": audio_paths,
        "final_video": final_video_path,
        "cover_images": (cover_result or {}).get("cover_paths", []),
        "statistics": {
            "original_length": original_length,
            "compression_ratio": f"{compression_ratio:.1f}%",
            "total_processing_time": execution_time,
        },
        "project_output_dir": project_output_dir,
        "failed_image_segments": failed_image_segments,
    }

    if description_data and description_path:
        result["mini_summary"] = {
            "file_path": description_path,
            "summary_length": description_data.get("total_length", len(description_data.get("summary", ""))),
        }

    if cover_result:
        result["cover_generation"] = cover_result

    return result


__all__ = ["run_auto"]
