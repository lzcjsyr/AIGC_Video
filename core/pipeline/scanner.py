"""项目扫描与进度探测模块。

本文件负责在本地工程目录中发现“可处理输入”与“可继续处理项目”，核心职责：
1. 扫描 input 目录，识别可处理文档并返回统一文件元数据（名称、路径、大小、时间等）。
2. 扫描 output 目录，识别历史项目并聚合项目级信息，供 CLI/API 选择继续处理。
3. 根据项目产物（script、images、voice、final_video 等）判断当前进度与缺失项。
4. 为交互流程提供结构化状态数据，支持断点续跑与下一步决策。

该模块只负责“状态发现与描述”，不执行实际生成任务。
"""

import os
import re
import json
import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from core.shared import (
    SUPPORTED_INPUT_EXTENSIONS,
    logger,
    get_file_info,
    FileProcessingError,
    project_name_sort_key,
)
from core.infra.project_paths import ProjectPaths
from core.config import OPENING_QUOTE

SEGMENT_MEDIA_EXTENSIONS = ("png", "jpg", "jpeg", "mp4", "mov", "avi", "mkv", "webm", "flv", "m4v")


def _project_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def scan_input_files(input_dir: str = "input") -> List[Dict[str, Any]]:
    """
    扫描input文件夹中的可处理文档
    
    Args:
        input_dir: 输入文件夹路径
    
    Returns:
        List[Dict[str, Any]]: 文件信息列表，包含路径、名称、大小等信息
    """
    # 将相对路径锚定到项目目录
    if not os.path.isabs(input_dir):
        input_dir = os.path.join(_project_root(), input_dir)
    
    if not os.path.exists(input_dir):
        logger.warning(f"输入目录不存在: {input_dir}")
        return []
    
    files = []
    
    logger.info(f"正在扫描 {input_dir} 文件夹...")
    
    try:
        for file_name in os.listdir(input_dir):
            file_path = os.path.join(input_dir, file_name)
            
            if os.path.isdir(file_path):
                file_info = get_file_info(file_path)
                files.append(file_info)
                logger.debug(f"找到文件夹: {file_name}")
                continue
            
            # 检查文件扩展名
            file_extension = Path(file_path).suffix.lower()
            if file_extension in SUPPORTED_INPUT_EXTENSIONS:
                file_info = get_file_info(file_path)
                files.append(file_info)
                logger.debug(f"找到文件: {file_name} ({file_info['size_formatted']})")
    
    except Exception as e:
        logger.error(f"扫描文件夹失败: {str(e)}")
        raise FileProcessingError(f"扫描文件夹失败: {str(e)}")
    
    # 按修改时间排序，最新的在前
    files.sort(key=lambda x: x['modified_time'], reverse=True)
    
    logger.info("共找到 %d 个可处理文件", len(files))
    
    return files


def scan_output_projects(output_dir: str = "output") -> List[Dict[str, Any]]:
    """
    扫描 output 目录下的项目文件夹

    Returns:
        List[Dict]: 每个项目的 { path, name, modified_time } 信息
    """
    # 将相对路径锚定到项目目录
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(_project_root(), output_dir)

    projects: List[Dict[str, Any]] = []
    if not os.path.exists(output_dir):
        return projects

    try:
        for entry in os.listdir(output_dir):
            p = os.path.join(output_dir, entry)
            if not os.path.isdir(p):
                continue
            # 判断：包含 text/ 目录即认为是项目
            text_dir = os.path.join(p, "text")
            if os.path.isdir(text_dir):
                stat = os.stat(p)
                projects.append({
                    "path": p,
                    "name": entry,
                    "modified_time": datetime.datetime.fromtimestamp(stat.st_mtime)
                })
    except Exception as e:
        logger.warning(f"扫描输出目录失败: {e}")
        return []

    # 按项目文件夹名排序，保持选择列表与目录名前缀数字一致
    projects.sort(key=project_name_sort_key)
    return projects


