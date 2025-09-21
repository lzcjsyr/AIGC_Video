# 智能视频制作系统

**将任何文档自动转换为专业短视频解说**

一键将PDF、EPUB等文档智能转换为带字幕、配音、配图的高质量短视频，专为知识类内容创作设计。

## 🚀 快速上手

### 第一步：安装配置
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置API密钥（复制并编辑 .env 文件）
cp .env.example .env
# 编辑 .env 文件，填入你的API密钥

```

### 第二步：准备文档
```bash
# 将要制作视频的文档放入 input 文件夹
# 支持格式：PDF、EPUB、MOBI、DOCX等
cp "你的文档.pdf" input/
```

### 第三步：开始制作
```bash
# 启动系统
python -m cli

# 然后按提示操作：
# 1. 选择"新建项目"
# 2. 选择你的文档文件
# 3. 选择"全自动模式"（推荐新手）
# 等待5-15分钟，视频制作完成！
```

### 输出结果
制作完成后，在 `output/项目名称_时间/` 文件夹中查看：
- `final_video.mp4` - 最终视频文件
- `images/` - 生成的配图
- `voice/` - 语音文件和字幕
- `text/` - 文本内容（可编辑重制）

## 💡 核心工作流程

系统采用**智能5步流程**，将长篇文档转换为短视频：

### 1️⃣ 智能总结 - 文档压缩
- **输入**：任意长度的文档文件
- **处理**：AI模型将文档压缩为适合视频的内容（默认800字）
- **输出**：标题、开场金句、正文内容

### 2️⃣ 脚本切分 - 内容分段
- **输入**：总结后的文本
- **处理**：按指定段数智能切分（默认6段，每段约15-20秒）
- **输出**：带时长预估的分段脚本

### 3️⃣ 要点提取 - 关键词生成
- **输入**：分段脚本
- **处理**：为每段提取视觉关键词和氛围词
- **输出**：用于图像生成的关键词数据

### 4️⃣ 多媒体生成 - 图像+语音
- **输入**：关键词数据和脚本内容
- **处理**：AI生成配图 + TTS合成语音（支持并发处理）
- **输出**：配图文件 + 语音文件 + 字幕文件

### 5️⃣ 视频合成 - 最终输出
- **输入**：图像、语音、文本、背景音乐
- **处理**：自动合成视频，添加字幕特效
- **输出**：高质量mp4视频文件

## 🎛️ 使用模式

### 模式一：全自动模式（推荐新手）
```bash
python -m cli
# 选择"全自动模式" → 一键完成所有步骤
```

### 模式二：分步处理模式（推荐定制）
```bash
python -m cli
# 选择"分步处理" → 每步完成可编辑再继续
```

**分步模式优势：**
- 第1步后：可编辑 `raw.docx` 调整总结内容
- 第2步后：可编辑 `script.docx` 调整分段和文本
- 第3步后：可重跑图像生成尝试不同风格
- 第4步后：可重跑语音合成尝试不同音色

### 模式三：项目管理模式
```bash
python -m cli
# 选择"打开现有项目" → 继续未完成的项目或重制特定步骤
```

## ⚙️ 关键参数配置

在 `config.py` 顶部的 `DEFAULT_GENERATION_PARAMS` 字典可调整通用默认参数（可通过 `config.get_default_generation_params()` 获取副本）：

```python
DEFAULT_GENERATION_PARAMS = {
    # 内容生成参数
    "target_length": 800,        # 目标字数 (500-3000)
    "num_segments": 6,           # 分段数量 (5-20)

    # 媒体参数
    "image_size": "1664x928",    # 图像尺寸 (推荐横屏)
    "llm_model": "google/gemini-2.5-pro",        # LLM 模型
    "image_model": "Qwen/Qwen-Image",            # 图像生成模型
    "voice": "zh_male_yuanboxiaoshu_moon_bigtts",# 语音音色

    # 风格参数
    "image_style_preset": "style05",             # 图像风格预设
    "opening_image_style": "des01",              # 开场图像风格

    # 输出参数
    "enable_subtitles": True,                     # 是否启用字幕
    "opening_quote": True,                        # 是否包含开场金句
    "bgm_filename": "Ramin Djawadi - Light of the Seven.mp3"  # 背景音乐
}
```

## 🎨 视频尺寸选择

| 尺寸 | 比例 | 适用场景 |
|------|------|----------|
| 1280x720 | 16:9 | YouTube、B站横屏 |
| 720x1280 | 9:16 | 抖音、快手竖屏 |
| 1024x1024 | 1:1 | 微信视频号 |
| 864x1152 | 3:4 | 小红书竖屏 |

## 🎭 图像风格预设

| 风格代码 | 风格名称 | 视觉特点 |
|----------|----------|----------|
| style01 | 概念极简 | 简洁现代，突出重点 |
| style02 | 俯视古典 | 经典构图，文艺气质 |
| style05 | 综合平衡 | 适用性广，推荐默认 |
| style08 | 科技未来 | 科幻感强，适合技术内容 |

## 📁 必需的API密钥

在 `.env` 文件中配置以下密钥：

```env
# LLM服务（至少配置一个）
OPENROUTER_API_KEY=your_key      # 推荐，模型选择多
SILICONFLOW_KEY=your_key         # 备选方案

