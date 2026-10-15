# 研究依据

本 skill 的规则来自 2026 年 10 月的一次调研。写稿时不需要读这个文件，修改规则前请先读。

可信度：**A** = 平台官方或同行评审研究；**B** = 主流媒体对官方信息的报道；**C** = 从业者经验，多个来源一致但没有硬数据。网上流传的“90% 的视频死在前 3 秒”“5 秒完播率要过 40%”等数字查不到原始出处，**本 skill 不使用**。

| 规则 | 依据 | 可信度 |
|---|---|---|
| 核心信息前 3 秒出现，钩子前 6 秒完成 | TikTok 官方 Creative best practices：“Introduce your content proposition in the first 3 seconds”“Prioritize your hook in the first 6 seconds” | A |
| 推荐不只看完播，还预测点赞、关注、收藏、分享、评论区停留、不喜欢等行为；负反馈扣分 | 2025 年抖音通过“安全与信任中心”首次公开推荐算法原理（财联社、人人都是产品经理等报道） | B |
| 只靠好奇心骗点击，换不来点赞 | Qiu & Golman, *Curiosity in news consumption*：10 万多篇微信文章，引发清晰问题、重要、意外的标题更易被点开，但点击数与点赞/点击比呈小幅负相关 | A |
| 具体但留缺口（倒 U 型） | Aubin Le Quéré & Matias (2025, *Scientific Reports*)：8977 个标题 A/B 测试的元分析，标题太模糊时更具体提升点击，太具体时再具体反而降低点击 | A |
| 好奇心来自信息缺口 | Loewenstein 信息缺口理论（上面两项研究的理论基础） | A |
| 分享动机：社交货币、实用价值、高唤醒情绪、故事 | Jonah Berger《疯传》STEPPS 框架（基于其纽约时报文章分享研究） | A/C（本次只查到二手摘要） |
| 视频号以社交推荐为重，朋友点赞会被好友看到 | 微信公开的召回频道说明（关注、朋友、推荐）及多篇行业解读 | B/C |
| 钩子类型：结果、反差、痛点、悬念、身份反差、提问、场景 | 人人都是产品经理多篇钩子文章、数英网、Opus、Captions 等，类型高度一致 | C |
| 最强的放第一句，不按时间顺序铺垫；开头必须被正文兑现 | 人人都是产品经理钩子文章；MrBeast 内部制作手册（开头要兑现封面承诺） | C |
| 写 3 个以上不同类型的开头再选 | 人人都是产品经理（写结果版、冲突版、悬念版后测试）；TikTok 官方建议每组投 3-5 条有差异的素材 | A/C |
| AI 稿的通病：开头慢而稳、过度文学化、缺少平台逻辑，需要打分自检 | 人人都是产品经理 AI 脚本文章 | C |
| 10 分钟讲解要切成 2-3 分钟的章节，每章自成一体 | Guo, Kim & Rubin (2014, L@S)：edX 690 万次观看，**无论视频多长，中位观看时长都不超过约 6 分钟**，超过 9 分钟的视频学生常常看不到一半；研究者建议切成 6 分钟以内的块（本次已核对论文原文） | A |
| 语速偏快、有热情的讲解更吸引人，不必刻意放慢 | 同上，讲者语速越快，观看时长通常越长 | A |
| 用口头信号标出内容结构（路线图、章首问题、章尾回顾）；内容分块；用对话式口吻 | Mayer 多媒体学习原则：信号原则、分块原则、个性化原则 | A |
| 开头之后给一句话路线图，但不剧透 | OutlierKit 等 YouTube 脚本指南 | C |
| 每 2-3 分钟预告下一部分，转场处最容易掉人；每个开环都要闭合；同时开 2-3 个开环 | OutlierKit、TubeMilestone 等 YouTube 长视频指南 | C |
| 约 3 分钟和 6 分钟处“再参与”；最好的内容放在约三分之二处 | MrBeast 内部制作手册（3 分钟、6 分钟再参与）；OutlierKit（最佳时刻放三分之二处）；与“中位观看约 6 分钟”的发现一致 | A/C |
| 每 30-50 字一个能画出来的东西 | 配图类视频画面 5-10 秒不变就容易掉人（OutlierKit，经验），按 322 字/分钟换算 | C |
| 每约 1 分钟一个节拍、手段轮换 | 从“每 20-30 秒一个惊喜”“每 2-3 分钟一次预告”等经验折中，按讲解类内容放宽，属于本 skill 的设计取舍 | C |
| 标点控制停顿，数字和符号改写成可朗读文字，多音字和缩写易读错 | Sarvam、Inworld、Audiostack、Pictory 的 TTS 文档；AnySpeech 中文文章 | A/C |
| 正文约 322 字/分钟 | **本项目实测**：《家庭、私有制和国家的起源》项目正文 5467 字、配音 1017 秒 | 实测 |
| 金句 ≤16 字、`source_name` 要短、可用一处【】标重点 | **本项目代码**：开场金句与正文同一套配音参数；开场卡片约 5 秒、每行最多 20 字、最多 4 行，金句下方显示书名，`【】` 内的词被高亮 | 实测 |
| 禁止“揭黑”“揭秘”噱头、利用不实信息蹭热点 | 抖音 2025 年治理新规报道（一财、IT之家等） | B |

