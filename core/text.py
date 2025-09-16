"""
Text-related logic: summarization, splitting to script, and keywords extraction.
"""

from typing import Dict, Any, List, Tuple
import re
import json
import datetime

from config import config
from prompts import summarize_system_prompt, keywords_extraction_prompt
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

        output = text_to_text(
            server=server,
            model=model,
            prompt=user_message,
            system_message=summarize_system_prompt,
            max_tokens=4096,
            temperature=config.LLM_TEMPERATURE_SCRIPT
        )

        if output is None:
            raise ValueError("未能从 API 获取响应。")

        parsed = parse_json_robust(output)

        # 新格式强约束：必须包含 title / content，golden_quote 可选
        if "title" not in parsed or "content" not in parsed:
            raise ValueError("生成的 JSON 缺少必需字段：title 或 content")

        title = parsed.get("title", "untitled")
        golden_quote = parsed.get("golden_quote", "")
        full_text = (parsed.get("content") or "").strip()
        if not full_text:
            raise ValueError("生成的 content 为空")

        # 返回原始数据，不进行分段
        raw_data: Dict[str, Any] = {
            "title": title,
            "golden_quote": golden_quote,
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


def process_raw_to_script(raw_data: Dict[str, Any], num_segments: int, split_mode: str = "auto") -> Dict[str, Any]:
    """
    将原始数据处理为分段脚本数据。
    这是步骤1.5的核心功能，从raw数据生成最终的script数据。
    """
    try:
        title = raw_data.get("title", "untitled")
        golden_quote = raw_data.get("golden_quote", "")
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
            "golden_quote": golden_quote,
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

    # 原有自动切分逻辑
    text = (full_text or "").strip()
    if num_segments <= 1 or len(text) == 0:
        return [text] if text else [""]

    # 1) 句子级切分：将标点（包括换行符）附着到前句
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
        cum = 0
        boundaries: List[int] = []  # 选取 num_segments-1 个边界（句索引之后）
        for idx, s in enumerate(sentences):
            prev = cum
            cum += len(s)
            target_k = len(boundaries) + 1
            threshold = ideal * target_k
            if prev < threshold <= cum or (abs(cum - threshold) <= len(s) // 2):
                if len(boundaries) < num_segments - 1:
                    boundaries.append(idx)
            if len(boundaries) >= num_segments - 1:
                break

        # 根据边界组装段落
        segments: List[str] = []
        start = 0
        for b in boundaries:
            segment_text = ''.join(sentences[start:b+1]).strip()
            segments.append(segment_text if segment_text else '')
            start = b + 1
        last_text = ''.join(sentences[start:]).strip()
        segments.append(last_text)

        # 如因边界选择不充分导致段数不足或过多，做轻微修正
        if len(segments) < num_segments:
            while len(segments) < num_segments:
                last = segments.pop() if segments else ''
                if len(last) <= 1:
                    segments.extend([last, ''])
                else:
                    mid = len(last) // 2
                    segments.extend([last[:mid], last[mid:]])
        elif len(segments) > num_segments:
            while len(segments) > num_segments and len(segments) >= 2:
                min_i = 0
                min_sum = float('inf')
                for i2 in range(len(segments) - 1):
                    ssum = len(segments[i2]) + len(segments[i2+1])
                    if ssum < min_sum:
                        min_sum = ssum
                        min_i = i2
                merged = segments[min_i] + segments[min_i+1]
                segments = segments[:min_i] + [merged] + segments[min_i+2:]
        return segments[:num_segments]

    # 3) 若句子数量 < 段数：字符级等分，尽量均衡
    base = total_len // num_segments
    rem = total_len % num_segments
    result: List[str] = []
    start_idx = 0
    for i in range(num_segments):
        length = base + (1 if i < rem else 0)
        end_idx = start_idx + length
        result.append(text[start_idx:end_idx])
        start_idx = end_idx
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


