"""
Media-related logic: opening image, images per segment, and TTS synthesis.
"""

from typing import Optional, Dict, Any, List
import os
import concurrent.futures
import threading

from config import config
from prompts import OPENING_IMAGE_STYLES
from utils import logger, ensure_directory_exists
from core.services import text_to_image_doubao, text_to_audio_bytedance
from prompts import IMAGE_STYLE_PRESETS

import requests


def _download_to_path(url: str, output_path: str, error_msg: str = "下载失败") -> None:
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(resp.content)
    except Exception as e:
        raise ValueError(f"{error_msg}: {e}")


def generate_opening_image(model: str, opening_style: str,
                           image_size: str, output_dir: str, opening_quote: bool = True) -> Optional[str]:
    """
    生成开场图像，使用预设风格。
    """
    if not opening_quote:
        return None
    try:
        prompt = OPENING_IMAGE_STYLES.get(opening_style)
        if not prompt:
            default_style = next(iter(OPENING_IMAGE_STYLES))
            logger.warning(f"未找到开场图像风格: {opening_style}，使用默认风格: {default_style}")
            prompt = OPENING_IMAGE_STYLES[default_style]
        prompt = str(prompt).strip()

        image_url = text_to_image_doubao(
            prompt=prompt,
            size=image_size,
            model=model
        )

        if not image_url:
            raise ValueError("开场图像生成失败")

        ensure_directory_exists(output_dir)
        image_path = os.path.join(output_dir, "opening.png")
        _download_to_path(image_url, image_path, error_msg="开场图像下载失败")
        logger.info(f"开场图像已保存: {image_path} (风格: {opening_style})")
        print(f"开场图像已保存: {image_path}")
        return image_path
    except Exception as e:
        logger.warning(f"开场图像生成失败: {e}")
        return None


def _generate_single_image(args) -> Dict[str, Any]:
    """
    生成单个图像的辅助函数（用于多线程）
    """
    segment_index, keywords, atmosphere, image_style, model, image_size, output_dir = args
    
    style_part = f"[风格] {image_style}" if image_style else ""
    content_parts: List[str] = []
    content_parts.extend(keywords)
    content_parts.extend(atmosphere)
    content_part = f"[内容] {' | '.join(content_parts)}" if content_parts else ""
    prompt_sections = [part for part in [style_part, content_part] if part]
    final_prompt = "\n".join(prompt_sections)

    print(f"正在生成第{segment_index}段图像...")
    logger.debug(f"第{segment_index}段图像提示词: {final_prompt}")

    for attempt in range(3):
        try:
            image_url = text_to_image_doubao(
                prompt=final_prompt,
                size=image_size,
                model=model
            )
            if image_url:
                image_path = os.path.join(output_dir, f"segment_{segment_index}.png")
                _download_to_path(image_url, image_path, error_msg=f"下载第{segment_index}段图像失败")
                print(f"第{segment_index}段图像已保存: {image_path}")
                logger.info(f"第{segment_index}段图像生成成功: {image_path}")
                return {"success": True, "segment_index": segment_index, "image_path": image_path}
            else:
                if attempt < 2:
                    logger.warning(f"第{segment_index}段图像生成失败，准备重试（第{attempt + 2}/3次）")
                    continue
        except Exception as e:
            error_msg = str(e)
            is_sensitive_error = (
                "OutputImageSensitiveContentDetected" in error_msg or
                "sensitive" in error_msg.lower() or
                "content" in error_msg.lower()
            )
            if attempt < 2:
                if is_sensitive_error:
                    logger.warning(f"第{segment_index}段图像涉及敏感内容，准备重试（第{attempt + 2}/3次）")
                else:
                    logger.warning(f"第{segment_index}段图像生成失败：{error_msg}，准备重试（第{attempt + 2}/3次）")
                continue
            else:
                if is_sensitive_error:
                    logger.warning(f"第{segment_index}段图像生成失败（敏感内容），已跳过。错误：{error_msg}")
                else:
                    logger.warning(f"第{segment_index}段图像生成失败，已跳过。错误：{error_msg}")
                print(f"第{segment_index}段图像生成失败，已跳过")
    
    return {"success": False, "segment_index": segment_index, "image_path": ""}