## 主要来源

- TikTok, Creative best practices for performance ads — https://ads.tiktok.com/help/article/creative-best-practices
- 抖音推荐算法原理公开（三言财经，人人都是产品经理转载）— https://www.woshipm.com/pd/6200177.html
- 抖音首次公开算法原理（财联社）— https://www.cls.cn/detail/2005910
- Qiu & Golman, Curiosity in news consumption — https://deepblue.lib.umich.edu/items/e4235eeb-79e7-4491-85c9-92425c1fd8d9
- When curiosity gaps backfire: effects of headline concreteness on information selection decisions — https://pmc.ncbi.nlm.nih.gov/articles/PMC11704130/
- 视频号推荐机制解读 — https://www.woshipm.com/operate/4394564.html
- 短视频开头钩子类型 — https://www.woshipm.com/share/6392167.html ， https://www.woshipm.com/share/6397891.html
- AI 生成爆款开头与打分 — https://www.woshipm.com/ai/6319065.html
- MrBeast 制作手册解读 — https://www.creatorhandbook.net/leaked-document-allegedly-reveals-mrbeasts-secrets-to-youtube-success-the-key-takeaways/
- Guo, Kim & Rubin, How Video Production Affects Student Engagement (L@S 2014) — https://up.csail.mit.edu/other-pubs/las2014-pguo-engagement.pdf
- Mayer 多媒体学习原则 — https://www.learningscientists.org/blog/2021/7/1-1 ， https://lucidea.com/blog/mayers-12-principles-of-multimedia-learning
- 长视频留存与开环 — https://outlierkit.com/resources/youtube-hooks-and-retention/ ， https://outlierkit.com/resources/youtube-script-template/ ， https://tubemilestone.com/blog/longer-youtube-videos-retention
- 模式打断与留存 — https://www.gofaceless.ai/zh/blog/optimize-video-engagement-pattern-breaks
- TTS 写作 — https://docs.sarvam.ai/creative-tts-best-practices.md ， https://docs.inworld.ai/tts/best-practices/generating-speech ， https://anyspeech.io/zh/blog/how-to-make-ai-voice-sound-less-robotic
- STEPPS 摘要 — https://english.ckgsb.edu.cn/knowledge/article/contagious-jonah-berger-on-why-some-things-catch-on/
- 抖音治理新规 — https://www.yicai.com/news/102250473.html

## 想继续提升时

最可靠的依据是你自己账号的数据：在抖音和视频号后台看每条视频的前几秒流失、平均观看时长和留存曲线上的掉点。掉点如果集中在章节转场处，就加强那里的桥。同一选题用不同的金句发布，比较结果，再把胜出的开头类型补进 `hook-playbook.md`。
