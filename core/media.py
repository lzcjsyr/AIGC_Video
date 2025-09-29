"""
Media-related logic: opening image, images per segment, and TTS synthesis.
"""

from typing import Optional, Dict, Any, List, Tuple, Iterable, Set
import os
import concurrent.futures
import base64

from config import config
from prompts import (
    OPENING_IMAGE_STYLES,
    COVER_IMAGE_STYLE_PRESETS,
    COVER_IMAGE_PROMPT_TEMPLATE,
    IMAGE_STYLE_PRESETS,
    IMAGE_DESCRIPTION_PROMPT_TEMPLATE,
    IMAGE_PROMPT_SAFETY_TEMPLATE,
)
from core.utils import logger, ensure_directory_exists, APIError
from core.services import (
    text_to_image_doubao,
    text_to_audio_bytedance,
    text_to_image_siliconflow,
    text_to_text,
)
from core.validators import auto_detect_server_from_model

import requests


def _download_to_path(url: str, output_path: str, error_msg: str = "下载失败") -> None:
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(resp.content)
    except Exception as e:
        raise ValueError(f"{error_msg}: {e}")


def _persist_image_result(image_result: Dict[str, str], output_path: str, error_msg: str) -> None:
    """根据返回类型写入图像文件，支持URL或base64"""
    ensure_directory_exists(os.path.dirname(output_path))

    if not image_result:
        raise ValueError(f"{error_msg}: 空响应")

    data_type = image_result.get("type")
    data_value = image_result.get("data")

    if not data_type or not data_value:
        raise ValueError(f"{error_msg}: 响应缺少必要字段")

    try:
        if data_type == "url":
            _download_to_path(data_value, output_path, error_msg=error_msg)
        elif data_type == "b64":
            with open(output_path, 'wb') as f:
                f.write(base64.b64decode(data_value))
        else:
            raise ValueError(f"未知的图像数据类型: {data_type}")
    except Exception as e:
        raise ValueError(f"{error_msg}: {e}")