def _read_json_if_exists(path: str) -> Optional[Dict[str, Any]]:
    """安全读取JSON文件"""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"读取JSON失败 {path}: {e}")
    return None


def detect_project_progress(project_dir: str) -> Dict[str, Any]:
    """
    检测项目当前进度阶段

    Returns:
        进度字典，包含当前步骤、各阶段完成状态等信息
    """
    # 使用 ProjectPaths 管理路径
    paths = ProjectPaths(project_dir)
    
    cover_images = []
    for fname in os.listdir(project_dir) if os.path.isdir(project_dir) else []:
        if fname.lower().startswith("cover_") and fname.lower().endswith(('.png', '.jpg', '.jpeg')):
            cover_images.append(os.path.join(project_dir, fname))
    cover_images.sort()

    # 检测raw数据 - 支持json或docx任一存在即可
    raw_json = _read_json_if_exists(paths.raw_json())
    has_raw = (raw_json is not None and isinstance(raw_json, dict) and 'content' in raw_json) or os.path.exists(paths.raw_docx())

    script = _read_json_if_exists(paths.script_json())
    has_script = script is not None and isinstance(script, dict) and 'segments' in script

    image_description = _read_json_if_exists(paths.mini_summary_json())

    has_description = False
    if has_script:
        if image_description is not None and image_description.get('summary'):
            has_description = True

    images_ok = False
    audio_ok = False
    images_started = False
    audio_started = False
    images_in_progress = False
    audio_in_progress = False
    has_opening_image = False
    has_opening_audio = False
    if has_script:
        try:
            num_segments = len(script.get('segments', []))
            
            # 画面素材检查 - 支持静态图片和 HyperFrames/视频片段
            image_files = [f for f in os.listdir(paths.images) if os.path.isfile(os.path.join(paths.images, f))] if os.path.isdir(paths.images) else []
            image_indices = []
            for f in image_files:
                m = re.match(rf'^segment_(\d+)\.({"|".join(SEGMENT_MEDIA_EXTENSIONS)})$', f, re.IGNORECASE)
                if m:
                    image_indices.append(int(m.group(1)))

            # 检测开场素材（opening.mp4 / opening.png）
            has_opening_image = os.path.exists(paths.opening_image())

            # 步骤4：画面完成条件 - 根据 OPENING_QUOTE 配置调整
            segment_images_complete = (len(image_indices) == num_segments) and (set(image_indices) == set(range(1, num_segments+1)))
            if OPENING_QUOTE:
                images_ok = segment_images_complete and has_opening_image
            else:
                images_ok = segment_images_complete
            images_started = len(image_indices) > 0 or (OPENING_QUOTE and has_opening_image)
            images_in_progress = images_started and not images_ok

            # 音频检查 - 使用 ProjectPaths
            audio_files = [f for f in os.listdir(paths.voice) if os.path.isfile(os.path.join(paths.voice, f))] if os.path.isdir(paths.voice) else []
            audio_indices = []
            for f in audio_files:
                m = re.match(r'^voice_(\d+)\.(wav|mp3)$', f)
                if m:
                    audio_indices.append(int(m.group(1)))

            # 检测开场音频（opening.wav，新项目；opening.mp3，旧项目兼容）
            has_opening_audio = os.path.exists(paths.opening_audio())

            # 步骤3：音频完成条件 - 根据 OPENING_QUOTE 配置调整
            segment_audio_complete = (len(audio_indices) == num_segments) and (set(audio_indices) == set(range(1, num_segments+1)))
            if OPENING_QUOTE:
                audio_ok = segment_audio_complete and has_opening_audio
            else:
                audio_ok = segment_audio_complete
            audio_started = len(audio_indices) > 0 or (OPENING_QUOTE and has_opening_audio)
            audio_in_progress = audio_started and not audio_ok
        except Exception:
            images_ok = False
            audio_ok = False
            images_started = False
            audio_started = False
            images_in_progress = False
            audio_in_progress = False
            has_opening_image = False
            has_opening_audio = False

    has_final_video = os.path.exists(paths.final_video()) and os.path.getsize(paths.final_video()) > 0

    # 计算当前步骤 - 支持步骤3和4的独立执行
    current_step = 0
    current_step_name = ""

    if has_raw:
        current_step = 1
        current_step_name = "1"
    if has_script:
        current_step = 1.5
        current_step_name = "1.5"
    if has_description:
        current_step = 2
        current_step_name = "2"

    # 步骤3是语音，步骤4是画面；两者可以独立重跑，但进度按顺序显示
    if images_ok and audio_ok:
        current_step = 4
        current_step_name = "4"
    elif images_ok:
        current_step = 4
        current_step_name = "4"
    elif images_in_progress:
        current_step = max(current_step, 4)
        current_step_name = "4（进行中）"
    elif audio_ok:
        current_step = 3
        current_step_name = "3"
    elif audio_in_progress:
        current_step = max(current_step, 3)
        current_step_name = "3（进行中）"

    if has_final_video:
        current_step = 5
        current_step_name = "5"
    if cover_images:
        current_step = max(current_step, 6)
        current_step_name = "6"

    # 向前推导逻辑：支持步骤3语音和步骤4画面独立重跑
    if has_final_video:
        has_raw = has_script = has_description = images_ok = audio_ok = True
    elif images_ok and audio_ok:
        has_raw = has_script = has_description = True
    elif images_ok:
        has_raw = has_script = has_description = True
    elif audio_ok:
        has_raw = has_script = True
    elif has_description:
        has_raw = has_script = True
    elif has_script:
        has_raw = True

    return {
        'has_raw': has_raw,
        'has_script': has_script,
        'has_description': has_description,
        'images_ok': images_ok,
        'audio_ok': audio_ok,
        'images_started': images_started,
        'audio_started': audio_started,
        'images_in_progress': images_in_progress,
        'audio_in_progress': audio_in_progress,
        'has_opening_image': has_opening_image,
        'has_opening_audio': has_opening_audio,
        'has_final_video': has_final_video,
        'has_cover': len(cover_images) > 0,
        'current_step': current_step,
        'current_step_name': current_step_name,
        'current_step_display': max(1, min(6, int(current_step))),
        'raw_json': raw_json,
        'script': script,
        'mini_summary': image_description,
        'final_video_path': paths.final_video(),
        'cover_images': cover_images,
        'images_dir': paths.images,
        'voice_dir': paths.voice,
        'text_dir': paths.text,
    }


