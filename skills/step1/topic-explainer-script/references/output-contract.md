# 中间文件、质检清单与 JSON 契约

## 中间文件（工作目录 = 项目 `text` 文件夹）

| 文件 | 内容 |
|---|---|
| `_topic_brief.json` | 选题判断，见 `research-and-facts.md` |
| `_research_notes.md` | 调研笔记、出处和按章覆盖 |
| `_hooks.json` | 开头候选、打分、选择和路线图 |
| `_beat_sheet.json` | 章节和节拍设计，写正文前完成 |
| `_draft_v1.txt` | 初稿正文，纯文本 |
| `_draft_final.txt` | 终稿正文，纯文本，与 `content` 完全一致 |
| `_review.json` | 质检结果和修改摘要 |
| `raw.json` | 最终输出，写到第一步指定的路径 |

不要把中间文件写到 `output/<项目>/text` 之类的其他位置。

## 节拍表 `_beat_sheet.json`

```json
{
  "core_question": "全片要回答的那一个问题",
  "roadmap": "开头的一句话路线图",
  "chapters": [
    {
      "index": 1,
      "approx_time": "0:45-3:00",
      "target_chars": 700,
      "entry_question": "这一章回答的具体问题",
      "payoff": "这一章结束时给出的结论，一句话",
      "beats": [
        {"device": "具体例子", "content": "用哪个案例或事实，对应 F/C 编号"},
        {"device": "替观众提问", "content": "……"},
        {"device": "数字 + 翻译", "content": "……"}
      ],
      "recap": "章尾一句话回顾",
      "bridge": "通往下一章的钩子"
    }
  ],
  "climax": {"chapter": 3, "content": "全片最有分量的发现，放在约三分之二处"},
  "re_hooks": [{"at": "约 3 分钟", "content": "……"}, {"at": "约 6-7 分钟", "content": "……"}],
  "open_loops": [{"opened_at": "开头", "question": "……", "closed_at": "第 3 章"}],
  "ending": "结尾怎么回扣开头的问题和大格局，留下哪一个可讨论的判断",
  "share_anchor": "传播锚点原句，以及它在哪一章"
}
```

每章的 `beats` 数量约等于 `target_chars ÷ 300`，相邻节拍的 `device` 不同。

## 终稿质检清单

修订 `_draft_v1.txt` 时逐项检查，结果写进 `_review.json`。**H、F、R 三组是硬闸门**，有一项不通过就继续改。

### H 开头（硬闸门）

- H1 正文首句 ≤20 字，不依赖金句也能独立当开头。
- H2 首句和三条金句里没有禁用开头的表达。
- H3 价值承诺讲清了“为什么和你有关”，用了至少 3 种拔高手法（含“落到个人”），没有自降身价的词；其中的事实都能对应到调研笔记。
- H4 前约 320 字（1 分钟内）有一句话路线图，没有剧透答案。
- H5 三条金句各 ≤ `golden_quote_max_chars` 字，类型不同，与首句不重复。
- H6 只听一遍能懂：把前三句念出来，没有要回看才能理解的地方。

### F 事实（硬闸门）

- F1 每个事实、数字、案例都能对应到 `_research_notes.md` 的编号。
- F2 没有编造的研究、引语、亲身经历。
- F3 有争议的结论写明了边界，没有把相关写成因果。
- F4 没有绝对化用语、医疗/投资/法律的确定性建议、“揭秘”式夸大。价值承诺里不冒充事实的主观高评价不算夸大。

### R 节奏（硬闸门）

- R1 章节数和每章长度符合 `SKILL.md` 的配置，每章都有入口问题、章内兑现和桥。
- R2 每个节拍内至少有一种注意力手段，相邻节拍手段不同，没有连续两个节拍都在讲背景或定义。
- R3 约 3 分钟和约 6-7 分钟处各有一个重新抓住注意力的设计；全片高潮在约三分之二处。
- R4 所有开环都已闭合，所有“后面会讲”都兑现了。
- R5 进度提示温和：用问题当路标，没有“第一点、第二点”；每章最多 2 处进度提示。

### U 易懂

- U1 每段只引入一个新概念；先具体后抽象。
- U2 术语第一次出现时有大白话解释，后文用词一致。
- U3 每个数字都有翻译或换算；一句最多一个数字。
- U4 口头列举不超过 3 项；因果链一步一句。
- U5 至少预判并点破了一个常见误解。

