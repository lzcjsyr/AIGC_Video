"""
智能视频制作系统 - 核心功能模块
包含文档读取、智能处理、图像生成、语音合成、视频制作等功能
"""

from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, VideoFileClip
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

from knowledge_prompt_cn import summarize_system_prompt, keywords_extraction_prompt
from genai_api import text_to_text, text_to_image_doubao, text_to_audio_doubao, text_to_audio_bytedance
from config import config
from utils import (
    logger, FileProcessingError, APIError, VideoProcessingError,
    log_function_call, ensure_directory_exists, clean_text, 
    validate_file_format, safe_json_loads, save_json_file,
    calculate_duration, ProgressTracker
)

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
        
        # 提取JSON内容
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        if json_start == -1 or json_end == 0:
            raise ValueError("未在输出中找到 JSON 对象。")
        
        parsed_content = json.loads(output[json_start:json_end])
        
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

要求：
1. keywords: 具体的画面内容关键词（物体、场景、人物等）
2. atmosphere: 氛围感关键词（情感、氛围、感觉等）
3. 每类3-5个关键词
4. 适合用于图像生成的描述性词汇
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
        
        # 提取JSON内容
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        if json_start == -1 or json_end == 0:
            raise ValueError("未在输出中找到 JSON 对象。")
        
        keywords_data = json.loads(output[json_start:json_end])
        
        # 验证格式
        if "segments" not in keywords_data:
            raise ValueError("关键词数据格式错误：缺少segments字段")
        
        # 确保段落数量匹配
        if len(keywords_data["segments"]) != len(script_data["segments"]):
            raise ValueError("关键词段落数量与口播稿不匹配")
        
        return keywords_data
    
    except json.JSONDecodeError:
        raise ValueError("解析关键词 JSON 输出失败")
    except Exception as e:
        raise ValueError(f"关键词提取错误: {e}")

################ Image Generation ################
def generate_images_for_segments(server: str, model: str, keywords_data: Dict[str, Any], 
                                image_style: str, image_size: str, output_dir: str) -> List[str]:
    """
    为每个段落生成图像
    """
    try:
        image_paths = []
        
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
        
        for segment in script_data["segments"]:
            segment_index = segment["index"]
            content = segment["content"]
            
            print(f"正在生成第{segment_index}段语音...")
            
            # 生成语音文件路径
            audio_path = os.path.join(output_dir, f"segment_{segment_index}.wav")
            
            # 调用语音合成API - 根据语音音色智能选择接口
            if tts_server == "doubao":
                # 判断使用哪种豆包TTS接口
                if voice.endswith("_bigtts"):
                    # 使用字节语音合成大模型接口
                    success = text_to_audio_bytedance(
                        text=content,
                        output_filename=audio_path,
                        voice=voice
                    )
                else:
                    # 使用方舟豆包TTS接口
                    success = text_to_audio_doubao(
                        text=content,
                        output_filename=audio_path,
                        voice=voice
                    )
            else:
                raise ValueError(f"不支持的TTS服务商: {tts_server}")
            
            if success:
                audio_paths.append(audio_path)
                print(f"第{segment_index}段语音已保存: {audio_path}")
            else:
                raise ValueError(f"生成第{segment_index}段语音失败")
        
        return audio_paths
    
    except Exception as e:
        raise ValueError(f"语音合成错误: {e}")

################ Video Composition ################
def compose_final_video(image_paths: List[str], audio_paths: List[str], output_path: str) -> str:
    """
    合成最终视频
    """
    try:
        if len(image_paths) != len(audio_paths):
            raise ValueError("图像文件数量与音频文件数量不匹配")
        
        video_clips = []
        
        # 为每个段落创建视频片段
        for i, (image_path, audio_path) in enumerate(zip(image_paths, audio_paths)):
            print(f"正在处理第{i+1}段视频...")
            
            # 加载音频获取时长
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration
            
            # 创建图像剪辑，设置持续时间为音频长度
            image_clip = ImageClip(image_path).set_duration(duration)
            
            # 组合图像和音频
            video_clip = image_clip.set_audio(audio_clip)
            video_clips.append(video_clip)
            
            # 释放音频剪辑资源
            audio_clip.close()
        
        # 连接所有视频片段
        print("正在合成最终视频...")
        final_video = concatenate_videoclips(video_clips)
        
        # 输出最终视频
        final_video.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac'
        )
        
        # 释放资源
        for clip in video_clips:
            clip.close()
        final_video.close()
        
        print(f"最终视频已保存: {output_path}")
        return output_path
    
    except Exception as e:
        raise ValueError(f"视频合成错误: {e}")