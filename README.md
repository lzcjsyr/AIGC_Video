# 智能视频制作系统 (Book2Video)

**一键将 PDF、EPUB 等文档自动转换为带字幕、配音、配图的高质量短视频。**

---

## 🚀 快速上手

### 1. 系统要求

* Python 3.10+
* FFmpeg (视频处理必需，请确保系统已安装并添加到环境变量)

### 2. 安装步骤

```bash
# 安装 Python 依赖
pip install -e .
```

*提示：macOS 用户可直接运行 `./scripts/install_macos.sh`，Windows 用户运行 `powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1` 进行一键环境安装与测试。*

### 3. 配置密钥

复制 `.env.example` 为 `.env` 并填写你所需要用到的 API 密钥：

* **大模型服务** (如 MiMo, OpenRouter, SiliconFlow)
* **语音合成** (如 字节跳动 TTS)
* **图像/画面生成** (如 火山引擎, Google Cloud Vertex AI，或 HyperFrames 动态画面)

### 4. 运行制作

将待处理的文档（PDF、EPUB、DOCX、MOBI 等）放入 `input/` 文件夹下，然后运行：

```bash
python start.py
```

根据终端提示操作：选择**新建项目** -> **选择你的文档** -> 推荐新手选择**全自动模式**，即可一键完成制作。

---

## 💡 核心工作流

系统采用模块化设计，将长文档转化为短视频分为以下核心步骤：

* **步骤 1 内容生成**：AI 提炼文档核心内容为适合短视频的篇幅。
* **步骤 1.5 脚本分段**：按规则或 Agent 模式分段，并生成每段对应的口播文案。
* **步骤 2 描述小结**：从原稿生成整体内容小结，供后续各段画面保持统一语境与视觉连贯性。
* **步骤 3 语音合成**：采用高品质 TTS 引擎生成拟真配音及 SRT 字幕，为画面生成提供精确时长。
* **步骤 4 画面生成**：生成静态段落图片，或根据音频时长渲染 HyperFrames 动态画面，并渲染精美开场视频。
* **步骤 5 视频合成**：混合开场视频、转场画面、配音、字幕及背景音乐，导出 MP4 视频。
* **步骤 6 封面生成**：自动生成适配社交媒体的竖版封面图。

---

## 🎛️ 使用模式

运行 `python start.py` 后可选择：

* **全自动模式（推荐）**：一键跑通所有流程，坐等视频产出。
* **分步处理模式**：每一步完成后，支持编辑中间生成的 Word 脚本（如 `raw.docx`、`script.docx`）或更换图片风格，精细化定制视频。
* **项目管理模式**：打开现有项目，从任意中断的步骤继续执行或重新制作特定部分。

### 第四步画面模式

步骤 1.5 默认使用规则分段，并把每段 `visualizer` 写为 `image`。手动编辑 `raw.docx` 时，可在某段末尾添加 `【hf】`，让该段写为 `visualizer: "hf"` 并使用 HyperFrames 动态配图；输出到 `script.json` 时会自动移除这个标记。如需让 Agent 按意群分段并自动选择 `image` / `hf`，可在 `config.yaml` 中启用：

```yaml
step1_5:
  split_mode: agent
```

`config.yaml` 的 `step4.visual_mode` 控制画面生成方式：

```yaml
step4:
  visual_mode: static_image       # 默认：生成 images/segment_i.png
  # visual_mode: hyperframes_agent # 动态：生成 images/segment_i.mp4
  # visual_mode: mixed             # 混合：按每段 visualizer 选择图片或 HyperFrames
  hyperframes_style_preset: data_driven
  image_prompt_template: keywords  # keywords / pure_images
```

选择 `hyperframes_agent` 时，系统会先使用步骤 3 已生成的真实音频时长，再调用 Claude Agent 按项目内置 HyperFrames 规范生成动态 HTML 并渲染为分段视频。

选择 `mixed` 时，系统读取 `text/script.json` 中每段的 `visualizer` 字段：`image` 生成 `segment_i.png`，`hf` 生成 `segment_i.mp4`。步骤 1.5 的默认规则模式会把每段 `visualizer` 写为 `image`；带 `【hf】` 标记或 Agent 判定为动态配图的段落会写为 `hf`。混合模式下两类段落会分组并行生成。

静态图片使用的提示词模板集中定义在 `prompts/step4_image_templates.yaml`。每个模板都包含便于人类辨识的 `label`、`description` 和原样多行的 `template`；只有 `template` 正文会发送给生图模型。`keywords` 完整保留原有图示加中文关键词模板；`pure_images` 生成无文字的电影感叙事画面。通过 `step4.image_prompt_template` 选择，配置不存在的模板名称时会直接报错并列出可选项。

---

## 🗂️ 项目目录与模块说明

为了方便你进行定制开发、效果微调或查找对应资源，以下是根目录下各主要模块的功能与职责：

* 📂 **`core/`** — **系统核心代码库**。
* 📂 **`prompts/`** — **大模型提示词与风格模板**。包含视频生成过程中生成描述小结、润色口播文案和构建画面所用的核心 Prompt 预设。如需调整文案生成风格或添加自定义艺术风格，在此修改。
* 📂 **`skills/`** — **自动化技能扩展**。`skills/step1/` 存放第一步写作 Agent skills；`skills/step4/` 存放第四步动态画面使用的官方 HyperFrames 核心 skills，包括 `hyperframes/`、`hyperframes-core/`、`hyperframes-animation/`、`hyperframes-creative/`、`hyperframes-cli/`、`hyperframes-media/`、`hyperframes-registry/` 和 `general-video/`。
  设置环境变量 `AIGC_VIDEO_LIBRARY_DIR` 可从另一个文件夹读取 `prompts/` 与 `skills/`（桌面版用它指向用户可编辑的副本）；设置 `AIGC_HYPERFRAMES_CLI` 指向 HyperFrames 的 `dist/cli.js` 时，渲染改用该固定版本而不是 `npx`。
* 📂 **`scripts/`** — **系统管理脚本**。提供 macOS/Linux 以及 Windows 环境下一键环境安装、依赖检验以及完整功能诊断的脚本。
* 📂 **`input/`** — **待处理文档输入目录**。放入需要转为视频的 PDF、EPUB、DOCX 等原始电子书/文档。
* 📂 **`output/`** — **项目生成输出目录**。每一次视频制作都将在此按“项目名_时间戳”生成独立的文件夹，包含视频和全部中间缓存资源。
* 📂 **`music/`** — **背景音乐储备库**。存放合成视频时备选的 MP3 音频，可在配置文件中自由指定。
* 📄 **`start.py`** — **系统控制台主入口**。直接通过 `python start.py` 即可进入交互式流程引导。
* 📄 **`pyproject.toml`** — **Python 依赖包配置**。规范了全部核心依赖组件及版本信息。
* 📄 **`config.yaml`** — **系统运行全局配置文件**（复制自 `config.example.yaml`）。可调节每一步的视频分辨率、生图模式、音色语速以及模型选型等所有个性化配置。

---

## 📁 制作产出结构

视频制作完成后，在 `output/《你的文档标题》_MMDD_HHMM/` 目录下将产生以下结构，供随时审阅或二次重制：

* `final_video.mp4` — **最终合成的高清短视频文件**
* `images/` — 各分段配图及精美的 HyperFrames 开场动画（`opening.mp4`）
* `voice/` — 对应段落的高保真配音 MP3 及字幕文件（`字幕.srt`）
* `text/` — 中间过程中 AI 生成并导出的 Word 文案脚本与段落总结文件（可供编辑修正后实现精准二次重制）
