# 智能视频制作系统（简明版）

将 EPUB/PDF 文档一键转为短视频：智能缩写 → 关键词 → 生图 → 配音 → 合成（可选字幕与BGM）。

### 功能概览
- **LLM 智能缩写**：长文压缩为口播稿（按段）。
- **关键词提取**：为每段生成画面关键词与氛围词。
- **AI 生图（豆包 Seedream 3.0）**：按段生成图片，支持多比例/风格。
- **语音合成（字节 TTS 大模型）**：逐段生成 WAV/MP3。
- **视频合成（MoviePy 2.x）**：图像×音频对齐，支持字幕与BGM、开场金句。
- **交互式重跑**：可在 `output/` 选择项目并重做任一步骤。

### 快速开始
1) 安装依赖
```bash
pip install -r requirements.txt
```

2) 配置密钥（创建 `.env`）
```env
OPENROUTER_API_KEY=...
SILICONFLOW_KEY=...
AIHUBMIX_API_KEY=...
SEEDREAM_API_KEY=...
BYTEDANCE_TTS_APPID=...
BYTEDANCE_TTS_ACCESS_TOKEN=...
```

3) 可先检查配置
```bash
python check_config.py
```

4) 运行（默认交互式流程）
```bash
python main.py
```

### 工作流程（5步）
1. **智能缩写** → 生成 `text/script.json`（含 `title`、`segments[]` 等）
2. **关键词提取** → 生成 `text/keywords.json`（每段 `keywords`、`atmosphere`）
3. **AI 图像生成** → `images/segment_{i}.png`
4. **语音合成** → `voice/voice_{i}.(wav|mp3)`
5. **资源校验与视频合成** → `final_video.mp4`

- 字幕按真实音频时长切分与对齐；可在 `config.SUBTITLE_CONFIG` 调整样式。
- BGM 从项目根目录 `music/` 读取（通过 `bgm_filename` 指定），默认音量见 `config.BGM_DEFAULT_VOLUME`。
- 若脚本含开场金句 `golden_quote`，将自动生成开场口播与开场画面（如可用）。

### 主要参数
```python
# 见 main.py: main()
input_file=None,            # None 表示交互式选择 input/ 中的文件
target_length=1000,          # 500–2000 字
num_segments=10,             # 5–20 段
image_size="1280x720",       # 见 config.SUPPORTED_IMAGE_SIZES
llm_model="google/gemini-2.5-pro",
image_model="doubao-seedream-3-0-t2i-250415",
voice="zh_male_yuanboxiaoshu_moon_bigtts",
output_dir="output",
image_style_preset="cinematic",  # cinematic/documentary/artistic/minimalist/vintage
enable_subtitles=True,
bgm_filename=None,           # 从项目根目录 music/ 读取
run_mode="auto"              # auto | step（分步确认）
```
- **服务商自动识别**：根据模型名选择 `openrouter/siliconflow/aihubmix`、`doubao`、`bytedance`。
- **尺寸/风格**：尺寸需在 `config.SUPPORTED_IMAGE_SIZES`；风格预设见 `prompts.IMAGE_STYLE_PRESETS`。

### 输出结构
```
output/
└── {title}_{MMDD_HHMM}/
    ├── images/
    │   └── segment_{1..N}.png
    ├── voice/
    │   └── voice_{1..N}.(wav|mp3)
    ├── text/
    │   ├── script.json
    │   └── keywords.json
    └── final_video.mp4
```

### 使用小贴士
- PDF 建议为可复制文本（扫描版可能无法提取文字）。
- 可在 `output/` 打开已有项目，选择 2–5 步重跑；系统会自动清理下游产物。
- 若替换图片或音频，保持文件名不变（`segment_{i}.png`、`voice_{i}.wav`）。

### 相关文件
- `main.py`：入口与流程编排（含交互选择与重跑）。
- `functions.py`：文档读取、LLM 调用、生图、TTS、合成等核心逻辑。
- `genai_api.py`：OpenAI 兼容 LLM、豆包 Seedream、生效的字节 TTS WebSocket 实现。
- `config.py`：全局配置（模型、尺寸、字幕、音量、开场/片尾等）。
- `utils.py`：JSON 解析修复、项目扫描、交互选择、校验、DOCX 导出等。
- `prompts.py`：提示词模板与图像风格预设。

如需更详细说明，请阅读源码内注释与各模块 docstring。