def _strip_code_fences(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip().strip('"').strip()


def _desensitize_image_prompt(original_prompt: str, safety_options: Optional[Dict[str, Any]]) -> Optional[str]:
    """使用LLM对图像提示词进行脱敏，必要时回退主模型。"""
    if not original_prompt or not safety_options:
        return None

    safety_model = safety_options.get("safety_model")
    primary_model = safety_options.get("llm_model")
    primary_server = safety_options.get("llm_server")
    max_tokens = safety_options.get("max_tokens", 800)
    temperature = safety_options.get("temperature", 0.2)

    candidates: List[Tuple[str, str]] = []
    if safety_model:
        safety_server = safety_options.get("safety_server") or auto_detect_server_from_model(safety_model, "llm")
        if safety_server:
            candidates.append((safety_server, safety_model))

    if primary_model:
        server = primary_server or auto_detect_server_from_model(primary_model, "llm")
        if server:
            candidates.append((server, primary_model))

    seen: Set[Tuple[str, str]] = set()
    for server, model in candidates:
        if not server or not model:
            continue
        key = (server, model)
        if key in seen:
            continue
        seen.add(key)

        try:
            response = text_to_text(
                server=server,
                model=model,
                prompt=IMAGE_PROMPT_SAFETY_TEMPLATE.format(prompt=original_prompt),
                system_message="",
                max_tokens=max_tokens,
                temperature=temperature,
            )
            cleaned = _strip_code_fences(response)
            if cleaned:
                logger.info(f"提示词脱敏成功，使用模型 {model}")
                return cleaned
        except APIError as api_error:
            message = str(api_error)
            if "未配置" in message or "API_KEY" in message.upper():
                logger.warning(f"提示词脱敏模型 {model} 缺少可用的 API Key，尝试回退模型")
                continue
            logger.warning(f"提示词脱敏调用失败: {api_error}")
            return None
        except Exception as exc:
            logger.warning(f"提示词脱敏出现异常: {exc}")
            return None

    return None


def generate_opening_image(image_server: str, model: str, opening_style: str,
                           image_size: str, output_dir: str, opening_quote: bool = True) -> Optional[str]:
    """生成开场图像，兼容多种服务商"""
    if not opening_quote:
        return None
    try:
        prompt = OPENING_IMAGE_STYLES.get(opening_style)
        if not prompt:
            default_style = next(iter(OPENING_IMAGE_STYLES))
            logger.warning(f"未找到开场图像风格: {opening_style}，使用默认风格: {default_style}")
            prompt = OPENING_IMAGE_STYLES[default_style]
        prompt = str(prompt).strip()

        image_path = os.path.join(output_dir, "opening.png")

        if image_server == "siliconflow":
            image_result = text_to_image_siliconflow(
                prompt=prompt,
                size=image_size,
                model=model
            )
            _persist_image_result(image_result, image_path, "开场图像保存失败")
        else:
            image_url = text_to_image_doubao(
                prompt=prompt,
                size=image_size,
                model=model
            )

            if not image_url:
                raise ValueError("开场图像生成失败")

            _persist_image_result({"type": "url", "data": image_url}, image_path, "开场图像下载失败")

        logger.info(f"开场图像已保存: {image_path} (风格: {opening_style})")
        print(f"开场图像已保存: {image_path}")
        return image_path
    except Exception as e:
        logger.warning(f"开场图像生成失败: {e}")
        return None


def _ensure_cover_style(style_id: str) -> Tuple[str, str]:
    """获取封面风格描述，返回(风格id, style_text)。"""
    if style_id in COVER_IMAGE_STYLE_PRESETS:
        return style_id, COVER_IMAGE_STYLE_PRESETS[style_id]
    default_key = next(iter(COVER_IMAGE_STYLE_PRESETS))
    return default_key, COVER_IMAGE_STYLE_PRESETS[default_key]


def generate_cover_images(
    project_output_dir: str,
    image_server: str,
    model: str,
    image_size: str,
    style_id: str,
    count: int,
    video_title: str,
    content_title: str,
    cover_subtitle: str,
) -> Dict[str, Any]:
    """生成封面图像，保存到项目根目录，文件名 cover_XX.png。"""
    try:
        if count < 1:
            count = 1

        os.makedirs(project_output_dir, exist_ok=True)
        style_key, style_text = _ensure_cover_style(style_id)
        prompt = COVER_IMAGE_PROMPT_TEMPLATE.format(
            video_title=video_title,
            content_title=content_title,
            cover_subtitle=cover_subtitle or video_title,
            style_block=style_text,
        )

        generated_paths: List[str] = []
        failures: List[str] = []

        for idx in range(1, count + 1):
            result = _generate_single_cover(
                image_server,
                model,
                image_size,
                prompt,
                project_output_dir,
                idx,
            )
            if result.get("success"):
                generated_paths.append(result["image_path"])
            else:
                failures.append(result.get("error", f"封面{idx}生成失败"))

        return {
            "success": len(generated_paths) > 0,
            "cover_paths": generated_paths,
            "failures": failures,
            "style_id": style_key,
        }
    except Exception as e:
        raise ValueError(f"封面图像生成错误: {e}")


def _generate_single_cover(
    image_server: str,
    model: str,
    image_size: str,
    prompt: str,
    project_output_dir: str,
    index: int,
) -> Dict[str, Any]:
    filename = f"cover_{index:02d}.png"
    image_path = os.path.join(project_output_dir, filename)

    try:
        if image_server == "siliconflow":
            image_result = text_to_image_siliconflow(
                prompt=prompt,
                size=image_size,
                model=model,
            )
            _persist_image_result(image_result, image_path, f"保存封面图像 {filename} 失败")
        else:
            image_url = text_to_image_doubao(
                prompt=prompt,
                size=image_size,
                model=model,
            )
            if not image_url:
                raise ValueError("封面图像生成返回空URL")
            _persist_image_result({"type": "url", "data": image_url}, image_path, f"下载封面图像 {filename} 失败")

        logger.info(f"封面图像已保存: {image_path}")
        print(f"封面图像已保存: {image_path}")
        return {"success": True, "image_path": image_path}
    except Exception as e:
        logger.warning(f"封面图像生成失败: {e}")
        print(f"封面图像生成失败: {e}")
        return {"success": False, "error": str(e)}


def _generate_single_image(args) -> Dict[str, Any]:
    """生成单个图像的辅助函数（用于多线程）"""
    (
        segment_index,
        initial_prompt,
        model,
        image_size,
        output_dir,
        image_server,
        safety_options,
    ) = args

    print(f"正在生成第{segment_index}段图像...")
    logger.debug(f"第{segment_index}段图像初始提示词: {initial_prompt}")

    prompt_in_use = initial_prompt
    desensitize_attempts = 0
    max_desensitize = safety_options.get("max_attempts", MAX_PROMPT_SAFETY_ATTEMPTS) if safety_options else 0

    attempt = 0
    max_attempts = 3
    while attempt < max_attempts:
        try:
            image_path = os.path.join(output_dir, f"segment_{segment_index}.png")

            if image_server == "siliconflow":
                image_result = text_to_image_siliconflow(
                    prompt=prompt_in_use,
                    size=image_size,
                    model=model
                )
                _persist_image_result(image_result, image_path, f"保存第{segment_index}段图像失败")
            else:
                image_url = text_to_image_doubao(
                    prompt=prompt_in_use,
                    size=image_size,
                    model=model
                )
                if not image_url:
                    raise ValueError("图像生成返回空URL")
                _persist_image_result({"type": "url", "data": image_url}, image_path, f"下载第{segment_index}段图像失败")

            print(f"第{segment_index}段图像已保存: {image_path}")
            logger.info(f"第{segment_index}段图像生成成功: {image_path}")
            return {"success": True, "segment_index": segment_index, "image_path": image_path}

        except Exception as exc:  # 捕获所有异常，包含 APIError
            error_msg = str(exc)
            lower_error = error_msg.lower()
            is_sensitive_error = (
                "outputimagesensitivecontentdetected" in lower_error
                or "sensitive" in lower_error
                or "content policy" in lower_error
            )

            if is_sensitive_error and safety_options and desensitize_attempts < max_desensitize:
                desensitize_attempts += 1
                print(f"第{segment_index}段提示词触发敏感审核，尝试自动脱敏（第{desensitize_attempts}/{max_desensitize}次）")
                logger.warning(f"第{segment_index}段提示词涉及敏感内容，尝试自动脱敏：{error_msg}")
                sanitized = _desensitize_image_prompt(prompt_in_use, safety_options)
                if sanitized:
                    prompt_in_use = sanitized
                    logger.debug(f"第{segment_index}段图像提示词已脱敏: {prompt_in_use}")
                    continue
                else:
                    logger.warning(f"第{segment_index}段提示词脱敏失败")

            attempt += 1

            if attempt < max_attempts:
                logger.warning(
                    f"第{segment_index}段图像生成失败：{error_msg}，准备重试（第{attempt + 1}/{max_attempts}次）"
                )
                continue

            logger.warning(f"第{segment_index}段图像生成失败，已跳过。错误：{error_msg}")
            print(f"第{segment_index}段图像生成失败，已跳过")
            break

    return {"success": False, "segment_index": segment_index, "image_path": ""}


def generate_images_for_segments(
    image_server: str,
    model: str,
    script_data: Dict[str, Any],
    image_style_preset: str,
    image_size: str,
    output_dir: str,
    images_method: str = "keywords",
    keywords_data: Optional[Dict[str, Any]] = None,
    description_data: Optional[Dict[str, Any]] = None,
    target_segments: Optional[Iterable[int]] = None,
    llm_model: Optional[str] = None,
    llm_server: Optional[str] = None,
) -> Dict[str, Any]:
    """为每个段落生成图像（支持多线程并发）"""
    try:
        try:
            image_style = IMAGE_STYLE_PRESETS.get(
                image_style_preset,
                next(iter(IMAGE_STYLE_PRESETS.values()))
            )
        except Exception:
            image_style = ""
        logger.info(
            f"使用图像服务: {image_server}，风格: {image_style_preset} -> {image_style}，模式: {images_method}"
        )

        images_method = images_method or getattr(config, "SUPPORTED_IMAGE_METHODS", ["keywords"])[0]
        segments = script_data.get("segments", [])
        if not segments:
            raise ValueError("脚本数据为空，无法生成图像")

        segment_count = len(segments)
        has_specific_selection = target_segments is not None
        target_set: Set[int] = set()
        if has_specific_selection:
            normalized_targets = list(target_segments or [])
            parsed_targets: Set[int] = set()
            for idx in normalized_targets:
                try:
                    parsed_targets.add(int(idx))
                except (TypeError, ValueError):
                    continue
            target_set = {idx for idx in parsed_targets if 1 <= idx <= segment_count}
            if not target_set and parsed_targets:
                raise ValueError("未找到需要生成图像的有效段落")

        prompt_payload: List[tuple[int, str]] = []

        if images_method == "description":
            summary_text = (description_data or {}).get("summary", "").strip()
            if not summary_text:
                raise ValueError("缺少描述模式所需的小结内容")
            template = IMAGE_DESCRIPTION_PROMPT_TEMPLATE
            default_style = getattr(
                config,
                "DESCRIPTION_DEFAULT_STYLE_GUIDANCE",
                "画面需保持信息清晰、构图稳定、色彩和谐。"
            )
            for segment in segments:
                segment_index = int(segment.get("index") or len(prompt_payload) + 1)
                if target_set:
                    if segment_index not in target_set:
                        continue
                elif has_specific_selection:
                    continue
                segment_content = segment.get("content", "")
                style_block = image_style or default_style
                final_prompt = template.format(
                    summary=summary_text,
                    segment=segment_content,
                    style_block=style_block
                )
                prompt_payload.append((segment_index, final_prompt))
        else:
            if not keywords_data:
                raise ValueError("缺少关键词数据")
            keyword_segments = list(keywords_data.get("segments", []))
            if len(keyword_segments) < len(segments):
                keyword_segments.extend(
                    [{"keywords": [], "atmosphere": []}] * (len(segments) - len(keyword_segments))
                )
            for idx, segment in enumerate(segments, 1):
                segment_keywords = keyword_segments[idx - 1] if idx - 1 < len(keyword_segments) else {}
                keywords = segment_keywords.get("keywords", [])
                atmosphere = segment_keywords.get("atmosphere", [])
                style_part = f"[风格] {image_style}" if image_style else ""
                content_parts: List[str] = []
                content_parts.extend(keywords)
                content_parts.extend(atmosphere)
                content_part = f"[内容] {' | '.join(content_parts)}" if content_parts else ""
                sections = [part for part in [style_part, content_part] if part]
                final_prompt = "\n".join(sections) if sections else image_style
                if not final_prompt:
                    final_prompt = f"[内容] {segment.get('content', '')}".strip()
                segment_index = segment.get('index') or idx
                if target_set:
                    if segment_index not in target_set:
                        continue
                elif has_specific_selection:
                    continue
                prompt_payload.append((segment_index, final_prompt))

        if not prompt_payload:
            raise ValueError("未生成有效的提示词")

        max_workers = getattr(config, "MAX_CONCURRENT_IMAGE_GENERATION", 3)
        print(f"使用 {max_workers} 个并发线程生成图像... (本次处理 {len(prompt_payload)} 段)")

        image_paths: List[str] = [""] * segment_count
        for idx, segment in enumerate(segments, 1):
            segment_index = int(segment.get("index") or idx)
            position = segment_index - 1
            if 0 <= position < segment_count:
                existing_path = os.path.join(output_dir, f"segment_{segment_index}.png")
                if os.path.exists(existing_path):
                    image_paths[position] = existing_path
        failed_segments: List[int] = []

        safety_options: Optional[Dict[str, Any]] = None
        if llm_model:
            safety_options = {
                "llm_model": llm_model,
                "llm_server": llm_server,
                "max_attempts": MAX_PROMPT_SAFETY_ATTEMPTS,
                "max_tokens": 800,
                "temperature": 0.2,
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(
                    _generate_single_image,
                    (int(idx), prompt, model, image_size, output_dir, image_server, safety_options or {})
                ): int(idx)
                for idx, prompt in prompt_payload
            }

            for future in concurrent.futures.as_completed(future_to_index):
                result = future.result()
                segment_index = int(result["segment_index"])
                position = segment_index - 1
                if result["success"] and 0 <= position < segment_count:
                    image_paths[position] = result["image_path"]
                else:
                    failed_segments.append(segment_index)
                    if 0 <= position < segment_count:
                        image_paths[position] = ""

        return {
            "image_paths": image_paths,
            "failed_segments": failed_segments,
            "processed_segments": sorted(target_set) if target_set else list(range(1, segment_count + 1)),
        }

    except Exception as e:
        raise ValueError(f"图像生成错误: {e}")


def _resolve_existing_voice_path(output_dir: str, segment_index: int) -> Optional[str]:
    """查找已存在的段落语音文件，优先返回wav版本"""
    candidates = [
        os.path.join(output_dir, f"voice_{segment_index}.wav"),
        os.path.join(output_dir, f"voice_{segment_index}.mp3"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _synthesize_single_voice(args) -> Dict[str, Any]:
    """
    合成单个语音的辅助函数（用于多线程）
    """
    segment_index, content, server, voice, output_dir, speed_ratio, loudness_ratio = args
    
    print(f"正在生成第{segment_index}段语音...")
    
    audio_filename = f"voice_{segment_index}.wav"
    audio_path = os.path.join(output_dir, audio_filename)
    
    try:
        if server == "bytedance":
            success = text_to_audio_bytedance(
                text=content,
                output_filename=audio_path,
                voice=voice,
                speed_ratio=speed_ratio,
                loudness_ratio=loudness_ratio,
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


def synthesize_voice_for_segments(
    server: str,
    voice: str,
    script_data: Dict[str, Any],
    output_dir: str,
    target_segments: Optional[Iterable[int]] = None,
    speed_ratio: float = 1.0,
    loudness_ratio: float = 1.0,
) -> List[str]:
    """
    为每个段落合成语音（支持多线程并发）
    """
    try:
        segments = script_data.get("segments", [])
        if not segments:
            raise ValueError("脚本数据为空，无法生成语音")

        segment_count = len(segments)
        has_specific_selection = target_segments is not None
        target_set: Set[int] = set()
        if has_specific_selection:
            normalized_targets = list(target_segments or [])
            parsed_targets: Set[int] = set()
            for idx in normalized_targets:
                try:
                    parsed_targets.add(int(idx))
                except (TypeError, ValueError):
                    continue
            target_set = {idx for idx in parsed_targets if 1 <= idx <= segment_count}
            if not target_set and parsed_targets:
                raise ValueError("未找到需要生成语音的有效段落")

        audio_paths: List[str] = [""] * segment_count
        task_args: List[Tuple[int, str, str, str, str, float, float]] = []

        for idx, segment in enumerate(segments, 1):
            segment_index = int(segment.get("index") or idx)
            position = segment_index - 1
            if not (0 <= position < segment_count):
                continue

            if has_specific_selection:
                if target_set:
                    if segment_index not in target_set:
                        existing = _resolve_existing_voice_path(output_dir, segment_index)
                        if existing:
                            audio_paths[position] = existing
                        continue
                else:
                    existing = _resolve_existing_voice_path(output_dir, segment_index)
                    if existing:
                        audio_paths[position] = existing
                    continue

            content = segment.get("content", "")
            task_args.append((segment_index, content, server, voice, output_dir, speed_ratio, loudness_ratio))

        if task_args:
            max_workers = getattr(config, "MAX_CONCURRENT_VOICE_SYNTHESIS", 2)
            print(f"使用 {max_workers} 个并发线程合成语音... (本次处理 {len(task_args)} 段)")

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_index = {
                    executor.submit(_synthesize_single_voice, args): args[0]
                    for args in task_args
                }

                for future in concurrent.futures.as_completed(future_to_index):
                    result = future.result()
                    segment_index = result["segment_index"]
                    if result["success"]:
                        position = segment_index - 1
                        if 0 <= position < segment_count:
                            audio_paths[position] = result["audio_path"]
                    else:
                        error_msg = result.get("error", f"生成第{segment_index}段语音失败")
                        raise ValueError(error_msg)
        else:
            print("本次未选择任何段落生成语音，保持现有音频。")

        # 补全未处理段落的音频路径并进行完整性校验
        for idx in range(1, segment_count + 1):
            position = idx - 1
            if audio_paths[position]:
                continue
            existing = _resolve_existing_voice_path(output_dir, idx)
            if existing:
                audio_paths[position] = existing
            else:
                raise ValueError(f"第{idx}段语音缺失，请先完成整体合成")

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

MAX_PROMPT_SAFETY_ATTEMPTS = 3


__all__ = [
    'generate_opening_image',
    'generate_images_for_segments',
    'generate_cover_images',
    'synthesize_voice_for_segments',
    'export_srt_subtitles'
]
