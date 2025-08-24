"""
智能视频制作系统 - 核心功能模块
包含文档读取、智能处理、图像生成、语音合成、视频制作等功能
"""

from moviepy import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, TextClip, ColorClip, CompositeAudioClip
# MoviePy 2.x: 使用类效果 API
try:
    from moviepy.audio.fx.AudioLoop import AudioLoop  # type: ignore
except Exception:
    AudioLoop = None  # fallback later
from moviepy.audio.fx.MultiplyVolume import MultiplyVolume  # type: ignore
from typing import Optional, Dict, Any, List, Tuple
import requests
import json
import os
import re
import datetime
import ebooklib
from ebooklib import epub
import PyPDF2
import pdfplumber

from prompts import summarize_system_prompt, keywords_extraction_prompt, IMAGE_STYLE_PRESETS
from genai_api import text_to_text, text_to_image_doubao, text_to_audio_bytedance
from config import config
 
from utils import (
    logger, FileProcessingError, APIError,
    log_function_call, ensure_directory_exists, clean_text, 
    validate_file_format
)
from utils import parse_json_robust
import numpy as np

# 统一字体解析：优先使用系统中文字体路径，失败回退到传入名称
def resolve_font_path(preferred: Optional[str]) -> Optional[str]:
    if preferred and os.path.exists(preferred):
        return preferred
    candidate_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/SimHei.ttf",
        "/System/Library/Fonts/Supplemental/SimSun.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode MS.ttf",
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            return path
    return preferred

# 通用下载器：下载二进制内容并保存到指定路径
def download_to_path(url: str, output_path: str, error_msg: str = "下载失败") -> None:
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError(error_msg)
    with open(output_path, 'wb') as f:
        f.write(response.content)

################ Document Reading ################
@log_function_call
def read_document(file_path: str) -> Tuple[str, int]:
    """
    读取EPUB或PDF文档，返回内容和字数
    
    Args:
        file_path: 文档文件路径
    
    Returns:
        Tuple[str, int]: (文档内容, 字数)
    """
    # 验证文件格式
    validate_file_format(file_path, config.SUPPORTED_INPUT_FORMATS)
    
    file_extension = os.path.splitext(file_path)[1].lower()
    
    logger.info(f"开始读取{file_extension.upper()}文件: {os.path.basename(file_path)}")
    
    if file_extension == '.epub':
        return read_epub(file_path)
    elif file_extension == '.pdf':
        return read_pdf(file_path)
    else:
        raise FileProcessingError(f"不支持的文件格式: {file_extension}")

def read_epub(file_path: str) -> Tuple[str, int]:
    """读取EPUB文件内容"""
    try:
        book = epub.read_epub(file_path)
        content_parts = []
        
        logger.debug("正在提取EPUB文件中的文本内容...")
        
        # 获取所有文本内容
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                content = item.get_content().decode('utf-8')
                # 清理HTML标签和格式化文本
                content = clean_text(content)
                if content:
                    content_parts.append(content)
        
        if not content_parts:
            raise FileProcessingError("EPUB文件中未找到可读取的文本内容")
        
        full_content = ' '.join(content_parts)
        word_count = len(full_content)
        
        logger.info(f"EPUB文件读取成功，总字数: {word_count:,}字")
        return full_content, word_count
    
    except Exception as e:
        logger.error(f"读取EPUB文件失败: {str(e)}")
        raise FileProcessingError(f"读取EPUB文件失败: {str(e)}")

def read_pdf(file_path: str) -> Tuple[str, int]:
    """读取PDF文件内容"""
    try:
        content_parts = []
        
        logger.debug("正在使用pdfplumber提取PDF文本...")
        
        # 先尝试pdfplumber（更准确的文本提取）
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    content_parts.append(text)
                    logger.debug(f"已提取第{i}页内容，字符数: {len(text)}")
        
        # 如果pdfplumber没有提取到内容，尝试PyPDF2
        if not content_parts:
            logger.debug("pdfplumber未提取到内容，尝试使用PyPDF2...")
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for i, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text()
                    if text:
                        content_parts.append(text)
                        logger.debug(f"已提取第{i}页内容，字符数: {len(text)}")
        
        if not content_parts:
            raise FileProcessingError("无法从PDF文件中提取文本内容，可能是扫描版PDF")
        
        full_content = ' '.join(content_parts)
        # 清理文本
        full_content = clean_text(full_content)
        word_count = len(full_content)
        
        logger.info(f"PDF文件读取成功，总字数: {word_count:,}字")
        return full_content, word_count
    
    except Exception as e:
        logger.error(f"读取PDF文件失败: {str(e)}")
        raise FileProcessingError(f"读取PDF文件失败: {str(e)}")

