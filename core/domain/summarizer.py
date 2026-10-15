"""Text-related logic: summarization and script segmentation."""

from typing import Dict, Any, List, Optional
import re
import json
import datetime

from core.config import config
from core.domain.metadata import (
    get_cover_subtitles,
    get_cover_titles,
    get_golden_quotes,
    get_video_titles,
)
from core.prompts import description_summary_system_prompt
from core.shared import logger
from core.infra.ai.llm_client import text_to_text


def parse_json_robust(raw_text: str) -> Dict[str, Any]:
    """解析AI响应中的JSON，处理```json代码块和截断的JSON"""
    logger.info(f"尝试解析JSON，原始文本长度: {len(raw_text)}")
    
    # 清理代码块标记
    text_to_parse = raw_text.strip()
    if text_to_parse.startswith("```json"):
        text_to_parse = text_to_parse[7:]  # 移除```json
    if text_to_parse.endswith("```"):
        text_to_parse = text_to_parse[:-3]  # 移除结尾的```
    text_to_parse = text_to_parse.strip()
    
    # 查找JSON边界
    start = text_to_parse.find('{')
    end = text_to_parse.rfind('}')
    
    if start == -1:
        logger.error(f"未找到JSON起始符号 - 文本: {text_to_parse[:200]}")
        raise ValueError("未在输出中找到 JSON 对象")
    
    # 如果没有找到结束符，尝试修复截断的JSON
    if end == -1 or end < start:
        logger.warning("检测到截断的JSON，尝试修复")
        
        # 简单修复：寻找最后一个完整的句子，然后补充结尾
        remaining_text = text_to_parse[start+1:]
        
        # 找到最后一个句号位置
        last_sentence_end = max(
            remaining_text.rfind('。'),
            remaining_text.rfind('？'),
            remaining_text.rfind('！')
        )
        
        if last_sentence_end > 0:
            # 截取到最后完整句子
            content_part = remaining_text[:last_sentence_end + 1]
            # 构建基本的JSON结构 - 假设是标准的三字段结构
            if '"title"' in content_part and '"content"' in content_part:
                # 补充可能缺失的结尾
                text_to_parse = text_to_parse[start:start+1+last_sentence_end+1] + '"}'
                end = text_to_parse.rfind('}')
            
    if end == -1 or end < start:
        logger.error("修复失败，无法找到有效JSON结构")
        raise ValueError("未在输出中找到有效的JSON对象")
    
    snippet = text_to_parse[start:end+1]
    logger.debug(f"提取的JSON: {snippet[:200]}...")
    
    # 尝试解析
    try:
        return json.loads(snippet)
    except Exception as e:
        logger.warning(f"标准解析失败: {e}，尝试使用json-repair")
        try:
            from json_repair import repair_json
            repaired = repair_json(snippet, ensure_ascii=False)
            return json.loads(repaired)
        except Exception as e2:
            logger.error(f"JSON修复失败: {e2}")
            logger.error(f"原始snippet: {snippet}")
            raise ValueError(f"JSON解析失败: {e2}")