def generate_images_for_segments(model: str, keywords_data: Dict[str, Any],
                                 image_style_preset: str, image_size: str, output_dir: str) -> Dict[str, Any]:
    """
    为每个段落生成图像（支持多线程并发）
    """
    try:
        try:
            image_style = IMAGE_STYLE_PRESETS.get(
                image_style_preset,
                next(iter(IMAGE_STYLE_PRESETS.values()))
            )
        except Exception:
            image_style = ""
        logger.info(f"使用图像风格: {image_style_preset} -> {image_style}")

        # 准备并发任务参数
        task_args = []
        for i, segment_keywords in enumerate(keywords_data["segments"], 1):
            keywords = segment_keywords.get("keywords", [])
            atmosphere = segment_keywords.get("atmosphere", [])
            task_args.append((i, keywords, atmosphere, image_style, model, image_size, output_dir))

        # 使用线程池并发生成图像
        max_workers = getattr(config, "MAX_CONCURRENT_IMAGE_GENERATION", 3)
        print(f"使用 {max_workers} 个并发线程生成图像...")
        
        image_paths: List[str] = [""] * len(task_args)  # 预分配位置
        failed_segments: List[int] = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_index = {executor.submit(_generate_single_image, args): args[0] for args in task_args}
            
            # 等待任务完成
            for future in concurrent.futures.as_completed(future_to_index):
                result = future.result()
                segment_index = result["segment_index"]
                if result["success"]:
                    image_paths[segment_index - 1] = result["image_path"]
                else:
                    failed_segments.append(segment_index)
                    image_paths[segment_index - 1] = ""

        return {
            "image_paths": image_paths,
            "failed_segments": failed_segments
        }

    except Exception as e:
        raise ValueError(f"图像生成错误: {e}")


def _synthesize_single_voice(args) -> Dict[str, Any]:
    """
    合成单个语音的辅助函数（用于多线程）
    """
    segment_index, content, server, voice, output_dir = args
    
    print(f"正在生成第{segment_index}段语音...")
    
    audio_filename = f"voice_{segment_index}.wav"
    audio_path = os.path.join(output_dir, audio_filename)
    
    try:
        if server == "bytedance":
            success = text_to_audio_bytedance(
                text=content,
                output_filename=audio_path,
                voice=voice
            )
        else:
            return {"success": False, "segment_index": segment_index, "error": f"不支持的TTS服务商: {server}"}
        
        if success:
            print(f"第{segment_index}段语音已保存: {audio_path}")
            return {"success": True, "segment_index": segment_index, "audio_path": audio_path}
        else:
            return {"success": False, "segment_index": segment_index, "error": f"生成第{segment_index}段语音失败"}
    
    except Exception as e:
        return {"success": False, "segment_index": segment_index, "error": str(e)}


def synthesize_voice_for_segments(server: str, voice: str, script_data: Dict[str, Any], output_dir: str) -> List[str]:
    """
    为每个段落合成语音（支持多线程并发）
    """
    try:
        # 准备并发任务参数
        task_args = []
        for segment in script_data["segments"]:
            segment_index = segment["index"]
            content = segment["content"]
            task_args.append((segment_index, content, server, voice, output_dir))

        # 使用线程池并发合成语音
        max_workers = getattr(config, "MAX_CONCURRENT_VOICE_SYNTHESIS", 2)
        print(f"使用 {max_workers} 个并发线程合成语音...")
        
        audio_paths: List[str] = [""] * len(task_args)  # 预分配位置
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_index = {executor.submit(_synthesize_single_voice, args): args[0] for args in task_args}
            
            # 等待任务完成
            for future in concurrent.futures.as_completed(future_to_index):
                result = future.result()
                segment_index = result["segment_index"]
                if result["success"]:
                    audio_paths[segment_index - 1] = result["audio_path"]
                else:
                    error_msg = result.get("error", f"生成第{segment_index}段语音失败")
                    raise ValueError(error_msg)

        # 语音合成完成后，立即导出SRT字幕文件
        print("🎬 开始导出SRT字幕文件...")
        try:
            srt_path = export_srt_subtitles(script_data, audio_paths, output_dir)
            print(f"✅ SRT字幕已保存: {srt_path}")
        except Exception as e:
            print(f"⚠️ SRT字幕导出失败: {e}")  # 非关键功能，失败不中断流程

        return audio_paths

    except Exception as e:
        raise ValueError(f"语音合成错误: {e}")