################ Intelligent Summarization ################
def intelligent_summarize(server: str, model: str, content: str, target_length: int, num_segments: int) -> Dict[str, Any]:
    """
    智能缩写 - 第一次LLM处理
    将长篇内容压缩为指定长度的口播稿
    """
    try:
        user_message = f"""请将以下内容智能压缩为{target_length}字的口播稿，分成{num_segments}段，每段约{target_length//num_segments}字。

原文内容：
{content}

要求：
1. 保持内容的核心信息和逻辑结构
2. 语言要适合口播，自然流畅
3. 分成{num_segments}段，每段独立完整
4. 总字数控制在{target_length}字左右
"""
        
        output = text_to_text(
            server=server, 
            model=model, 
            prompt=user_message, 
            system_message=summarize_system_prompt, 
            max_tokens=4096, 
            temperature=0.7
        )
        
        if output is None:
            raise ValueError("未能从 API 获取响应。")
        
        # 鲁棒解析（先常规，失败则修复）
        parsed_content = parse_json_robust(output)
        
        # 验证必需字段（golden_quote 为可选）
        required_keys = ["title", "segments"]
        if not all(key in parsed_content for key in required_keys):
            missing_keys = [key for key in required_keys if key not in parsed_content]
            raise ValueError(f"生成的 JSON 缺少必需的 Key: {', '.join(missing_keys)}")
        
        # 添加系统字段
        total_length = sum(len(segment['content']) for segment in parsed_content['segments'])
        
        enhanced_data = {
            "title": parsed_content["title"],
            "golden_quote": parsed_content.get("golden_quote", ""),
            "total_length": total_length,
            "target_segments": num_segments,
            "actual_segments": len(parsed_content["segments"]),
            "created_time": datetime.datetime.now().isoformat(),
            "model_info": {
                "llm_server": server,
                "llm_model": model,
                "generation_type": "script_generation"
            },
            "segments": []
        }
        
        # 处理每个段落，添加详细信息
        for i, segment in enumerate(parsed_content["segments"], 1):
            content_text = segment["content"]
            length = len(content_text)
            # 使用配置的语速估算播放时长（每分钟字数）
            wpm = int(getattr(config, "SPEECH_SPEED_WPM", 300))
            estimated_duration = length / max(1, wpm) * 60
            
            enhanced_data["segments"].append({
                "index": i,
                "content": content_text,
                "length": length,
                "estimated_duration": round(estimated_duration, 1)
            })
        
        return enhanced_data
    
    except json.JSONDecodeError:
        raise ValueError("解析 JSON 输出失败")
    except Exception as e:
        raise ValueError(f"智能缩写处理错误: {e}")

