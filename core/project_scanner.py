"""
项目和文件扫描器
- 扫描input目录：发现可处理的文档文件  
- 扫描output目录：发现已存在的项目
- 管理项目进度：检测项目状态和收集资源
"""

import os
import re
import json
import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from core.utils import logger, get_file_info, FileProcessingError


def scan_input_files(input_dir: str = "input") -> List[Dict[str, Any]]:
    """
    扫描input文件夹中的PDF、EPUB和MOBI文件
    
    Args:
        input_dir: 输入文件夹路径
    
    Returns:
        List[Dict[str, Any]]: 文件信息列表，包含路径、名称、大小等信息
    """
    # 将相对路径锚定到项目目录
    if not os.path.isabs(input_dir):
        input_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), input_dir)
    
    if not os.path.exists(input_dir):
        logger.warning(f"输入目录不存在: {input_dir}")
        return []
    
    supported_extensions = ['.pdf', '.epub', '.mobi']
    files = []
    
    logger.info(f"正在扫描 {input_dir} 文件夹...")
    
    try:
        for file_name in os.listdir(input_dir):
            file_path = os.path.join(input_dir, file_name)
            
            # 跳过目录
            if os.path.isdir(file_path):
                continue
            
            # 检查文件扩展名
            file_extension = Path(file_path).suffix.lower()
            if file_extension in supported_extensions:
                file_info = get_file_info(file_path)
                files.append(file_info)
                logger.debug(f"找到文件: {file_name} ({file_info['size_formatted']})")
    
    except Exception as e:
        logger.error(f"扫描文件夹失败: {str(e)}")
        raise FileProcessingError(f"扫描文件夹失败: {str(e)}")
    
    # 按修改时间排序，最新的在前
    files.sort(key=lambda x: x['modified_time'], reverse=True)
    
    pdf_count = sum(1 for f in files if f['extension'] == '.pdf')
    epub_count = sum(1 for f in files if f['extension'] == '.epub')
    mobi_count = sum(1 for f in files if f['extension'] == '.mobi')
    logger.info(f"共找到 {len(files)} 个文件 (PDF: {pdf_count}, EPUB: {epub_count}, MOBI: {mobi_count})")
    
    return files


def scan_output_projects(output_dir: str = "output") -> List[Dict[str, Any]]:
    """
    扫描 output 目录下的项目文件夹

    Returns:
        List[Dict]: 每个项目的 { path, name, modified_time } 信息
    """
    # 将相对路径锚定到项目目录
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), output_dir)

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

    # 最新修改在前
    projects.sort(key=lambda x: x["modified_time"], reverse=True)
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
    text_dir = os.path.join(project_dir, "text")
    images_dir = os.path.join(project_dir, "images")
    voice_dir = os.path.join(project_dir, "voice")
    final_video_path = os.path.join(project_dir, "final_video.mp4")

    # 检测raw数据 - 支持json或docx任一存在即可
    raw_json = _read_json_if_exists(os.path.join(text_dir, "raw.json"))
    raw_docx_path = os.path.join(text_dir, "raw.docx")
    has_raw = (raw_json is not None and isinstance(raw_json, dict) and 'content' in raw_json) or os.path.exists(raw_docx_path)

    script = _read_json_if_exists(os.path.join(text_dir, "script.json"))
    has_script = script is not None and isinstance(script, dict) and 'segments' in script

    keywords = _read_json_if_exists(os.path.join(text_dir, "keywords.json"))
    has_keywords = has_script and keywords is not None and 'segments' in keywords and \
        len(keywords.get('segments', [])) == len(script.get('segments', []))

    images_ok = False
    audio_ok = False
    if has_script:
        try:
            num_segments = len(script.get('segments', []))
            
            # 图片检查
            image_files = [f for f in os.listdir(images_dir) if os.path.isfile(os.path.join(images_dir, f))] if os.path.isdir(images_dir) else []
            image_indices = []
            for f in image_files:
                m = re.match(r'^segment_(\d+)\.(png|jpg|jpeg)$', f, re.IGNORECASE)
                if m:
                    image_indices.append(int(m.group(1)))
            images_ok = (len(image_indices) == num_segments) and (set(image_indices) == set(range(1, num_segments+1)))
            
            # 音频检查
            audio_files = [f for f in os.listdir(voice_dir) if os.path.isfile(os.path.join(voice_dir, f))] if os.path.isdir(voice_dir) else []
            audio_indices = []
            for f in audio_files:
                m = re.match(r'^voice_(\d+)\.(wav|mp3)$', f)
                if m:
                    audio_indices.append(int(m.group(1)))
            audio_ok = (len(audio_indices) == num_segments) and (set(audio_indices) == set(range(1, num_segments+1)))
        except Exception:
            images_ok = False
            audio_ok = False

    has_final_video = os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 0

    # 计算当前步骤 - 支持步骤3和4的独立执行
    current_step = 0
    current_step_name = ""

    if has_raw:
        current_step = 1
        current_step_name = "1"
    if has_script:
        current_step = 1.5
        current_step_name = "1.5"
    if has_keywords:
        current_step = 2
        current_step_name = "2"

    # 步骤3和4可以独立完成，取较高的步骤号
    if images_ok and audio_ok:
        current_step = 4
        current_step_name = "3+4"
    elif images_ok:
        current_step = 3
        current_step_name = "3"
    elif audio_ok:
        current_step = 4
        current_step_name = "4"

    if has_final_video:
        current_step = 5
        current_step_name = "5"

    # 向前推导逻辑：调整为支持并行步骤3和4
    if has_final_video:
        has_raw = has_script = has_keywords = images_ok = audio_ok = True
    elif images_ok and audio_ok:
        has_raw = has_script = has_keywords = True
    elif images_ok:
        has_raw = has_script = has_keywords = True
    elif audio_ok:
        has_raw = has_script = True
    elif has_keywords:
        has_raw = has_script = True
    elif has_script:
        has_raw = True

    return {
        'has_raw': has_raw,
        'has_script': has_script,
        'has_keywords': has_keywords,
        'images_ok': images_ok,
        'audio_ok': audio_ok,
        'has_final_video': has_final_video,
        'current_step': current_step,
        'current_step_name': current_step_name,
        'current_step_display': max(1, min(5, int(current_step))),
        'raw_json': raw_json,
        'script': script,
        'keywords': keywords,
        'final_video_path': final_video_path,
        'images_dir': images_dir,
        'voice_dir': voice_dir,
        'text_dir': text_dir
    }