def generate_description_summary(
    server: str,
    model: str,
    base_url: str,
    content: str,
    max_chars: int = 100,
) -> Dict[str, Any]:
    """为描述模式生成配图背景小结"""
    try:
        user_message = f"""请基于以下文案内容生成一段不超过{max_chars}字的简介，概述内容的核心信息，：

原文内容：
{content}

要求：
1. 使用自然、简洁的中文。
2. 突出主题、背景与主要看点。
3. 字数不超过{max_chars}字。
"""

        summary = ""
        attempts = max(1, int(getattr(config, "DESCRIPTION_SUMMARY_MAX_RETRY", 3)))
        used_attempts = 0

        for attempt in range(attempts):
            used_attempts = attempt + 1
            output = text_to_text(
                server=server,
                model=model,
                prompt=user_message,
                system_message=description_summary_system_prompt,
                max_tokens=4096,
                temperature=config.LLM_TEMPERATURE_DESCRIPTION,
                base_url=base_url,
            )

            if output is None:
                raise ValueError("未能从 API 获取响应。")

            try:
                parsed = parse_json_robust(output)
                summary = _clean_summary_text(parsed.get("summary"))
            except Exception as parse_error:
                logger.warning(f"描述小结JSON解析失败，尝试兜底处理: {parse_error}")
                summary = _extract_summary_fallback(output)

            summary = _clean_summary_text(summary)

            if summary:
                if len(summary) > max_chars:
                    logger.warning(
                        "描述小结长度(%d)超过预期上限(%d)，将按原文保留",
                        len(summary),
                        max_chars,
                    )

                if not _looks_truncated_summary(summary):
                    break

                logger.warning(
                    "描述小结疑似不完整，准备重试 (第%d次尝试)",
                    attempt + 1,
                )
                summary = ""

            if attempt < attempts - 1:
                continue

        if not summary:
            summary = _build_fallback_summary(content, max_chars)
            generation_type = "description_summary_fallback"
        else:
            generation_type = "description_summary"

        if not summary:
            raise ValueError("生成的小结为空")

        return {
            "summary": summary,
            "max_length": max_chars,
            "total_length": len(summary),
            "created_time": datetime.datetime.now().isoformat(),
            "model_info": {
                "llm_server": server,
                "llm_model": model,
                "generation_type": generation_type,
                "attempts": used_attempts,
            }
        }

    except Exception as e:
        raise ValueError(f"描述模式小结生成错误: {e}")


def _clean_summary_text(value) -> str:
    if not value:
        return ""
    text = str(value).strip()
    text = text.strip('"')
    text = re.sub(r'^\s*[\[{（(]*"?summary"?\s*[:：\-–]?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*[\[{（(]*简介\s*[:：\-–]?\s*', '', text)
    text = text.rstrip(']}')
    text = text.strip('"')
    return text.strip()


def _extract_summary_fallback(raw_text: str) -> str:
    """当JSON解析失败时，尝试从原始文本中提取摘要"""
    if not raw_text:
        return ""

    text = raw_text.strip()

    # 去除代码块包裹
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("\n", 1)[0]

    text = _clean_summary_text(text.strip().strip('"'))

    lines = [line.strip('"') for line in text.splitlines() if line.strip()]
    summary = " ".join(lines) if lines else text
    return _clean_summary_text(summary)


