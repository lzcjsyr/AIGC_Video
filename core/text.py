"""
Text-related logic: summarization, splitting to script, and keywords extraction.
"""

from typing import Dict, Any, List, Tuple
import re
import json
import datetime

from config import config
from prompts import (
    summarize_system_prompt,
    keywords_extraction_prompt,
    description_summary_system_prompt,
)
from core.utils import logger
from core.services import text_to_text


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
        logger.error(f"修复失败，无法找到有效JSON结构")
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


def _ensure_book_title_format(content_title: str, fallback: str) -> str:
    """确保内容标题带有中文书名号《》且不为空。"""
    title = (content_title or "").strip()
    if not title:
        title = (fallback or "").strip()
    if not title:
        return "《未命名作品》"

    if not (title.startswith("《") and title.endswith("》")):
        stripped = title.strip("《》")
        title = f"《{stripped}》"
    return title


def intelligent_summarize(server: str, model: str, content: str, target_length: int, num_segments: int) -> Dict[str, Any]:
    """
    智能缩写 - 第一次LLM处理
    新逻辑：LLM生成完整口播终稿（content），返回原始数据，不进行分段。
    """
    try:
        user_message = f"""请将以下内容智能压缩为约{target_length}字的口播终稿，不要分段：

原文内容：
{content}

要求：
1. 保持核心信息与清晰逻辑，语言适合口播
2. 输出完整终稿到 content 字段，勿做任何分段
3. 总字数控制在{target_length}字左右
"""

        # 使用4096 tokens以确保完整输出，足够容纳3000字中文内容和JSON结构
        max_tokens = 4096
        output = text_to_text(
            server=server,
            model=model,
            prompt=user_message,
            system_message=summarize_system_prompt,
            max_tokens=max_tokens,
            temperature=config.LLM_TEMPERATURE_SCRIPT,
        )

        if output is None:
            raise ValueError("未能从 API 获取响应。")

        parsed = parse_json_robust(output)

        # 新格式强约束：必须包含 title / content，golden_quote 可选
        if "title" not in parsed or "content" not in parsed:
            raise ValueError("生成的 JSON 缺少必需字段：title 或 content")

        title = parsed.get("title", "untitled")
        content_title = _ensure_book_title_format(parsed.get("content_title", ""), title)

        def _normalize_options(raw_options, fallback_value: str) -> List[str]:
            options: List[str] = []
            if isinstance(raw_options, list):
                for item in raw_options:
                    if isinstance(item, str):
                        candidate = item.strip()
                        if candidate and candidate not in options:
                            options.append(candidate)
            elif isinstance(raw_options, str):
                candidate = raw_options.strip()
                if candidate:
                    options.append(candidate)

            fallback_candidate = fallback_value.strip() if isinstance(fallback_value, str) else ""
            if fallback_candidate and fallback_candidate not in options:
                options.append(fallback_candidate)

            return options

        raw_cover_subtitle_options = parsed.get("cover_subtitle_options", [])
        raw_golden_quote_options = parsed.get("golden_quote_options", [])
        cover_subtitle = (parsed.get("cover_subtitle") or "").strip()
        golden_quote = (parsed.get("golden_quote") or "").strip()

        cover_subtitle_options = _normalize_options(raw_cover_subtitle_options, cover_subtitle)
        golden_quote_options = _normalize_options(raw_golden_quote_options, golden_quote)

        cover_subtitle = cover_subtitle_options[0] if cover_subtitle_options else ""
        golden_quote = golden_quote_options[0] if golden_quote_options else ""

        full_text = (parsed.get("content") or "").strip()
        if not full_text:
            raise ValueError("生成的 content 为空")

        # 返回原始数据，不进行分段
        raw_data: Dict[str, Any] = {
            "title": title,
            "content_title": content_title,
            "cover_subtitle": cover_subtitle,
            "cover_subtitle_options": cover_subtitle_options,
            "golden_quote": golden_quote,
            "golden_quote_options": golden_quote_options,
            "content": full_text,
            "total_length": len(full_text),
            "target_segments": num_segments,
            "created_time": datetime.datetime.now().isoformat(),
            "model_info": {
                "llm_server": server,
                "llm_model": model,
                "generation_type": "raw_generation"
            }
        }

        return raw_data

    except Exception as e:
        raise ValueError(f"智能缩写处理错误: {e}")


def generate_description_summary(server: str, model: str, content: str, max_chars: int = 100) -> Dict[str, Any]:
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
                temperature=config.LLM_TEMPERATURE_KEYWORDS,
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


