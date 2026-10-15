#!/usr/bin/env python3
"""Validate a topic-explainer raw.json against the Book2Video Step 1 contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

SKILL_MD = Path(__file__).resolve().parents[1] / "SKILL.md"
REQUIRED_FIELDS = {
    "source_name",
    "video_titles",
    "cover_titles",
    "cover_subtitles",
    "golden_quotes",
    "content",
    "total_length",
}
THREE_ITEM_FIELDS = ("video_titles", "cover_titles", "cover_subtitles", "golden_quotes")
BANNED_OPENINGS = ("大家好", "哈喽", "今天给大家", "今天我们来", "相信很多人", "众所周知", "在这个", "随着")
BANNED_ANYWHERE = (
    "接下来我们来看",
    "下面我来介绍",
    "值得注意的是",
    "不难发现",
    "这给我们的启示是",
    "总的来说",
    "综上所述",
    "希望对你有帮助",
    "评论区告诉我",
    "你怎么看",
    "点赞关注",
    "学到了扣1",
    "转发给有需要的人",
    "第一点",
    "第二点",
)
PACKAGING_FIELDS = ("video_titles", "cover_titles", "cover_subtitles", "golden_quotes")
PACKAGING_RISK = (
    "最强", "最好", "最佳", "最全", "最牛", "最重要", "第一", "唯一", "顶级", "极致", "绝对",
    "100%", "百分百", "永远", "终极", "震惊", "惊呆", "不看后悔", "万万没想到", "刷爆", "全网",
    "揭秘", "揭黑", "内幕", "转发给", "看到最后",
)
HUMBLE_OPENING = ("简单聊聊", "简单说说", "浅谈", "随便聊", "一点点帮助", "也许对你")
OPENING_CHARS = 320
ATTENTION = re.compile(r"[？?]|\d|[一二三四五六七八九十百千万亿两半]成|百分之|但|可是|然而|其实|反而|没想到|比如|就像|相当于|也就是说")
GAP_CHARS = 400
UNSPEAKABLE = re.compile(r"[%/~#*【】\[\]（）()<>|]|^\s*[-•]\s|^\s*\d+[.、]\s", re.MULTILINE)


def length_config() -> dict:
    text = SKILL_MD.read_text(encoding="utf-8")
    keys = ("content_min_chars", "content_max_chars", "golden_quote_max_chars")
    config = {}
    for key in keys:
        match = re.search(rf"^{key}:\s*(\d+)", text, re.MULTILINE)
        if not match:
            raise ValueError(f"SKILL.md 缺少 {key}")
        config[key] = int(match.group(1))
    return config


def first_sentence(content: str) -> str:
    return re.split(r"[。！？!?\n]", content.strip(), maxsplit=1)[0]


def attention_gaps(content: str) -> list[str]:
    """Return the openings of stretches longer than GAP_CHARS with no attention device."""
    gaps, last = [], 0
    for match in ATTENTION.finditer(content):
        if match.start() - last > GAP_CHARS:
            gaps.append(content[last:last + 20].replace("\n", " "))
        last = match.end()
    if len(content) - last > GAP_CHARS:
        gaps.append(content[last:last + 20].replace("\n", " "))
    return gaps


def validate(raw_path: Path, draft_path: Path | None, min_chars: int | None, max_chars: int | None) -> list[str]:
    config = length_config()
    low = min_chars or config["content_min_chars"]
    high = max_chars or config["content_max_chars"]
    data = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("raw JSON 顶层必须是对象")
    if set(data) != REQUIRED_FIELDS:
        raise ValueError(f"字段集合错误；缺少={sorted(REQUIRED_FIELDS - set(data))}，多余={sorted(set(data) - REQUIRED_FIELDS)}")

    source_name = data["source_name"]
    if not isinstance(source_name, str) or not re.fullmatch(r"《[^《》]+》", source_name):
        raise ValueError("source_name 必须是带书名号的非空字符串")
    if re.search(r"\.(pdf|epub|docx?|txt|mobi|azw3|md)》$", source_name, re.IGNORECASE):
        raise ValueError("source_name 不得包含文件扩展名")

    for field in THREE_ITEM_FIELDS:
        values = data[field]
        if not isinstance(values, list) or len(values) != 3:
            raise ValueError(f"{field} 必须是正好包含3项的数组")
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError(f"{field} 的每一项都必须是非空字符串")
        if len(set(values)) != 3:
            raise ValueError(f"{field} 的3项不得重复")
    if any(len(value) > 10 for value in data["cover_titles"]):
        raise ValueError("cover_titles 每项不得超过10字符")
    if any(len(value) > 15 for value in data["cover_subtitles"]):
        raise ValueError("cover_subtitles 每项不得超过15字符")
    quote_max = config["golden_quote_max_chars"]
    quotes = [re.sub(r"[【】]", "", value) for value in data["golden_quotes"]]
    if any(len(value) > quote_max for value in quotes):
        raise ValueError(f"golden_quotes 每项不得超过{quote_max}字符（不计【】）")
    if any(value.count("【") > 1 or value.count("【") != value.count("】") for value in data["golden_quotes"]):
        raise ValueError("golden_quotes 每条最多用一对【】标出重点词")

    content = data["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content 必须是非空字符串")
    if not low <= len(content) <= high:
        raise ValueError(f"content 长度 {len(content)} 不在 {low}-{high} 之间")
    if not isinstance(data["total_length"], int) or isinstance(data["total_length"], bool):
        raise ValueError("total_length 必须是整数")
    if data["total_length"] != len(content):
        raise ValueError(f"total_length 必须等于 len(content)={len(content)}")
    if draft_path is not None and content != draft_path.read_text(encoding="utf-8").strip():
        raise ValueError("content 必须与 _draft_final.txt 完全一致")

    if any(content.lstrip().startswith(quote) for quote in quotes):
        raise ValueError("不要把金句拼到 content 开头，金句只放在 golden_quotes 里")
    if "【" in content or "】" in content:
        raise ValueError("content 里不要用【】")
    opening = first_sentence(content)
    if len(opening) > 20:
        raise ValueError(f"正文首句 {len(opening)} 字，超过20字：{opening}")
    for text in [opening, *quotes]:
        hit = next((word for word in BANNED_OPENINGS if text.startswith(word)), None)
        hit = hit or next((word for word in ("大家好", "今天给大家", "今天我们来") if word in text), None)
        if hit:
            raise ValueError(f"开头使用了禁用表达“{hit}”：{text}")
    hits = [word for word in BANNED_ANYWHERE if word in content]
    if hits:
        raise ValueError(f"正文出现禁用表达：{'、'.join(hits)}")
    symbol = UNSPEAKABLE.search(content)
    if symbol:
        raise ValueError(f"正文有不可直接朗读的符号或列表格式：{symbol.group(0)!r}")

    warnings = []
    gaps = attention_gaps(content)
    if gaps:
        warnings.append(f"有 {len(gaps)} 处连续 {GAP_CHARS} 字没有提问、数字、转折、例子或类比，检查节拍：{gaps[0]}……")
    long_paragraphs = [p for p in content.split("\n") if len(p) > 300]
    if long_paragraphs:
        warnings.append(f"有 {len(long_paragraphs)} 个段落超过300字，建议按意思拆开：{long_paragraphs[0][:20]}……")
    if re.search(r"\n\s*\n", content):
        warnings.append("正文里有空行，Studio 的 Word 文档会把它合并掉；自然段之间用一个换行即可")
    if len(source_name) - 2 > 12:
        warnings.append("source_name 超过12字，开场卡片上会显得很长")
    long_sentences = [s for s in re.split(r"[。！？!?\n]", content) if len(s) > 40]
    if long_sentences:
        warnings.append(f"有 {len(long_sentences)} 句超过40字，建议拆短：{long_sentences[0][:20]}……")
    if re.search(r"[A-Za-z]{2,}", content):
        warnings.append("正文含英文单词或缩写，确认配音能正确读出")
    risky = sorted({word for field in PACKAGING_FIELDS for value in data[field] for word in PACKAGING_RISK if word in value})
    if risky:
        warnings.append(f"标题、封面或金句含风险词：{'、'.join(risky)}，按 packaging.md 的风险自检换说法")
    humble = [word for word in HUMBLE_OPENING if word in content[:OPENING_CHARS]]
    if humble:
        warnings.append(f"开头出现自降身价的说法：{'、'.join(humble)}，价值承诺要往高处说")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_json", type=Path)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--min", type=int, help="用户改了时长时的正文最少字数")
    parser.add_argument("--max", type=int, help="用户改了时长时的正文最多字数")
    args = parser.parse_args()
    for warning in validate(args.raw_json, args.draft, args.min, args.max):
        print(f"提示：{warning}")
    print("raw.json contract valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