def export_srt_subtitles(script_data: Dict[str, Any], audio_paths: List[str], voice_dir: str) -> str:
    """
    导出SRT字幕文件到voice文件夹
    
    Args:
        script_data: 脚本数据
        audio_paths: 音频文件路径列表
        voice_dir: voice文件夹路径
    
    Returns:
        str: SRT文件路径
    """
    from moviepy import AudioFileClip
    from core.video_composer import VideoComposer
    
    try:
        # 获取实际音频时长
        segment_durations = []
        for audio_path in audio_paths:
            if os.path.exists(audio_path):
                clip = AudioFileClip(audio_path)
                segment_durations.append(float(clip.duration))
                clip.close()
            else:
                segment_durations.append(0.0)
        
        # 复用VideoComposer的字幕分割逻辑
        composer = VideoComposer()
        subtitle_config = config.SUBTITLE_CONFIG.copy()
        
        # 生成SRT内容
        srt_lines = []
        subtitle_index = 1
        current_time = 0.0
        
        for i, segment in enumerate(script_data["segments"]):
            content = segment["content"]
            duration = segment_durations[i] if i < len(segment_durations) else 0.0
            
            # 分割文本
            subtitle_texts = composer.split_text_for_subtitle(
                content,
                subtitle_config["max_chars_per_line"],
                subtitle_config["max_lines"]
            )
            
            # 计算每行时长
            if len(subtitle_texts) == 0:
                continue
                
            line_durations = []
            if len(subtitle_texts) == 1:
                line_durations = [duration]
            else:
                lengths = [max(1.0, len(t)) for t in subtitle_texts]
                total_len = sum(lengths)
                acc = 0.0
                for idx, length in enumerate(lengths):
                    if idx < len(lengths) - 1:
                        d = duration * (length / total_len)
                        line_durations.append(d)
                        acc += d
                    else:
                        line_durations.append(max(0.0, duration - acc))
            
            # 生成SRT条目
            for subtitle_text, subtitle_duration in zip(subtitle_texts, line_durations):
                start_time = current_time
                end_time = current_time + subtitle_duration
                
                # SRT时间格式
                start_srt = _format_srt_time(start_time)
                end_srt = _format_srt_time(end_time)
                
                srt_lines.append(f"{subtitle_index}")
                srt_lines.append(f"{start_srt} --> {end_srt}")
                srt_lines.append(subtitle_text.strip())
                srt_lines.append("")
                
                subtitle_index += 1
                current_time = end_time
        
        # 写入SRT文件
        project_name = os.path.basename(voice_dir.rstrip('/').rstrip('\\'))
        if project_name == "voice":
            project_name = os.path.basename(os.path.dirname(voice_dir.rstrip('/').rstrip('\\')))
        
        srt_filename = f"{project_name}_subtitles.srt"
        srt_path = os.path.join(voice_dir, srt_filename)
        
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(srt_lines))
        
        return srt_path
        
    except Exception as e:
        raise ValueError(f"SRT字幕导出错误: {e}")


def _format_srt_time(seconds: float) -> str:
    """格式化时间为SRT格式 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