def process_raw_to_script(raw_data: Dict[str, Any], num_segments: int, split_mode: str = "auto") -> Dict[str, Any]:
    """
    将原始数据处理为分段脚本数据。
    这是步骤1.5的核心功能，从raw数据生成最终的script数据。
    """
    try:
        title = raw_data.get("title", "untitled")
        content_title = _ensure_book_title_format(raw_data.get("content_title", ""), title)
        cover_subtitle = raw_data.get("cover_subtitle", "")
        golden_quote = raw_data.get("golden_quote", "")

        def _sanitize_script_options(values: Any, primary: str) -> List[str]:
            options: List[str] = []
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str):
                        candidate = value.strip()
                        if candidate and candidate not in options:
                            options.append(candidate)
            if isinstance(primary, str):
                primary_value = primary.strip()
                if primary_value and primary_value not in options:
                    options.insert(0, primary_value)
            return options

        cover_subtitle_options = _sanitize_script_options(raw_data.get("cover_subtitle_options"), cover_subtitle)
        golden_quote_options = _sanitize_script_options(raw_data.get("golden_quote_options"), golden_quote)
        full_text = raw_data.get("content", "").strip()

        if not full_text:
            raise ValueError("原始数据的 content 字段为空")

        # 根据模式分段
        segments_text = _split_text_into_segments(full_text, num_segments, split_mode)
        actual_segments = len(segments_text)

        # 汇总统计
        total_length = len(full_text)
        enhanced_data: Dict[str, Any] = {
            "title": title,
            "content_title": content_title,
            "cover_subtitle": cover_subtitle,
            "cover_subtitle_options": cover_subtitle_options,
            "golden_quote": golden_quote,
            "golden_quote_options": golden_quote_options,
            "total_length": total_length,
            "target_segments": num_segments,
            "actual_segments": actual_segments,
            "created_time": datetime.datetime.now().isoformat(),
            "model_info": raw_data.get("model_info", {}),
            "segments": []
        }

        # 更新模型信息中的处理类型
        enhanced_data["model_info"]["generation_type"] = "script_generation"

        # 估算每段时长
        wpm = int(getattr(config, "SPEECH_SPEED_WPM", 300))
        for i, seg_text in enumerate(segments_text, 1):
            length_i = len(seg_text)
            estimated_duration = length_i / max(1, wpm) * 60
            enhanced_data["segments"].append({
                "index": i,
                "content": seg_text,
                "length": length_i,
                "estimated_duration": round(estimated_duration, 1)
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


def _split_text_into_segments(full_text: str, num_segments: int, mode: str = "auto") -> List[str]:
    """
    文本切分函数
    mode: "manual" 手动切分(按换行符), "auto" 自动切分(智能均分)
    """
    if mode == "manual":
        return _split_text_by_newlines(full_text)

    # 自动切分逻辑
    text = (full_text or "").strip()
    if num_segments <= 1 or len(text) == 0:
        return [text] if text else [""]

    # 1) 句子级切分：将标点附着到前句
    raw_parts = re.split(r'([。！？；.!?\n])', text)
    sentences: List[str] = []
    i = 0
    while i < len(raw_parts):
        token = raw_parts[i]
        if token and token.strip():
            cur = token.strip()
            if i + 1 < len(raw_parts) and raw_parts[i + 1] and raw_parts[i + 1].strip() in '。！？；.!?\n':
                cur += raw_parts[i + 1].strip()
                i += 2
            else:
                i += 1
            sentences.append(cur)
        else:
            i += 1

    if not sentences:
        sentences = [text]

    # 2) 若句子数量 >= 段数：在句子边界上均衡聚合
    total_len = sum(len(s) for s in sentences)
    if len(sentences) >= num_segments:
        ideal = total_len / float(num_segments)
        segments: List[str] = []
        current: List[str] = []
        current_len = 0

        for idx, s in enumerate(sentences):
            current.append(s)
            current_len += len(s)
            
            # 决策：是否应该断句
            remaining = len(sentences) - idx - 1
            needed = num_segments - len(segments) - 1
            
            # 如果当前段接近理想长度，且后续还有足够句子分配
            if current_len >= ideal * 0.7 and remaining >= needed and needed > 0:
                segments.append(''.join(current))
                current = []
                current_len = 0
        
        # 添加最后一段
        if current:
            segments.append(''.join(current))

        # 3) 修正段数：拆分最长或合并最短
        while len(segments) < num_segments and segments:
            # 找最长段落，在标点处拆分
            longest_idx = max(range(len(segments)), key=lambda i: len(segments[i]))
            seg = segments[longest_idx]
            if len(seg) < 2:
                break
            mid = len(seg) // 2
            # 寻找附近的标点位置
            for p in ['。', '！', '？', '\n']:
                pos = seg.rfind(p, max(0, mid - 30), mid + 30)
                if pos > 0:
                    mid = pos + 1
                    break
            part1, part2 = seg[:mid].strip(), seg[mid:].strip()
            if part1 and part2:  # 只有两部分都非空才拆分
                segments[longest_idx:longest_idx+1] = [part1, part2]
            else:
                break

        while len(segments) > num_segments:
            # 合并相邻最短的两段
            min_idx = min(range(len(segments) - 1), 
                         key=lambda i: len(segments[i]) + len(segments[i+1]))
            segments[min_idx:min_idx+2] = [segments[min_idx] + segments[min_idx+1]]

        return segments[:num_segments]

    # 3) 若句子数量 < 段数：字符级均分
    base = total_len // num_segments
    rem = total_len % num_segments
    result: List[str] = []
    pos = 0
    for i in range(num_segments):
        length = base + (1 if i < rem else 0)
        result.append(text[pos:pos+length])
        pos += length
    return result


def extract_keywords(server: str, model: str, script_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    要点提取 - 第二次LLM处理
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
            temperature=config.LLM_TEMPERATURE_KEYWORDS
        )

        if output is None:
            raise ValueError("未能从 API 获取响应。")

        # 鲁棒解析（先常规，失败则修复）
        keywords_data = parse_json_robust(output)

        # 精简对齐：按脚本段数对齐（多截断、少补空），不再额外校验/告警
        expected = len(script_data["segments"])  # 以脚本段数为准
        segs = list(keywords_data.get("segments") or [])
        keywords_data["segments"] = (
            segs[:expected]
            + [{"keywords": [], "atmosphere": []}] * max(0, expected - len(segs))
        )

        # 添加模型信息
        keywords_data["model_info"] = {
            "llm_server": server,
            "llm_model": model,
            "generation_type": "keywords_extraction"
        }
        keywords_data["created_time"] = datetime.datetime.now().isoformat()

        return keywords_data

    except Exception as e:
        raise ValueError(f"要点提取错误: {e}")