### S 结构

- S1 全片只有一条主线，每章都服务于开头的总问题。
- S2 结尾回扣开头的问题和开头许下的大格局，给出变化后的答案，留下一个真实的可讨论判断，没有运营话术和课程式总结。
- S4 全片有一句传播锚点：短、能单独截图或转述、离开视频也成立，通常落在结尾或高潮处；观众能带走的东西和 `_topic_brief.json` 的 `takeaway` 一致。
- S3 画面型句子和逻辑型句子交替出现，没有连续 3 句以上同类。

### V 配音

- V1 没有 `%`、`/`、`~`、英文缩写等不可直接朗读的符号。
- V2 单句基本不超过 25 字，标点足够。
- V3 没有括号、舞台说明、Markdown、列表、表情符号。

### P 包装

- P1 标题、封面和金句的承诺与正文一致，不是标题党。
- P2 `platform` 对应的平台差异已经体现（见 `pacing-and-clarity.md` 第六节）。
- P3 标题、封面、金句过了 `packaging.md` 的风险自检，没有绝对化用语、噱头词、诱导互动。
- P4 3 条 `video_titles` 至少用了 3 种不同的标题公式，每条前 7 个字内有钩子。

```json
{
  "checks": {"H1": true, "H2": true, "H3": true, "H4": true, "H5": true, "H6": true, "F1": true, "F2": true, "F3": true, "F4": true, "R1": true, "R2": true, "R3": true, "R4": true, "R5": true, "U1": true, "U2": true, "U3": true, "U4": true, "U5": true, "S1": true, "S2": true, "S3": true, "S4": true, "V1": true, "V2": true, "V3": true, "P1": true, "P2": true, "P3": true, "P4": true},
  "title_formulas": ["3 条 video_titles 各自用的公式"],
  "chapter_lengths": [0, 0, 0, 0],
  "changes": ["从初稿到终稿的主要修改，每条一句"],
  "unverified": ["未能联网核实、需要用户人工核对的事实；没有则空数组"]
}
```

## 最终 JSON 契约

`raw.json` 只包含以下 7 个字段，不加其他字段，必须能被 Python `json.loads` 解析：

```json
{
  "source_name": "《选题短标题》，带书名号",
  "video_titles": ["3 条发布标题，互不重复，信息完整，含搜索关键词，15-30 字"],
  "cover_titles": ["3 条封面主标题，每条 ≤10 字，大字报式，一眼能读完"],
  "cover_subtitles": ["3 条封面副标题，每条 ≤15 字，补充主标题"],
  "golden_quotes": ["3 条开场金句，每条 ≤ golden_quote_max_chars 字（不计【】），不同钩子类型"],
  "content": "完整口播终稿，与 _draft_final.txt 完全一致，自然段之间用一个换行",
  "total_length": 0
}
```

- `total_length` 等于 Python `len(content)`。
- `content` 的长度在 `SKILL.md` 的 `content_min_chars` 到 `content_max_chars` 之间（用户改了长度时，以 `length_override` 为准）。
- `content` 的自然段之间用一个换行，不要空行：Studio 的 Word 文档会把空行合并掉。章节边界记在 `_beat_sheet.json` 里，正文靠口语过渡区分章节。
- `source_name` 会显示在开场卡片上，建议书名号内不超过 12 字。
- 金句可以用一处 `【】` 标出重点词（见 `hook-playbook.md`），其他字段和 `content` 里不要用 `【】`。
- 排在第一位的金句会被默认选用，把总分最高的放第一位。
- 封面、标题、金句互相配合：封面负责一眼抓住，标题负责信息完整和被搜到，金句负责开口第一句。

## 校验

```bash
python <本skill目录>/scripts/validate_raw.py <raw.json> --draft <_draft_final.txt>
# 用户改了长度时：
python <本skill目录>/scripts/validate_raw.py <raw.json> --draft <_draft_final.txt> --min 2000 --max 2600
```

校验脚本检查字段、条数、长度、金句长度、首句长度、禁用表达、不可朗读的符号、金句是否被拼进正文，并对节拍空档（一大段里没有提问、数字或转折）、空行、过长的句子和段落、包装里的风险词给出提示。它不能代替 H、F、R 组的判断。
