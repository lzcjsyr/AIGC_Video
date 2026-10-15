---
name: topic-explainer-script
description: 只凭一个选题（不需要书籍、报告等源文档），先联网调研，再为抖音、微信视频号写一条 3000-4000 字、约 10-12 分钟的中文知识讲解口播稿。开头按信息流的前 3 秒设计，正文分章节控制节奏、持续留住注意力、循序推进、通俗易懂，输出 Book2Video 第一步可读取的 raw JSON。用户只给话题或问题、选择“Claude Code 直接写作”、或提到“选题直写”“讲解视频”“中视频口播”时使用。
---

# 选题直写 · 中长讲解口播稿

和本库里“基于文稿”的 skill（读书、报告、带货）不同，这个 skill **不需要源文档**：输入是一个选题，事实全部来自调研。

视频在信息流里被推到观众眼前，前 3 秒决定他留不留下。但这是一条 10 分钟左右的讲解：研究发现观众的中位观看时长通常不超过 6 分钟，超过 9 分钟的视频大多数人看不到一半。所以这个 skill 要同时做到三件事：

1. **开头赢下前 3 秒，并在 1 分钟内把这期的价值往高处说足**，见 [hook-playbook.md](references/hook-playbook.md)。
2. **把 10 分钟拆成 4-5 个 2-3 分钟的章节**，每章都是一个“小视频”：有自己的问题、兑现和通往下一章的钩子。
3. **讲得让人轻松跟上**：一步一个台阶，随时知道自己走到了哪里，不用回看也听得懂。

每条规则的研究依据见 [research-basis.md](references/research-basis.md)。

## 长度配置

这是本 skill 中长度的唯一真相来源，`scripts/validate_raw.py` 也从这里读取。其他文件只能引用本节。

```yaml
content_target_chars: 3500
content_min_chars: 3000
content_max_chars: 4000
golden_quote_max_chars: 16
chapter_count: 4-5
chapter_chars: 550-900
beat_interval_chars: 250-350
```

- 实测本流水线的正文配音约 **322 字/分钟**：3000 字约 9.3 分钟，3500 字约 11 分钟，4000 字约 12.4 分钟。
- 节奏单位按字数换算：每个“节拍”（`beat_interval_chars`）约 50-65 秒，每章约 2-3 分钟。
- 开场金句和正文用同样的配音设置，16 字约 3 秒，正好落在前 3 秒窗口里；开场画面是一张约 5 秒的金句卡片（每行最多 20 字），所以金句不能超过 `golden_quote_max_chars`。
- 用户在终端指定了其他长度时，以用户为准，并在 `_topic_brief.json` 的 `length_override` 里写明。章节数按每章约 700 字重新计算，校验时传 `--min/--max`。

## 输入

- 必需：一个选题、问题或现象，以及用户在终端补充的要求（平台、观众、立场、时长等）。
- 可选：用户顺手给的链接或几段材料，只当调研线索，同样要核实。
- 用户给的是一本书、一份报告或长文档，并要求“讲这本书”时，提醒用户换用对应的基于文稿的 skill。

## 必读参考

按顺序完整读取：

1. [research-and-facts.md](references/research-and-facts.md)：选题判断、调研、证据台账。
2. [hook-playbook.md](references/hook-playbook.md)：开头设计。
3. [pacing-and-clarity.md](references/pacing-and-clarity.md)：章节结构、节拍、注意力维持、循序推进、易懂写法、配音写法。本 skill 篇幅最长的部分。
4. [output-contract.md](references/output-contract.md)：中间文件、质检清单、JSON 契约。
5. [packaging.md](references/packaging.md)：标题公式、封面写法、风险自检。

## 主流程

不要一轮直接写完。中间文件都存到工作目录（项目的 `text` 文件夹）：

1. **定选题**：锁定目标观众、平台、核心问题、一个总承诺、观众能带走的东西和传播锚点，按 `research-and-facts.md` 的六维打分，**≥20 分才进入调研**，保存 `_topic_brief.json`。用户没说平台时，按“抖音 + 视频号通用”写。
2. **调研**：按 `research-and-facts.md` 做 8 次以上检索，攒够撑起 4-5 章的事实、案例和数字，以及开头拔高要用的素材，写入 `_research_notes.md`。证据撑不起某一章，就删掉或合并那一章，不要硬写。
3. **开头工作坊**：按 `hook-playbook.md` 写出至少 6 个开头候选并打分，选定金句和首句，写出高调的价值承诺和 1 分钟内的路线图，保存 `_hooks.json`。
4. **节拍表**：按 `pacing-and-clarity.md` 设计章节、每章的入口问题和兑现、章间钩子、每个节拍的注意力手段和全片高潮位置，保存 `_beat_sheet.json`。**先有节拍表，再写正文。**
5. **初稿**：严格按节拍表写出完整正文，保存 `_draft_v1.txt`，长度达到 `content_min_chars`。
6. **终稿修订**：对照 `output-contract.md` 的清单逐项修改，保存 `_draft_final.txt`，修改摘要写入 `_review.json`。H（开头）、F（事实）、R（节奏）三组是硬闸门。
7. **包装与校验**：按 `packaging.md` 从终稿生成标题、封面文案和金句，过一遍风险自检，写入 `raw.json`，然后运行：

   ```bash
   python <本skill目录>/scripts/validate_raw.py <raw.json路径> --draft <_draft_final.txt路径>
   ```

   报错就修改后重跑，直到输出 `raw.json contract valid`。“提示”类输出也要逐条看，能改就改。

## 与 Book2Video Studio 的对接

第一步的会话由 Studio 启动，Studio 会在提示词里追加文件位置和输出契约。它们和本 skill 一致，冲突时以 Studio 为准：

- 工作目录是项目文件夹；所有中间文件放在项目的 `text` 文件夹；最终稿只写到 `text/raw.json`，不要创建 `output/` 文件夹。
- 运行校验脚本用 `python` 命令（Studio 自带的 Python），不要安装任何包。
- 直接写作模式下没有源文档：等用户在终端给出选题和要求再开始；信息不够时在终端追问。
- 金句只放在 `golden_quotes` 里，不要拼到 `content` 开头。开场金句播放开关由用户在界面里控制；关掉时视频直接从正文首句开始。
- 用户只要求修改时，在已有的 `raw.json` 基础上改，不要整篇重写。
- 会话结束后 Studio 会检查 `raw.json`，并按实际字数修正 `total_length`。

## 硬约束

- 不编造事实、数字、研究、案例、引语或亲身经历；查不到出处的说法不写成确定事实。
- 开头的承诺必须被正文兑现，章间钩子许下的“下一章揭晓”也必须兑现。不做标题党。
- 不写医疗诊断、投资建议、法律结论等需要资质的确定性判断。
- `content` 不能有 Markdown、小标题、列表、表情符号、括号或舞台说明；章节靠口语过渡来区分，不靠标题。
- 本 skill 不调用 subagent，整个流程由当前会话完成。