def collect_ordered_assets(project_dir: str, script_data: Dict[str, Any], require_audio: bool = True) -> Dict[str, List[str]]:
    """
    根据 script_data 的段落顺序，收集按序排列的图片和音频文件路径

    Args:
        project_dir: 项目目录
        script_data: 包含段落信息的脚本数据
        require_audio: 是否强制要求每段音频都存在

    Returns:
        Dict[str, List[str]]: {"images": [...], "audio": [...]}
    """
    images_dir = os.path.join(project_dir, "images")
    voice_dir = os.path.join(project_dir, "voice")
    num_segments = len(script_data.get('segments', []))

    image_paths: List[str] = []
    audio_paths: List[str] = []
    
    for i in range(1, num_segments+1):
        # 按多种图片格式搜索
        candidates = [
            os.path.join(images_dir, f"segment_{i}.png"),
            os.path.join(images_dir, f"segment_{i}.jpg"),
            os.path.join(images_dir, f"segment_{i}.jpeg"),
        ]
        image_path = None
        for p in candidates:
            if os.path.exists(p):
                image_path = p
                break
                
        if not image_path:
            raise FileNotFoundError(f"缺少图片: segment_{i}.(png|jpg|jpeg)")
        image_paths.append(image_path)
        
        # 音频文件搜索
        audio_wav = os.path.join(voice_dir, f"voice_{i}.wav")
        audio_mp3 = os.path.join(voice_dir, f"voice_{i}.mp3")
        
        if require_audio:
            if os.path.exists(audio_wav):
                audio_paths.append(audio_wav)
            elif os.path.exists(audio_mp3):
                audio_paths.append(audio_mp3)
            else:
                raise FileNotFoundError(f"缺少音频: voice_{i}.(wav|mp3)")
        else:
            # 非强制音频：有则收集
            if os.path.exists(audio_wav):
                audio_paths.append(audio_wav)
            elif os.path.exists(audio_mp3):
                audio_paths.append(audio_mp3)
    
    return {"images": image_paths, "audio": audio_paths}


def clear_downstream_outputs(project_dir: str, from_step) -> None:
    """
    清理从指定步骤之后的产物
    from_step: 1, 1.5, 2, 3, 4, 5
    """
    text_dir = os.path.join(project_dir, "text")
    images_dir = os.path.join(project_dir, "images")
    voice_dir = os.path.join(project_dir, "voice")
    final_video_path = os.path.join(project_dir, "final_video.mp4")

    try:
        if from_step <= 1:
            # 删除 script 和 keywords
            for filename in ["script.json", "script.docx", "keywords.json"]:
                file_path = os.path.join(text_dir, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
        elif from_step <= 1.5:
            # 删除 keywords，保留 script
            for filename in ["keywords.json"]:
                file_path = os.path.join(text_dir, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
        if from_step <= 2:
            # 清空 images
            if os.path.isdir(images_dir):
                for f in os.listdir(images_dir):
                    fp = os.path.join(images_dir, f)
                    if os.path.isfile(fp):
                        os.remove(fp)
                        
        if from_step <= 3:
            # 清空 voice
            if os.path.isdir(voice_dir):
                for f in os.listdir(voice_dir):
                    fp = os.path.join(voice_dir, f)
                    if os.path.isfile(fp):
                        os.remove(fp)
                        
        if from_step <= 4:
            # 删除最终视频
            if os.path.exists(final_video_path):
                os.remove(final_video_path)
                
    except Exception as e:
        logger.warning(f"清理旧产物失败: {e}")