# 图像生成（必需）
SEEDREAM_API_KEY=your_key        # 豆包图像生成

# 语音合成（必需）
BYTEDANCE_TTS_APPID=your_appid   # 字节跳动TTS
BYTEDANCE_TTS_ACCESS_TOKEN=your_token
```

## 🛠️ 高级功能

### Web界面模式
```bash
cd web && python start_web.py
# 访问 http://localhost:3000 使用图形界面
```

### 独立工具
```bash
# 文档统计分析
python tools/check_text_stats.py

# 单独测试媒体生成
python tools/gen_single_media.py
```

### 项目管理
- **断点续制**：意外中断可从任意步骤继续
- **重制优化**：可重新执行特定步骤优化效果
- **批量处理**：同时处理多个文档项目
- **文件编辑**：支持编辑中间产物后重新处理

## 🏗️ 输出文件结构

```
output/
└── 《你的文档标题》_MMDD_HHMM/
    ├── final_video.mp4          # 🎬 最终视频
    ├── images/
    │   ├── opening.png          # 开场图片
    │   └── segment_1.png        # 各段配图
    ├── voice/
    │   ├── opening.wav          # 开场语音
    │   ├── voice_1.wav          # 各段语音
    │   └── 项目名_subtitles.srt  # 字幕文件
    └── text/
        ├── raw.json/.docx       # 总结内容（可编辑）
        ├── script.json/.docx    # 分段脚本（可编辑）
        └── keywords.json        # 关键词数据
```

## ❓ 常见问题

**Q: 视频制作需要多长时间？**
A: 通常5-15分钟，取决于文档长度和API响应速度。

**Q: 支持哪些文档格式？**
A: PDF、EPUB、MOBI、DOCX、TXT等主流格式。

**Q: 可以自定义背景音乐吗？**
A: 可以，将mp3文件放入 `music/` 文件夹，在参数中指定文件名。

**Q: 如何调整视频内容？**
A: 使用分步模式，每步生成的docx文件都可编辑后重新处理。

**Q: API费用大概多少？**
A: 制作一个5分钟视频的总成本约2-5元人民币。

## 🔧 故障排除

1. **检查依赖与路径**：确认已安装依赖，项目根目录存在 `config.py`、`core/`、`cli/`。
2. **日志查看**：`cli/cli.log` 或控制台输出
3. **网络问题**：确保API服务可访问
4. **依赖问题**：重新运行 `pip install -r requirements.txt`

---

**开始你的智能视频创作之旅！** 🚀

将知识转化为视频，让AI为你的内容赋能。