def clear_downstream_outputs(project_dir: str, from_step) -> None:
    """
    清理从指定步骤之后的产物
    from_step: 1, 1.5, 2, 3, 4, 5
    """
    # 使用 ProjectPaths 管理路径
    paths = ProjectPaths(project_dir)

    try:
        if from_step <= 1:
            # 删除脚本和描述小结
            for filepath in [paths.script_json(), paths.script_docx(), paths.mini_summary_json()]:
                if os.path.exists(filepath):
                    os.remove(filepath)
        elif from_step <= 1.5:
            # 删除描述小结，保留脚本
            if os.path.exists(paths.mini_summary_json()):
                os.remove(paths.mini_summary_json())
                    
        if from_step <= 3:
            # 清空 voice（步骤3语音）及其下游画面/成片
            if os.path.isdir(paths.voice):
                for f in os.listdir(paths.voice):
                    fp = os.path.join(paths.voice, f)
                    if os.path.isfile(fp):
                        os.remove(fp)

        if from_step <= 4:
            # 清空 images（步骤4画面）及其下游成片
            if os.path.isdir(paths.images):
                for f in os.listdir(paths.images):
                    fp = os.path.join(paths.images, f)
                    if os.path.isfile(fp):
                        os.remove(fp)

            # 删除最终视频
            if os.path.exists(paths.final_video()):
                os.remove(paths.final_video())
                
    except Exception as e:
        logger.warning(f"清理旧产物失败: {e}")