################ Keywords Extraction ################
def extract_keywords(server: str, model: str, script_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    关键词提取 - 第二次LLM处理
    为每个段落提取关键词和氛围词
    """
    try:
        segments_text = []
        for segment in script_data["segments"]:
            segments_text.append(f"第{segment['index']}段: {segment['content']}")
        
        user_message = f"""请为以下每个段落提取关键词和氛围词，用于图像生成：

{chr(10).join(segments_text)}
"""
        
        output = text_to_text(
            server=server,
            model=model,
            prompt=user_message,
            system_message=keywords_extraction_prompt,
            max_tokens=4096,
            temperature=0.5
        )
        
        if output is None:
            raise ValueError("未能从 API 获取响应。")
        
        # 鲁棒解析（先常规，失败则修复）
        keywords_data = parse_json_robust(output)
        
        # 验证格式
        if "segments" not in keywords_data:
            raise ValueError("关键词数据格式错误：缺少segments字段")
        
        # 确保段落数量匹配
        if len(keywords_data["segments"]) != len(script_data["segments"]):
            raise ValueError("关键词段落数量与口播稿不匹配")
        
        # 添加模型信息
        keywords_data["model_info"] = {
            "llm_server": server,
            "llm_model": model,
            "generation_type": "keywords_extraction"
        }
        keywords_data["created_time"] = datetime.datetime.now().isoformat()
        
        return keywords_data
    
    except json.JSONDecodeError:
        raise ValueError("解析关键词 JSON 输出失败")
    except Exception as e:
        raise ValueError(f"关键词提取错误: {e}")

################ Image Generation ################
def generate_opening_image(server: str, model: str, keywords_data: Dict[str, Any],
                           image_style_preset: str, image_size: str, output_dir: str) -> Optional[str]:
    """
    基于关键词数据中的 opening_image 生成开场图像（简洁抽象）。

    仅消费 opening_image 中的两类字段：
      - keywords: 具象可视化的画面元素
      - atmosphere: 抽象氛围/风格词（强调高对比度、强烈冲击等）

    返回生成的开场图像路径；若缺少所需字段则返回 None。
    """
    try:
        opening = (keywords_data or {}).get("opening_image") or {}
        if not isinstance(opening, dict):
            return None

        # 仅消费 keywords / atmosphere
        keywords = opening.get("keywords", []) or []
        atmosphere = opening.get("atmosphere", []) or []

        # 基础风格：极简、抽象
        minimalist_style = get_image_style("minimalist")
        base_style_parts: List[str] = [minimalist_style, "简洁抽象", "留白", "干净构图"]

        # 强化氛围默认值（若未覆盖）
        emphasis = ["高对比度", "强烈视觉冲击", "戏剧性光影"]
        # 合并 atmosphere 与默认强调词，保序去重
        atmo_merged: List[str] = []
        for item in list(atmosphere) + emphasis:
            if item and item not in atmo_merged:
                atmo_merged.append(item)

        prompt_parts: List[str] = []
        prompt_parts.extend(base_style_parts)
        if isinstance(keywords, list):
            prompt_parts.extend(keywords[:8])
        prompt_parts.extend(atmo_merged[:6])
        prompt_parts.append("高质量，专业影像")

        final_prompt = ", ".join([p for p in prompt_parts if p])

        # 调用豆包图像生成API
        image_url = text_to_image_doubao(
            prompt=final_prompt,
            size=image_size,
            model=model
        )

        if not image_url:
            raise ValueError("开场图像生成失败")

        # 下载并保存
        ensure_directory_exists(output_dir)
        image_path = os.path.join(output_dir, "opening.png")
        download_to_path(image_url, image_path, error_msg="开场图像下载失败")
        print(f"开场图像已保存: {image_path}")
        return image_path
    except Exception as e:
        logger.warning(f"开场图像生成失败: {e}")
        return None
def generate_images_for_segments(server: str, model: str, keywords_data: Dict[str, Any], 
                                image_style_preset: str, image_size: str, output_dir: str) -> List[str]:
    """
    为每个段落生成图像
    
    Args:
        server: 图像生成服务商
        model: 图像生成模型
        keywords_data: 关键词数据
        image_style_preset: 图像风格预设名称
        image_size: 图像尺寸
        output_dir: 输出目录
    
    Returns:
        List[str]: 生成图像的文件路径列表
    """
    try:
        image_paths = []
        
        # 获取图像风格字符串
        image_style = get_image_style(image_style_preset)
        logger.info(f"使用图像风格: {image_style_preset} -> {image_style}")
        
        for i, segment_keywords in enumerate(keywords_data["segments"], 1):
            keywords = segment_keywords.get("keywords", [])
            atmosphere = segment_keywords.get("atmosphere", [])
            
            # 构建图像提示词
            prompt_parts = []
            if image_style:
                prompt_parts.append(image_style)
            
            prompt_parts.extend(keywords)
            prompt_parts.extend(atmosphere)
            prompt_parts.append("高质量，细节丰富，专业摄影")
            
            final_prompt = ", ".join(prompt_parts)
            
            print(f"正在生成第{i}段图像...")
            
            # 调用豆包图像生成API
            image_url = text_to_image_doubao(
                prompt=final_prompt,
                size=image_size,
                model=model
            )
            
            if image_url:
                # 下载并保存图像
                image_path = os.path.join(output_dir, f"segment_{i}.png")
                download_to_path(image_url, image_path, error_msg=f"下载第{i}段图像失败")
                image_paths.append(image_path)
                print(f"第{i}段图像已保存: {image_path}")
            else:
                raise ValueError(f"生成第{i}段图像失败")
        
        return image_paths
    
    except Exception as e:
        raise ValueError(f"图像生成错误: {e}")

################ Voice Synthesis ################
def synthesize_voice_for_segments(server: str, voice: str, script_data: Dict[str, Any], output_dir: str) -> List[str]:
    """
    为每个段落合成语音
    """
    try:
        audio_paths = []
        
        for segment in script_data["segments"]:
            segment_index = segment["index"]
            content = segment["content"]
            
            print(f"正在生成第{segment_index}段语音...")
            
            # 生成语音文件路径：voice_{序号}.wav
            audio_filename = f"voice_{segment_index}.wav"
            audio_path = os.path.join(output_dir, audio_filename)
            
            # 调用语音合成API - 根据语音音色智能选择接口
            if server == "bytedance":
                # 使用字节语音合成大模型接口
                success = text_to_audio_bytedance(
                    text=content,
                    output_filename=audio_path,
                    voice=voice
                )
            else:
                raise ValueError(f"不支持的TTS服务商: {server}")
            
            if success:
                audio_paths.append(audio_path)
                print(f"第{segment_index}段语音已保存: {audio_path}")
            else:
                raise ValueError(f"生成第{segment_index}段语音失败")
        
        return audio_paths
    
    except Exception as e:
        raise ValueError(f"语音合成错误: {e}")

################ Video Composition ################
def compose_final_video(image_paths: List[str], audio_paths: List[str], output_path: str, 
                       script_data: Dict[str, Any] = None, enable_subtitles: bool = False,
                       bgm_audio_path: Optional[str] = None, bgm_volume: float = 0.15,
                       narration_volume: float = 1.0,
                       opening_image_path: Optional[str] = None,
                       opening_golden_quote: Optional[str] = None,
                       opening_narration_audio_path: Optional[str] = None) -> str:
    """
    合成最终视频
    
    Args:
        image_paths: 图像文件路径列表
        audio_paths: 音频文件路径列表
        output_path: 输出视频路径
        script_data: 脚本数据，用于生成字幕
        enable_subtitles: 是否启用字幕
    
    Returns:
        str: 输出视频路径
    """
    try:
        if len(image_paths) != len(audio_paths):
            raise ValueError("图像文件数量与音频文件数量不匹配")
        
        video_clips = []
        audio_clips = []
        
        # 可选：创建开场片段（图像 + 居中金句 + 可选开场口播）
        # 开场时长逻辑：若提供开场口播 => 时长=口播时长+OPENING_HOLD_AFTER_NARRATION_SECONDS；否则无开场
        opening_seconds = 0.0
        opening_voice_clip = None
        # 若提供开场口播音频，则以“音频长度 + 停留时长”作为总开场时长
        try:
            if opening_narration_audio_path and os.path.exists(opening_narration_audio_path):
                opening_voice_clip = AudioFileClip(opening_narration_audio_path)
                hold_after = float(getattr(config, "OPENING_HOLD_AFTER_NARRATION_SECONDS", 2.0))
                opening_seconds = float(opening_voice_clip.duration) + max(0.0, hold_after)
        except Exception as _oaerr:
            logger.warning(f"开场口播音频加载失败: {_oaerr}，将退回固定时长开场")
            opening_voice_clip = None
        
        if opening_image_path and os.path.exists(opening_image_path) and opening_seconds > 1e-3:
            try:
                print("正在创建开场片段…")
                opening_base = ImageClip(opening_image_path).with_duration(opening_seconds)

                # 解析可用字体（参考字幕配置）
                subtitle_config = config.SUBTITLE_CONFIG.copy()

                resolved_font = resolve_font_path(subtitle_config.get("font_family"))
                quote_text = (opening_golden_quote or "").strip()
                if quote_text:
                    # 读取开场金句样式（带默认值回退）
                    quote_style = getattr(config, "OPENING_QUOTE_STYLE", {}) or {}
                    base_font = int(config.SUBTITLE_CONFIG.get("font_size", 36))
                    scale = float(quote_style.get("font_scale", 1.3))
                    font_size = int(quote_style.get("font_size", base_font * scale))
                    text_color = quote_style.get("color", config.SUBTITLE_CONFIG.get("color", "white"))
                    stroke_color = quote_style.get("stroke_color", config.SUBTITLE_CONFIG.get("stroke_color", "black"))
                    stroke_width = int(quote_style.get("stroke_width", max(3, int(config.SUBTITLE_CONFIG.get("stroke_width", 3)))))
                    pos = quote_style.get("position", ("center", "center"))

                    # 开场金句换行：按 max_chars_per_line 和 max_lines 控制
                    try:
                        max_chars = int(quote_style.get("max_chars_per_line", 18))
                        max_q_lines = int(quote_style.get("max_lines", 4))
                        # 复用字幕拆分逻辑，严格按每行字符数限制
                        candidate_lines = split_text_for_subtitle(quote_text, max_chars, max_q_lines)
                        wrapped_quote = "\n".join(candidate_lines[:max_q_lines]) if candidate_lines else quote_text
                    except Exception:
                        wrapped_quote = quote_text

                    # 覆盖字体解析（优先采用 OPENING_QUOTE_STYLE.font_family）
                    font_override = quote_style.get("font_family")
                    if font_override and os.path.exists(font_override):
                        resolved_font = font_override

                    # 行间距与字间距（MoviePy 2.x 无直接参数，这里通过逐行排版+空格近似实现）
                    line_spacing_px = int(quote_style.get("line_spacing", 0))
                    letter_spaces = int(quote_style.get("letter_spacing", 0))

                    def _apply_letter_spacing(s: str, n: int) -> str:
                        if n <= 0 or not s:
                            return s
                        return (" " * n).join(list(s))

                    def _make_text_clip(text: str) -> TextClip:
                        return TextClip(
                            text=text,
                            font_size=font_size,
                            color=text_color,
                            font=resolved_font or config.SUBTITLE_CONFIG.get("font_family"),
                            stroke_color=stroke_color,
                            stroke_width=stroke_width
                        )

                    try:
                        # 预处理字间距
                        lines = wrapped_quote.split("\n") if wrapped_quote else []
                        lines = [_apply_letter_spacing(ln, letter_spaces) for ln in lines] if lines else []

                        # 无需自定义行距：直接用单 TextClip（多行通过 \n 渲染）
                        if line_spacing_px <= 0 or not (isinstance(pos, tuple) and pos == ("center", "center")):
                            processed = "\n".join(lines) if lines else wrapped_quote
                            text_clip = _make_text_clip(processed).with_position(pos).with_duration(opening_seconds)
                            opening_clip = CompositeVideoClip([opening_base, text_clip])
                        else:
                            # 居中且需要行距：逐行排布
                            video_w, video_h = opening_base.size
                            line_clips: List[Any] = [_make_text_clip(ln) for ln in lines] if lines else []
                            if line_clips:
                                total_h = sum(c.h for c in line_clips) + line_spacing_px * (len(line_clips) - 1)
                                y_start = max(0, (video_h - total_h) // 2)
                                y_cur = y_start
                                placed: List[Any] = [opening_base]
                                for c in line_clips:
                                    placed.append(c.with_position(("center", y_cur)).with_duration(opening_seconds))
                                    y_cur += c.h + line_spacing_px
                                opening_clip = CompositeVideoClip(placed)
                            else:
                                text_clip = _make_text_clip(wrapped_quote).with_position(pos).with_duration(opening_seconds)
                                opening_clip = CompositeVideoClip([opening_base, text_clip])
                    except Exception:
                        text_clip = _make_text_clip(wrapped_quote).with_position(pos).with_duration(opening_seconds)
                        opening_clip = CompositeVideoClip([opening_base, text_clip])
                else:
                    opening_clip = opening_base

                # 绑定开场口播音频（如存在）
                if opening_voice_clip is not None:
                    try:
                        opening_clip = opening_clip.with_audio(opening_voice_clip)
                    except Exception as _bindaerr:
                        logger.warning(f"为开场片段绑定音频失败: {_bindaerr}")

                video_clips.append(opening_clip)
            except Exception as e:
                logger.warning(f"开场片段生成失败: {e}，将跳过开场")

        # 为每个段落创建视频片段
        for i, (image_path, audio_path) in enumerate(zip(image_paths, audio_paths)):
            print(f"正在处理第{i+1}段视频...")
            
            # 加载音频获取时长
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration
            
            # 创建图像剪辑，设置持续时间为音频长度 (MoviePy 2.x 使用 with_duration)
            image_clip = ImageClip(image_path).with_duration(duration)
            
            # 组合图像和音频 (MoviePy 2.x 使用 with_audio)
            video_clip = image_clip.with_audio(audio_clip)
            video_clips.append(video_clip)
            audio_clips.append(audio_clip)
        
        # 连接所有视频片段
        print("正在合成最终视频...")
        # 使用 compose 方式合并，避免音频轨丢失或不同尺寸导致的问题
        final_video = concatenate_videoclips(video_clips, method="compose")
        
        # 添加字幕（如果启用）
        # 生效的字幕开关需同时满足：运行时参数与全局配置均为 True
        effective_subtitles = bool(enable_subtitles) and bool(getattr(config, "SUBTITLE_CONFIG", {}).get("enabled", True))
        if effective_subtitles and script_data:
            print("正在添加字幕...")
            try:
                # 传入最终视频尺寸，便于字幕计算边距/背景
                subtitle_config = config.SUBTITLE_CONFIG.copy()
                subtitle_config["video_size"] = final_video.size
                # 传入每段音频真实时长用于精准对齐
                subtitle_config["segment_durations"] = [ac.duration for ac in audio_clips]
                # 开场字幕偏移：让第一段字幕从开场片段之后开始
                subtitle_config["offset_seconds"] = opening_seconds
                subtitle_clips = create_subtitle_clips(script_data, subtitle_config)
                if subtitle_clips:
                    # 将字幕与视频合成
                    final_video = CompositeVideoClip([final_video] + subtitle_clips)
                    print(f"已添加 {len(subtitle_clips)} 个字幕剪辑")
                else:
                    print("未生成任何字幕剪辑")
            except Exception as e:
                logger.warning(f"添加字幕失败: {str(e)}，继续生成无字幕视频")

        # 调整口播音量（在与BGM混音前）——MoviePy 2.x 使用 MultiplyVolume
        try:
            if final_video.audio is not None and narration_volume is not None:
                narration_audio = final_video.audio
                if isinstance(narration_volume, (int, float)) and abs(float(narration_volume) - 1.0) > 1e-9:
                    narration_audio = narration_audio.with_effects([MultiplyVolume(float(narration_volume))])
                    final_video = final_video.with_audio(narration_audio)
                    print(f"🔊 口播音量调整为: {float(narration_volume)}")
        except Exception as e:
            logger.warning(f"口播音量调整失败: {str(e)}，将使用原始音量")

        # 在视频开头应用视觉渐显（从黑到正常）
        try:
            fade_in_seconds = float(getattr(config, "OPENING_FADEIN_SECONDS", 0.0))
            if fade_in_seconds > 1e-3:
                def _fade_in_frame(gf, t):
                    try:
                        alpha = min(1.0, max(0.0, float(t) / float(fade_in_seconds)))
                    except Exception:
                        alpha = 1.0
                    return alpha * gf(t)
                try:
                    final_video = final_video.transform(_fade_in_frame, keep_duration=True)
                    print(f"🎬 已添加开场渐显 {fade_in_seconds}s")
                except Exception as _ferr:
                    logger.warning(f"开场渐显应用失败: {_ferr}")
        except Exception as e:
            logger.warning(f"读取开场渐显配置失败: {e}")
        
        # 在片尾追加 config.ENDING_FADE_SECONDS 秒静帧并渐隐（仅画面，无口播音频）
        try:
            tail_seconds = float(getattr(config, "ENDING_FADE_SECONDS", 2.5))
            if isinstance(image_paths, list) and len(image_paths) > 0 and tail_seconds > 1e-3:
                last_image_path = image_paths[-1]
                tail_clip = ImageClip(last_image_path).with_duration(tail_seconds)
                # 使用 transform 实现到黑场的线性渐隐
                def _fade_frame(gf, t):
                    try:
                        alpha = max(0.0, 1.0 - float(t) / float(tail_seconds))
                    except Exception:
                        alpha = 0.0
                    return alpha * gf(t)
                try:
                    tail_clip = tail_clip.transform(_fade_frame, keep_duration=True)
                except Exception:
                    pass
                final_video = concatenate_videoclips([final_video, tail_clip], method="compose")
                print(f"🎬 已添加片尾静帧 {tail_seconds}s 并渐隐")
        except Exception as tail_err:
            logger.warning(f"片尾静帧添加失败: {tail_err}，将继续生成无片尾渐隐的视频")
        
        # 可选：叠加背景音乐（与口播混音）
        bgm_clip = None
        try:
            if bgm_audio_path and os.path.exists(bgm_audio_path):
                print(f"🎵 开始处理背景音乐: {bgm_audio_path}")
                bgm_clip = AudioFileClip(bgm_audio_path)
                print(f"🎵 BGM加载成功，时长: {bgm_clip.duration:.2f}秒")
                
                # 调整 BGM 音量（MoviePy 2.x MultiplyVolume）
                try:
                    if isinstance(bgm_volume, (int, float)) and abs(float(bgm_volume) - 1.0) > 1e-9:
                        bgm_clip = bgm_clip.with_effects([MultiplyVolume(float(bgm_volume))])
                        print(f"🎵 BGM音量调整为: {float(bgm_volume)}")
                except Exception:
                    print("⚠️ BGM音量调整失败，使用原音量")
                    pass
                
                # 循环或裁剪至视频总时长（优先使用 MoviePy 2.x 的 AudioLoop）
                try:
                    target_duration = final_video.duration
                    print(f"🎵 视频总时长: {target_duration:.2f}秒，BGM时长: {bgm_clip.duration:.2f}秒")
                    if AudioLoop is not None:
                        # 使用 2.x 的 AudioLoop 效果类
                        bgm_clip = bgm_clip.with_effects([AudioLoop(duration=target_duration)])
                        print(f"🎵 BGM长度适配完成（AudioLoop），最终时长: {bgm_clip.duration:.2f}秒")
                    else:
                        # 简化的回退：直接裁剪到目标时长（避免复杂手动循环）
                        if hasattr(bgm_clip, "with_duration"):
                            bgm_clip = bgm_clip.with_duration(min(bgm_clip.duration, target_duration))
                            print("⚠️ AudioLoop 不可用，已将BGM裁剪到目标时长")
                        else:
                            raise RuntimeError("AudioLoop 不可用，且不支持 with_duration")

                except Exception as loop_err:
                    print(f"⚠️ 背景音乐长度适配失败: {loop_err}，将不添加BGM继续生成")
                    logger.warning(f"背景音乐循环/裁剪失败: {loop_err}，将不添加BGM继续生成")
                    bgm_clip = None
                    
                # 合成复合音频
                if bgm_clip is not None:
                    print("🎵 开始合成背景音乐和口播音频")
                    # 通用线性淡出增益函数（用于片尾淡出）
                    def _linear_fade_out_gain(total: float, tail: float):
                        cutoff = max(0.0, total - tail)
                        def _gain_any(t_any):
                            import numpy as _np
                            def _scalar(ts: float) -> float:
                                if ts <= cutoff:
                                    return 1.0
                                if ts >= total:
                                    return 0.0
                                return max(0.0, 1.0 - (ts - cutoff) / tail)
                            if hasattr(t_any, "__len__"):
                                return _np.array([_scalar(float(ts)) for ts in t_any])
                            return _scalar(float(t_any))
                        return _gain_any
                    if final_video.audio is not None:
                        # 可选：自动 Ducking，根据口播包络动态压低 BGM（MoviePy 2.x 通过 transform 实现时间变增益）
                        try:
                            if getattr(config, "AUDIO_DUCKING_ENABLED", False):
                                strength = float(getattr(config, "AUDIO_DUCKING_STRENGTH", 0.7))
                                smooth_sec = float(getattr(config, "AUDIO_DUCKING_SMOOTH_SECONDS", 0.12))
                                total_dur = float(final_video.duration)
                                # 采样频率（包络计算），20Hz 足够平滑且开销低
                                env_fps = 20.0
                                num_samples = max(2, int(total_dur * env_fps) + 1)
                                times = np.linspace(0.0, total_dur, num_samples)
                                # 估算口播瞬时幅度（绝对值，通道取均值）
                                amp = np.zeros_like(times)
                                for i, t in enumerate(times):
                                    try:
                                        frame = final_video.audio.get_frame(float(min(max(0.0, t), total_dur - 1e-6)))
                                        # frame 形如 [L, R]
                                        amp[i] = float(np.mean(np.abs(frame)))
                                    except Exception:
                                        amp[i] = 0.0
                                # 平滑（简单滑动平均窗口）
                                win = max(1, int(smooth_sec * env_fps))
                                if win > 1:
                                    kernel = np.ones(win, dtype=float) / win
                                    amp = np.convolve(amp, kernel, mode="same")
                                # 归一化
                                max_amp = float(np.max(amp)) if np.max(amp) > 1e-8 else 1.0
                                env = amp / max_amp
                                # 计算 duck 增益曲线：口播强 -> BGM 更低
                                gains = 1.0 - strength * env
                                gains = np.clip(gains, 0.0, 1.0)
                                # 构建时间变增益函数（支持标量/向量 t）
                                def _gain_lookup(t_any):
                                    import numpy as _np
                                    def _lookup_scalar(ts: float) -> float:
                                        if ts <= 0.0:
                                            return float(gains[0])
                                        if ts >= total_dur:
                                            return float(gains[-1])
                                        idx = int(ts * env_fps)
                                        if idx < 0:
                                            idx = 0
                                        if idx >= gains.shape[0]:
                                            idx = gains.shape[0] - 1
                                        return float(gains[idx])
                                    if hasattr(t_any, "__len__"):
                                        return _np.array([_lookup_scalar(float(ts)) for ts in t_any])
                                    return _lookup_scalar(float(t_any))

                                # 应用时间变增益到 BGM（使用 transform），注意多声道广播维度
                                bgm_clip = bgm_clip.transform(
                                    lambda gf, t: (
                                        (_gain_lookup(t)[:, None] if hasattr(t, "__len__") else _gain_lookup(t))
                                        * gf(t)
                                    ),
                                    keep_duration=True,
                                )
                                print(f"🎚️ 已启用自动Ducking（strength={strength}, smooth={smooth_sec}s）")
                        except Exception as duck_err:
                            logger.warning(f"自动Ducking失败: {duck_err}，将使用恒定音量BGM")
                        # 在片尾对 BGM 做淡出（不影响口播，因为尾段无口播）
                        try:
                            total_dur = float(final_video.duration)
                            fade_tail = float(getattr(config, "ENDING_FADE_SECONDS", 2.5))
                            fade_gain = _linear_fade_out_gain(total_dur, fade_tail)
                            bgm_clip = bgm_clip.transform(
                                lambda gf, t: ((fade_gain(t)[:, None]) if hasattr(t, "__len__") else fade_gain(t)) * gf(t),
                                keep_duration=True,
                            )
                            print(f"🎚️ 已添加BGM片尾{fade_tail}s淡出")
                        except Exception as _fade_err:
                            logger.warning(f"BGM淡出应用失败: {_fade_err}")
                        mixed_audio = CompositeAudioClip([final_video.audio, bgm_clip])
                        print("🎵 BGM与口播音频合成完成")
                    else:
                        # 无口播，仅 BGM；同样添加片尾淡出
                        try:
                            total_dur = float(final_video.duration)
                            fade_tail = float(getattr(config, "ENDING_FADE_SECONDS", 2.5))
                            fade_gain = _linear_fade_out_gain(total_dur, fade_tail)
                            bgm_clip = bgm_clip.transform(
                                lambda gf, t: ((fade_gain(t)[:, None]) if hasattr(t, "__len__") else fade_gain(t)) * gf(t),
                                keep_duration=True,
                            )
                            print(f"🎚️ 已添加BGM片尾{fade_tail}s淡出")
                        except Exception as _fade_err:
                            logger.warning(f"BGM淡出应用失败: {_fade_err}")
                        mixed_audio = CompositeAudioClip([bgm_clip])
                        print("🎵 仅添加BGM音频（无口播音频）")
                    final_video = final_video.with_audio(mixed_audio)
                    print("🎵 背景音乐添加成功！")
                else:
                    print("❌ BGM处理失败，生成无背景音乐视频")
            else:
                if bgm_audio_path:
                    print(f"⚠️ 背景音乐文件不存在: {bgm_audio_path}")
                else:
                    print("ℹ️ 未指定背景音乐文件")
        except Exception as e:
            print(f"❌ 背景音乐处理异常: {str(e)}")
            logger.warning(f"背景音乐处理失败: {str(e)}，将继续生成无背景音乐的视频")

        # 输出最终视频：使用简单进度条，避免某些终端环境下 tqdm 多行滚动刷屏
        moviepy_logger = 'bar'

        final_video.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            logger=moviepy_logger
        )
        
        # 释放资源
        for clip in video_clips:
            clip.close()
        for aclip in audio_clips:
            aclip.close()
        final_video.close()
        if bgm_clip is not None:
            try:
                bgm_clip.close()
            except Exception:
                pass
        if 'opening_voice_clip' in locals() and opening_voice_clip is not None:
            try:
                opening_voice_clip.close()
            except Exception:
                pass
        
        print(f"最终视频已保存: {output_path}")
        return output_path
    
    except Exception as e:
        raise ValueError(f"视频合成错误: {e}")

################ Style Helper Functions ################
def get_image_style(style_name: str = "cinematic") -> str:
    """
    获取图像风格字符串
    
    Args:
        style_name: 风格名称，如果不存在则返回第一个风格
    
    Returns:
        str: 图像风格描述字符串
    """
    return IMAGE_STYLE_PRESETS.get(style_name, list(IMAGE_STYLE_PRESETS.values())[0])

def split_text_for_subtitle(text: str, max_chars_per_line: int = 20, max_lines: int = 2) -> List[str]:
    """
    将长文本分割为适合字幕显示的短句，严格按每行字符数限制
    
    Args:
        text: 原始文本
        max_chars_per_line: 每行最大字符数
        max_lines: 最大行数
    
    Returns:
        List[str]: 分割后的字幕文本列表
    """
    # 如果文本很短，直接按字符数切分
    if len(text) <= max_chars_per_line:
        return [text]
    
    # 按句号、问号、感叹号分割（含中英文）
    sentences = []
    current = ""
    for char in text:
        current += char
        # 一级分句：按中英文重停顿标点切分（。！？；.!?）
        if char in "。！？；.!?":
            sentences.append(current.strip())
            current = ""
    
    if current.strip():
        sentences.append(current.strip())
    
    # 如果没有句子分隔符，强制按字符数切分
    if not sentences:
        result = []
        for i in range(0, len(text), max_chars_per_line):
            result.append(text[i:i + max_chars_per_line])
        return result
    
    # 组合句子，严格按每行字符数限制
    result = []
    current_subtitle = ""
    
    for sentence in sentences:
        # 如果单个句子超过每行限制：先尝试按次级标点（，、）细分，再必要时硬切
        if len(sentence) > max_chars_per_line:
            if current_subtitle:
                result.append(current_subtitle)
                current_subtitle = ""

            # 二级分句函数：按（，、、“”、‘ ’、《 》以及英文逗号, 和 ASCII 单引号'）切分并保留标点（不处理 ASCII 双引号）
            def _split_by_secondary(s: str) -> List[str]:
                tokens = re.split(r'([，、,“”‘’《》，,])', s)
                chunks: List[str] = []
                buf = ""
                in_ascii_single = False

                OPENERS = ("“", "‘", "《")
                CLOSERS = ("”", "’", "》")
                COMMAS = ("，", "、", ",")

                def flush_buf() -> None:
                    nonlocal buf
                    if buf:
                        chunks.append(buf)
                        buf = ""

                def start_new_with(tok: str) -> None:
                    nonlocal buf
                    flush_buf()
                    buf = tok

                def end_with(tok: str) -> None:
                    nonlocal buf
                    if buf:
                        buf += tok
                        flush_buf()
                    elif chunks:
                        chunks[-1] += tok
                    else:
                        # 若不存在上一段，则临时放入缓冲，避免功能变化
                        buf = tok

                for t in tokens:
                    if not t:
                        continue

                    if t in OPENERS:
                        start_new_with(t)
                        continue

                    if t in CLOSERS:
                        end_with(t)
                        continue

                    if t == "'":
                        if not in_ascii_single:
                            start_new_with(t)
                            in_ascii_single = True
                        else:
                            end_with(t)
                            in_ascii_single = False
                        continue

                    if t in COMMAS:
                        end_with(t)
                        continue

                    # 普通文本
                    buf += t

                if buf:
                    chunks.append(buf)
                return chunks

            parts = _split_by_secondary(sentence)

            if len(parts) == 1:
                # 无（，、）可用，回退到按字符数硬切
                for i in range(0, len(sentence), max_chars_per_line):
                    result.append(sentence[i:i + max_chars_per_line])
            else:
                # 使用二级分句，尽量合并到不超过上限的行
                buf = ""
                for p in parts:
                    if len(p) <= max_chars_per_line:
                        if not buf:
                            buf = p
                        elif len(buf + p) <= max_chars_per_line:
                            buf += p
                        else:
                            result.append(buf)
                            buf = p
                    else:
                        # 次级片段仍然过长，先输出已有缓冲，再硬切
                        if buf:
                            result.append(buf)
                            buf = ""
                        for i in range(0, len(p), max_chars_per_line):
                            result.append(p[i:i + max_chars_per_line])
                if buf:
                    result.append(buf)
        elif not current_subtitle:
            current_subtitle = sentence
        elif len(current_subtitle + sentence) <= max_chars_per_line:
            current_subtitle += sentence
        else:
            result.append(current_subtitle)
            current_subtitle = sentence
    
    if current_subtitle:
        result.append(current_subtitle)
    
    return result

def create_subtitle_clips(script_data: Dict[str, Any], subtitle_config: Dict[str, Any] = None) -> List[TextClip]:
    """
    创建字幕剪辑列表
    
    Args:
        script_data: 脚本数据，包含segments信息
        subtitle_config: 字幕配置，如果为None则使用默认配置
    
    Returns:
        List[TextClip]: 字幕剪辑列表
    """
    if subtitle_config is None:
        from config import config
        subtitle_config = config.SUBTITLE_CONFIG.copy()
    
    subtitle_clips = []
    current_time = float(subtitle_config.get("offset_seconds", 0.0) if isinstance(subtitle_config, dict) else 0.0)
    
    logger.info("开始创建字幕剪辑...")
    
    # 解析可用字体（优先使用系统中的中文字体文件路径，避免中文缺字）
    def _resolve_font_path(preferred: Optional[str]) -> Optional[str]:
        return resolve_font_path(preferred)

    resolved_font = _resolve_font_path(subtitle_config.get("font_family"))
    if not resolved_font:
        logger.warning("未能解析到可用中文字体，可能导致字幕无法显示中文字符。建议在 config.SUBTITLE_CONFIG.font_family 指定字体文件路径。")

    # 读取视频尺寸（用于计算底部边距和背景条）
    video_size = subtitle_config.get("video_size", (1280, 720))
    video_width, video_height = video_size

    segment_durations = subtitle_config.get("segment_durations", [])

    # 定义需要替换为空格的标点集合（中英文常见标点）
    # 中文引号“”‘’与书名号《》保留；英文双引号直接替换为双空格；其他标点替换为双空格
    # 使用 + 将连续标点视作一个整体，避免产生过多空白
    punctuation_pattern = r"[-.,!?;:\"，。！？；：（）()\[\]{}【】—…–、]+"

    # 内部辅助：根据配置生成文本与可选阴影、背景条的剪辑列表
    def _make_text_and_bg_clips(display_text: str, start_time: float, duration: float) -> List[Any]:
        position = subtitle_config["position"]
        margin_bottom = int(subtitle_config.get("margin_bottom", 0))
        anchor_x = position[0] if isinstance(position, tuple) else "center"

        # 主文本剪辑（用于测量高度与实际展示）
        main_clip = TextClip(
            text=display_text,
            font_size=subtitle_config["font_size"],
            color=subtitle_config["color"],
            font=resolved_font or subtitle_config["font_family"],
            stroke_color=subtitle_config["stroke_color"],
            stroke_width=subtitle_config["stroke_width"]
        )

        # 计算文本位置（当定位 bottom 时基于文本高度与边距）
        if isinstance(position, tuple) and len(position) == 2 and position[1] == "bottom":
            baseline_safe_padding = int(subtitle_config.get("baseline_safe_padding", 4))
            y_text = max(0, video_height - margin_bottom - main_clip.h - baseline_safe_padding)
            main_pos = (anchor_x, y_text)
        else:
            main_pos = position

        main_clip = main_clip.with_position(main_pos).with_start(start_time).with_duration(duration)

        clips_to_add: List[Any] = []

        # 背景条（如启用）
        bg_color = subtitle_config.get("background_color")
        bg_opacity = float(subtitle_config.get("background_opacity", 0))
        if bg_color and bg_opacity > 0.0:
            bg_height = int(
                subtitle_config["font_size"] * subtitle_config.get("max_lines", 2)
                + subtitle_config.get("line_spacing", 10) + 4
            )
            bg_clip = ColorClip(size=(video_width, bg_height), color=bg_color)
            if hasattr(bg_clip, "with_opacity"):
                bg_clip = bg_clip.with_opacity(bg_opacity)
            y_bg = max(0, video_height - margin_bottom - bg_height)
            bg_clip = bg_clip.with_position(("center", y_bg)).with_start(start_time).with_duration(duration)
            clips_to_add.append(bg_clip)

        # 可选阴影
        if subtitle_config.get("shadow_enabled", False):
            shadow_color = subtitle_config.get("shadow_color", "black")
            shadow_clip = TextClip(
                text=display_text,
                font_size=subtitle_config["font_size"],
                color=shadow_color,
                font=resolved_font or subtitle_config["font_family"]
            ).with_position(main_pos).with_start(start_time).with_duration(duration)
            clips_to_add.extend([shadow_clip, main_clip])
        else:
            clips_to_add.append(main_clip)

        return clips_to_add

    for i, segment in enumerate(script_data["segments"], 1):
        content = segment["content"]
        # 优先使用真实音频时长，其次回退到估算时长
        duration = None
        if isinstance(segment_durations, list) and len(segment_durations) >= i:
            duration = float(segment_durations[i-1])
        if duration is None:
            duration = float(segment.get("estimated_duration", 0))
        
        logger.debug(f"处理第{i}段字幕，时长: {duration}秒")
        
        # 分割长文本为适合显示的字幕
        subtitle_texts = split_text_for_subtitle(
            content,
            subtitle_config["max_chars_per_line"],
            subtitle_config["max_lines"]
        )
        
        # 计算每行字幕的显示时长：按行字符数占比分配，确保总和==段时长
        subtitle_start_time = current_time
        line_durations: List[float] = []
        if len(subtitle_texts) > 0:
            lengths = [max(1, len(t)) for t in subtitle_texts]
            total_len = sum(lengths)
            acc = 0.0
            for idx, L in enumerate(lengths):
                if idx < len(lengths) - 1:
                    d = duration * (L / total_len)
                    line_durations.append(d)
                    acc += d
                else:
                    line_durations.append(max(0.0, duration - acc))
        else:
            line_durations = [duration]
        
        for subtitle_text, subtitle_duration in zip(subtitle_texts, line_durations):
            try:
                # 将连续标点替换为两个空格，并压缩可能产生的多余空格
                display_text = re.sub(punctuation_pattern, "  ", subtitle_text)
                display_text = re.sub(r" {3,}", "  ", display_text)

                clips_to_add = _make_text_and_bg_clips(display_text, subtitle_start_time, subtitle_duration)
                subtitle_clips.extend(clips_to_add)
                logger.debug(f"创建字幕: '{subtitle_text[:20]}...' 时间: {subtitle_start_time:.1f}-{subtitle_start_time+subtitle_duration:.1f}s")
                
                subtitle_start_time += subtitle_duration
                
            except Exception as e:
                logger.warning(f"创建字幕失败: {str(e)}，跳过此字幕")
                continue
        
        current_time += duration
    
    logger.info(f"字幕创建完成，共创建 {len(subtitle_clips)} 个字幕剪辑")
    return subtitle_clips