def _looks_truncated_summary(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True

    suspicious_endings = {',', '，', ':', '：', ';', '；', '“', '‘', '"', "'", '(', '（', '《', '/', '\\'}
    if stripped[-1] in suspicious_endings:
        return True

    if _has_unbalanced_pairs(stripped):
        return True

    return False


def _has_unbalanced_pairs(text: str) -> bool:
    pairs = [
        ('《', '》'),
        ('「', '」'),
        ('“', '”'),
        ('‘', '’'),
        ('(', ')'),
        ('（', '）'),
        ('[', ']'),
        ('{', '}'),
        ('<', '>'),
    ]

    for opener, closer in pairs:
        if text.count(opener) != text.count(closer):
            return True

    if text.count('"') % 2 != 0:
        return True
    if text.count("'") % 2 != 0:
        return True

    return False


def _build_fallback_summary(source_text: str, max_chars: int) -> str:
    text = (source_text or "").strip()
    if not text:
        return ""

    sentences = re.split(r'(?<=[。！？.!?])', text)
    summary_parts: List[str] = []
    total_chars = 0

    for sentence in sentences:
        segment = sentence.strip()
        if not segment:
            continue

        segment_len = len(segment)
        if total_chars + segment_len > max_chars:
            remaining = max_chars - total_chars
            if remaining > 0:
                summary_parts.append(segment[:remaining].rstrip())
                total_chars += remaining
            break

        summary_parts.append(segment)
        total_chars += segment_len

        if total_chars >= max_chars:
            break

    if not summary_parts:
        return text[:max_chars].rstrip()

    summary = ''.join(summary_parts).strip()
    if len(summary) > max_chars:
        summary = summary[:max_chars].rstrip()

    return summary


def process_raw_to_script(
    raw_data: Dict[str, Any],
    num_segments: int,
    split_mode: str = "punctuation",
    agent_segments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    将原始数据处理为分段脚本数据。
    这是步骤1.5的核心功能，从raw数据生成最终的script数据。
    """
    try:
        video_titles = get_video_titles(raw_data)
        title = video_titles[0] if video_titles else "untitled"

        raw_source_name = (raw_data or {}).get("source_name")
        source_name = raw_source_name.strip() if isinstance(raw_source_name, str) else ""
        if not source_name:
            source_name = title
        cover_titles = get_cover_titles(raw_data, title)
        cover_subtitles = get_cover_subtitles(raw_data)
        golden_quotes = get_golden_quotes(raw_data)
        full_text = raw_data.get("content", "").strip()

        if not full_text:
            raise ValueError("原始数据的 content 字段为空")

        # 根据模式分段
        if split_mode == "agent":
            segments = _normalize_agent_segments(agent_segments or [], full_text)
            segments_text = [segment["content"] for segment in segments]
        else:
            segments_text = _split_text_into_segments(full_text, num_segments, split_mode)
            segments = [_normalize_marked_segment(text) for text in segments_text]
        actual_segments = len(segments_text)

        # 汇总统计
        total_length = len(full_text)
        enhanced_data: Dict[str, Any] = {
            "source_name": source_name,
            "video_titles": video_titles,
            "cover_titles": cover_titles,
            "cover_subtitles": cover_subtitles,
            "golden_quotes": golden_quotes,
            "total_length": total_length,
            "target_segments": num_segments if split_mode == "agent" else actual_segments,
            "actual_segments": actual_segments,
            "created_time": datetime.datetime.now().isoformat(),
            "model_info": raw_data.get("model_info", {}),
            "segments": []
        }

        # 更新模型信息中的处理类型
        enhanced_data["model_info"]["generation_type"] = "script_generation"

        # 估算每段时长
        wpm = int(getattr(config, "SPEECH_SPEED_WPM", 300))
        for i, segment in enumerate(segments, 1):
            seg_text = segment["content"]
            length_i = len(seg_text)
            estimated_duration = length_i / max(1, wpm) * 60
            enhanced_data["segments"].append({
                "index": i,
                "content": seg_text,
                "length": length_i,
                "estimated_duration": round(estimated_duration, 1),
                "visualizer": segment["visualizer"],
            })

        return enhanced_data

    except Exception as e:
        raise ValueError(f"处理原始数据为脚本错误: {e}")


def _split_text_by_newlines(full_text: str) -> List[str]:
    """手动切分：根据换行符切分，合并连续换行符"""
    text = (full_text or "").strip()
    if not text:
        return [""]

    # 按换行符切分，过滤空段
    segments = [seg.strip() for seg in re.split(r'\n+', text) if seg.strip()]
    return segments if segments else [text]


HF_MARKER_PATTERN = re.compile(r'\s*【(?:motion|hf)】\s*$', re.IGNORECASE)


def _normalize_visualizer_value(visualizer: Any) -> str:
    value = str(visualizer or "image").strip().lower()
    if value in {"image", "hf"}:
        return value
    raise ValueError(f"visualizer 不支持: {value}")


def _normalize_marked_segment(text: str) -> Dict[str, str]:
    content = str(text or "").strip()
    if HF_MARKER_PATTERN.search(content):
        return {
            "content": HF_MARKER_PATTERN.sub("", content).strip(),
            "visualizer": "hf",
        }
    return {"content": content, "visualizer": "image"}


def _compact_text_for_compare(text: str) -> str:
    return re.sub(r'\s+', '', text or "")


def _ends_sentence(text: str) -> bool:
    return bool(re.search(r'[。．.！？!?；;][”’"\'）》」』）)]*$', (text or "").strip()))


def _normalize_agent_segments(agent_segments: List[Dict[str, Any]], full_text: str) -> List[Dict[str, str]]:
    if not agent_segments:
        raise ValueError("Agent分段结果为空")

    normalized: List[Dict[str, str]] = []
    for index, segment in enumerate(agent_segments, 1):
        if not isinstance(segment, dict):
            raise ValueError(f"Agent分段结果第{index}段格式错误")
        content = str(segment.get("content") or "").strip()
        if not content:
            raise ValueError(f"Agent分段结果第{index}段为空")
        try:
            visualizer = _normalize_visualizer_value(segment.get("visualizer"))
        except ValueError as exc:
            raise ValueError(f"Agent分段结果第{index}段 {exc}") from exc
        if index < len(agent_segments) and not _ends_sentence(content):
            raise ValueError(f"Agent分段结果第{index}段疑似在句子内部切分")
        normalized.append({"content": content, "visualizer": visualizer})

    merged = _compact_text_for_compare("".join(segment["content"] for segment in normalized))
    source = _compact_text_for_compare(full_text)
    if merged != source:
        raise ValueError("Agent分段结果与原文内容不一致")
    return normalized


def _split_text_into_segments(full_text: str, num_segments: int, mode: str = "punctuation") -> List[str]:
    """Rule modes ignore the agent's target count; auto is a legacy alias."""
    if mode == "manual":
        return _split_text_by_newlines(full_text)
    if mode not in {"punctuation", "auto"}:
        raise ValueError(f"不支持的分段方式: {mode}")
    return _split_text_by_strong_punctuation(full_text)


def _split_text_by_strong_punctuation(text: str) -> List[str]:
    """Keep terminal punctuation, closing quotes and motion markers with their sentence.

    Newlines and commas are not boundaries. Dots between digits belong to a
    decimal/version number; all other periods end a segment.
    """
    source = (text or "").strip()
    if not source:
        return []
    boundary = re.compile(r"(?:[。．！？!?；;]|(?<!\d)\.|\.(?!\d))+")
    closing = set("”’\"'）》」』）)]}】")
    segments: List[str] = []
    start = 0
    for match in boundary.finditer(source):
        if match.start() < start:
            continue
        end = match.end()
        while end < len(source) and source[end] in closing:
            end += 1
        marker = re.match(r'\s*【(?:motion|hf)】', source[end:], re.IGNORECASE)
        if marker:
            end += marker.end()
        piece = source[start:end].strip()
        if piece:
            segments.append(piece)
        start = end
    if tail := source[start:].strip():
        segments.append(tail)
    return segments


def export_plain_text_segments(script_data: Dict[str, Any], text_dir: str, max_chars_per_line: int = 20) -> str:
    """
    导出纯文本分段文件（不含时间戳），使用与SRT相同的文本切分逻辑
    
    Args:
        script_data: 脚本数据
        text_dir: text文件夹路径
        max_chars_per_line: 每行最大字符数（与字幕配置一致）
    
    Returns:
        str: TXT文件路径
    """
    import os
    from core.domain.composer import VideoComposer
    
    try:
        txt_filename = "字幕.txt"
        txt_path = os.path.join(text_dir, txt_filename)
        
        # 使用VideoComposer的文本切分方法（与SRT字幕完全一致）
        composer = VideoComposer()
        txt_lines = []
        
        for i, segment in enumerate(script_data["segments"], 1):
            content = segment["content"]
            subtitle_texts = composer.split_text_for_subtitle(content, max_chars_per_line)
            
            # 直接添加切分后的内容，不添加段落标记
            for line in subtitle_texts:
                txt_lines.append(line.strip())
        
        # 写入TXT文件
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(txt_lines))
        
        logger.info(f"纯文本分段文件已保存: {txt_path}")
        return txt_path
        
    except Exception as e:
        raise ValueError(f"纯文本分段文件导出错误: {e}")
