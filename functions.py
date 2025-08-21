"""
智能视频制作系统 - 核心功能模块
包含文档读取、智能处理、图像生成、语音合成、视频制作等功能
"""

from moviepy import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, VideoFileClip, TextClip, ColorClip, CompositeAudioClip
# MoviePy 2.x: 使用类效果 API
try:
    from moviepy.audio.fx.AudioLoop import AudioLoop  # type: ignore
except Exception:
    AudioLoop = None  # fallback later
from moviepy.audio.fx.MultiplyVolume import MultiplyVolume  # type: ignore
try:
    from moviepy.audio.AudioClip import concatenate_audioclips  # type: ignore
except Exception:
    concatenate_audioclips = None  # fallback later
from typing import Optional, Dict, Any, List, Tuple
from io import BytesIO
from PIL import Image
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
try:
    from proglog import TqdmProgressBar  # type: ignore
except Exception:
    TqdmProgressBar = None
from utils import (
    logger, FileProcessingError, APIError, VideoProcessingError,
    log_function_call, ensure_directory_exists, clean_text, 
    validate_file_format, safe_json_loads, save_json_file,
    calculate_duration, ProgressTracker, interactive_file_selector
)
from utils import parse_json_robust
import numpy as np

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
        
        # 验证必需字段
        required_keys = ["title", "segments"]
        if not all(key in parsed_content for key in required_keys):
            missing_keys = [key for key in required_keys if key not in parsed_content]
            raise ValueError(f"生成的 JSON 缺少必需的 Key: {', '.join(missing_keys)}")
        
        # 添加系统字段
        total_length = sum(len(segment['content']) for segment in parsed_content['segments'])
        
        enhanced_data = {
            "title": parsed_content["title"],
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
            # 按照每分钟300字计算播放时长
            estimated_duration = length / 300 * 60
            
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
                response = requests.get(image_url)
                if response.status_code == 200:
                    image_path = os.path.join(output_dir, f"segment_{i}.png")
                    with open(image_path, 'wb') as f:
                        f.write(response.content)
                    image_paths.append(image_path)
                    print(f"第{i}段图像已保存: {image_path}")
                else:
                    raise ValueError(f"下载第{i}段图像失败")
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
        
        # 从script_data中获取title，用于文件命名
        title = script_data.get('title', 'untitled')
        # 清理title中的特殊字符，确保文件名安全
        safe_title = title.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        
        for segment in script_data["segments"]:
            segment_index = segment["index"]
            content = segment["content"]
            
            print(f"正在生成第{segment_index}段语音...")
            
            # 生成语音文件路径：{title}_{序号}.wav
            audio_filename = f"{safe_title}_{segment_index}.wav"
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
                       narration_volume: float = 1.0) -> str:
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
        if enable_subtitles and script_data:
            print("正在添加字幕...")
            try:
                # 传入最终视频尺寸，便于字幕计算边距/背景
                subtitle_config = config.SUBTITLE_CONFIG.copy()
                subtitle_config["video_size"] = final_video.size
                # 传入每段音频真实时长用于精准对齐
                subtitle_config["segment_durations"] = [ac.duration for ac in audio_clips]
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
                
                # 循环或裁剪至视频总时长（优先使用 audio_loop，更稳健）
                try:
                    target_duration = final_video.duration
                    print(f"🎵 视频总时长: {target_duration:.2f}秒，BGM时长: {bgm_clip.duration:.2f}秒")

                    if AudioLoop is not None:
                        # 使用 2.x 的 AudioLoop 效果类
                        bgm_clip = bgm_clip.with_effects([AudioLoop(duration=target_duration)])
                        print(f"🎵 BGM长度适配完成（AudioLoop），最终时长: {bgm_clip.duration:.2f}秒")
                    else:
                        # 尝试手动循环直至匹配长度，否则裁剪
                        print("ℹ️ audio_loop 不可用，尝试手动循环BGM…")
                        if concatenate_audioclips is not None:
                            try:
                                repeats = int(target_duration // bgm_clip.duration)
                                remainder = float(max(0.0, target_duration - repeats * bgm_clip.duration))
                                clips_to_concat = []
                                if repeats > 0:
                                    clips_to_concat.extend([bgm_clip] * repeats)
                                if remainder > 0:
                                    if hasattr(bgm_clip, "with_duration"):
                                        clips_to_concat.append(bgm_clip.with_duration(remainder))
                                if clips_to_concat:
                                    bgm_clip = concatenate_audioclips(clips_to_concat)
                                    print(f"🎵 BGM长度适配完成（manual loop），最终时长: {bgm_clip.duration:.2f}秒")
                                else:
                                    # 极短视频：裁剪
                                    if hasattr(bgm_clip, "with_duration"):
                                        bgm_clip = bgm_clip.with_duration(min(bgm_clip.duration, target_duration))
                                        print("⚠️ 已将BGM裁剪到目标时长")
                                    else:
                                        raise RuntimeError("无法适配BGM长度：缺少with_duration能力")
                            except Exception as _manual_err:
                                print(f"⚠️ 手动循环失败: {_manual_err}，回退为裁剪处理")
                                if hasattr(bgm_clip, "with_duration"):
                                    bgm_clip = bgm_clip.with_duration(min(bgm_clip.duration, target_duration))
                                    print("⚠️ 已将BGM裁剪到目标时长")
                                else:
                                    raise RuntimeError("audio_loop 不可用，手动循环失败，且不支持 with_duration")
                        else:
                            # 无法拼接：裁剪
                            if hasattr(bgm_clip, "with_duration"):
                                bgm_clip = bgm_clip.with_duration(min(bgm_clip.duration, target_duration))
                                print("⚠️ audio_loop 不可用，已将BGM裁剪到目标时长")
                            else:
                                raise RuntimeError("audio_loop 不可用，且不支持 with_duration")

                except Exception as loop_err:
                    print(f"⚠️ 背景音乐长度适配失败: {loop_err}，将不添加BGM继续生成")
                    logger.warning(f"背景音乐循环/裁剪失败: {loop_err}，将不添加BGM继续生成")
                    bgm_clip = None
                    
                # 合成复合音频
                if bgm_clip is not None:
                    print("🎵 开始合成背景音乐和口播音频")
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

                        mixed_audio = CompositeAudioClip([final_video.audio, bgm_clip])
                        print("🎵 BGM与口播音频合成完成")
                    else:
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

        # 输出最终视频（使用单行进度条，避免终端刷屏）
        moviepy_logger = None
        try:
            if TqdmProgressBar is not None:
                moviepy_logger = TqdmProgressBar(tqdm_kwargs={"leave": False, "mininterval": 0.2})
            else:
                moviepy_logger = 'bar'
        except Exception:
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
    
    # 按句号、问号、感叹号分割
    sentences = []
    current = ""
    for char in text:
        current += char
        if char in "。！？":
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
        # 如果单个句子就超过了每行限制，强制切分
        if len(sentence) > max_chars_per_line:
            if current_subtitle:
                result.append(current_subtitle)
                current_subtitle = ""
            # 强制按字符数切分长句子
            for i in range(0, len(sentence), max_chars_per_line):
                result.append(sentence[i:i + max_chars_per_line])
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
    current_time = 0
    
    logger.info("开始创建字幕剪辑...")
    
    # 解析可用字体（优先使用系统中的中文字体文件路径，避免中文缺字）
    def _resolve_font_path(preferred: Optional[str]) -> Optional[str]:
        # 若直接传入的是可用路径，则直接使用
        if preferred and os.path.exists(preferred):
            return preferred
        # 常见 macOS 中文字体文件路径候选
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
        return preferred  # 退回到传入名称（由 PIL 自行解析）

    resolved_font = _resolve_font_path(subtitle_config.get("font_family"))
    if not resolved_font:
        logger.warning("未能解析到可用中文字体，可能导致字幕无法显示中文字符。建议在 config.SUBTITLE_CONFIG.font_family 指定字体文件路径。")

    # 读取视频尺寸（用于计算底部边距和背景条）
    video_size = subtitle_config.get("video_size", (1280, 720))
    video_width, video_height = video_size

    segment_durations = subtitle_config.get("segment_durations", [])

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
                # 设置位置
                position = subtitle_config["position"]
                margin_bottom = int(subtitle_config.get("margin_bottom", 0))
                anchor_x = position[0] if isinstance(position, tuple) else "center"
                
                # 创建字幕剪辑（可能包含阴影效果）
                if subtitle_config.get("shadow_enabled", False):
                    # 创建阴影效果：先创建阴影文本，再创建主文本
                    shadow_offset = subtitle_config.get("shadow_offset", (2, 2))
                    shadow_color = subtitle_config.get("shadow_color", "black")
                    
                    # 创建阴影文本剪辑
                    shadow_clip = TextClip(
                        text=subtitle_text,
                        font_size=subtitle_config["font_size"],
                        color=shadow_color,
                        font=resolved_font or subtitle_config["font_family"]
                    )
                    
                    # 创建主文本剪辑
                    main_clip = TextClip(
                        text=subtitle_text,
                        font_size=subtitle_config["font_size"],
                        color=subtitle_config["color"],
                        font=resolved_font or subtitle_config["font_family"],
                        stroke_color=subtitle_config["stroke_color"],
                        stroke_width=subtitle_config["stroke_width"]
                    )
                    
                    # 计算阴影位置（简化处理，使用相同的主要位置但稍微偏移）
                    # 对于阴影效果，我们使用相同的基础位置，让MoviePy的stroke效果来处理阴影
                    shadow_pos = position
                    
                    # 设置时间和位置
                    # 计算文本的实际 y 坐标（当定位到 bottom 时，使用边距避免出界）
                    if isinstance(position, tuple) and len(position) == 2 and position[1] == "bottom":
                        y_text = max(0, video_height - margin_bottom - main_clip.h)
                        main_pos = (anchor_x, y_text)
                        shadow_pos = (anchor_x, y_text)
                    else:
                        main_pos = position
                        shadow_pos = position
                    shadow_clip = shadow_clip.with_position(shadow_pos).with_start(subtitle_start_time).with_duration(subtitle_duration)
                    main_clip = main_clip.with_position(main_pos).with_start(subtitle_start_time).with_duration(subtitle_duration)
                    
                    clips_to_add = []
                    # 背景条
                    bg_color = subtitle_config.get("background_color")
                    bg_opacity = float(subtitle_config.get("background_opacity", 0))
                    if bg_color:
                        bg_height = int(subtitle_config["font_size"] * subtitle_config.get("max_lines", 2) + subtitle_config.get("line_spacing", 10) + 20)
                        bg_clip = ColorClip(size=(video_width, bg_height), color=bg_color)
                        if hasattr(bg_clip, "with_opacity"):
                            bg_clip = bg_clip.with_opacity(bg_opacity)
                        y_bg = max(0, video_height - margin_bottom - bg_height)
                        bg_clip = bg_clip.with_position(("center", y_bg)).with_start(subtitle_start_time).with_duration(subtitle_duration)
                        clips_to_add.append(bg_clip)
                    clips_to_add.extend([shadow_clip, main_clip])
                    subtitle_clips.extend(clips_to_add)
                    
                    logger.debug(f"创建阴影字幕: '{subtitle_text[:20]}...' 时间: {subtitle_start_time:.1f}-{subtitle_start_time+subtitle_duration:.1f}s")
                
                else:
                    # 创建普通字幕文本剪辑（无阴影）
                    txt_clip = TextClip(
                        text=subtitle_text,
                        font_size=subtitle_config["font_size"],
                        color=subtitle_config["color"],
                        font=resolved_font or subtitle_config["font_family"],
                        stroke_color=subtitle_config["stroke_color"],
                        stroke_width=subtitle_config["stroke_width"]
                    )
                    
                    # 计算文本的实际 y 坐标（当定位到 bottom 时，使用边距避免出界）
                    if isinstance(position, tuple) and len(position) == 2 and position[1] == "bottom":
                        y_text = max(0, video_height - margin_bottom - txt_clip.h)
                        txt_pos = (anchor_x, y_text)
                    else:
                        txt_pos = position
                    txt_clip = txt_clip.with_position(txt_pos).with_start(subtitle_start_time).with_duration(subtitle_duration)

                    clips_to_add = []
                    # 背景条
                    bg_color = subtitle_config.get("background_color")
                    bg_opacity = float(subtitle_config.get("background_opacity", 0))
                    if bg_color:
                        bg_height = int(subtitle_config["font_size"] * subtitle_config.get("max_lines", 2) + subtitle_config.get("line_spacing", 10) + 20)
                        bg_clip = ColorClip(size=(video_width, bg_height), color=bg_color)
                        if hasattr(bg_clip, "with_opacity"):
                            bg_clip = bg_clip.with_opacity(bg_opacity)
                        y_bg = max(0, video_height - margin_bottom - bg_height)
                        bg_clip = bg_clip.with_position(("center", y_bg)).with_start(subtitle_start_time).with_duration(subtitle_duration)
                        clips_to_add.append(bg_clip)
                    clips_to_add.append(txt_clip)
                    subtitle_clips.extend(clips_to_add)
                    
                    logger.debug(f"创建字幕: '{subtitle_text[:20]}...' 时间: {subtitle_start_time:.1f}-{subtitle_start_time+subtitle_duration:.1f}s")
                
                subtitle_start_time += subtitle_duration
                
            except Exception as e:
                logger.warning(f"创建字幕失败: {str(e)}，跳过此字幕")
                continue
        
        current_time += duration
    
    logger.info(f"字幕创建完成，共创建 {len(subtitle_clips)} 个字幕剪辑")
    return subtitle_clips