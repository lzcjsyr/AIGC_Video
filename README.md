# 智能视频制作系统（精简说明）

将 EPUB/PDF 文档自动转为短视频：LLM 智能缩写 → 关键词提取 → Seedream 3.0 生图 → 字节 TTS 配音 → MoviePy 合成（可选字幕与 BGM）。

### 核心能力

- **智能摘要**：长文压缩为口播稿，按段落输出 JSON。
- **图像生成**：豆包 Seedream 3.0；支持多比例、多风格预设。
- **语音合成**：字节语音合成大模型，多音色，逐段生成 WAV。
- **视频合成**：按段对齐图像与音频；可自动字幕、可混入 BGM。
- **交互式重跑**：支持新建或打开既有项目，选择任一步骤重做。

### 工作流程（5步）

1) **智能缩写**→ `text/script.json`
2) **关键词提取** → `text/keywords.json`
3) **图像生成** → `images/segment_{i}.png`
4) **语音合成** → `voice/{title}_{i}.wav`
5) **资源校验与视频合成** → `final_video.mp4`

字幕按真实音频时长切分与对齐；BGM 从项目根目录 `music/` 读取（`bgm_filename`），默认音量见 `config.BGM_DEFAULT_VOLUME`。

### 快速开始

1) 配置密钥（创建 `.env`）

```env
OPENROUTER_API_KEY=...
SILICONFLOW_KEY=...
AIHUBMIX_API_KEY=...
SEEDREAM_API_KEY=...
BYTEDANCE_TTS_APPID=...
BYTEDANCE_TTS_ACCESS_TOKEN=...
```

2) 可先运行配置检查

```bash
python check_config.py
```

3) 运行（交互式新建/打开项目，支持逐步确认）

```bash
python main.py
```

### 关键参数（简表）

```python
def main(
    input_file=None,
    target_length=1000,          # 500-2000
    num_segments=10,             # 5-20
    image_size="1280x720",       # 见 config.SUPPORTED_IMAGE_SIZES
    llm_model="google/gemini-2.5-pro",
    image_model="doubao-seedream-3-0-t2i-250415",
    voice="zh_male_yuanboxiaoshu_moon_bigtts",
    output_dir="output",
    image_style_preset="cinematic",
    enable_subtitles=True,
    bgm_filename=None,           # 从项目根目录 music/ 读取
    run_mode="auto"              # auto | step
)
```

- **服务商自动识别**：根据模型名自动选择 openrouter/siliconflow/aihubmix 与 doubao/bytedance。
- **尺寸/风格**：尺寸需在 `config.SUPPORTED_IMAGE_SIZES`，风格见 `prompts.IMAGE_STYLE_PRESETS`。

### 输出结构

```
output/
└── {title}_{MMDD_HHMM}/
    ├── images/
    ├── voice/
    ├── text/
    │   ├── script.json
    │   └── keywords.json
    └── final_video.mp4
```

### 模型与服务商（概览）

- **LLM**：OpenRouter / SiliconFlow / aihubmix（按模型名自动识别）。
- **图像**：豆包 Seedream 3.0。
- **TTS**：字节语音合成大模型。

### 项目结构（简）

```
AIGC_Video/
├── main.py        # 入口与流程编排（含交互式重跑）
├── functions.py   # 文档/LLM/生图/TTS/合成等核心逻辑
├── config.py      # 配置与校验（尺寸、字幕、BGM音量等）
├── genai_api.py   # 第三方服务调用封装
├── utils.py       # 工具与交互组件
├── prompts.py     # 提示词模板与风格预设
├── check_config.py# 配置检查
├── music/         # 可选BGM放置目录
├── input/         # 输入文档目录
└── output/        # 结果目录
```

> 下方为更详细的原始说明，供参考（如需极简只看上方）。

# 智能视频制作系统

一个基于多种AI技术的智能视频制作系统，将EPUB和PDF文档自动转换为短视频内容。系统通过LLM智能缩写、关键词提取、AI图像生成、语音合成等技术，实现从文档到视频的全自动化制作流程。

## 系统特点

- 🤖 **智能化处理**: 使用多个大语言模型进行内容理解和压缩
- 🎨 **高质量图像**: 豆包Seedream 3.0生成电影级图像
- 🔊 **自然语音**: 字节语音合成大模型，支持多音色
- 🎬 **自动合成**: 图像+语音+字幕自动合成视频
- ⚙️  **模块化设计**: 支持多服务商切换，配置灵活
- 📊 **完整输出**: 包含脚本、关键词、处理摘要等完整信息

## 目录

- [工作流程](#工作流程)
- [输入参数说明](#输入参数说明)
- [输出结构说明](#输出结构说明)
- [AI服务商说明](#ai服务商说明)
- [环境配置](#环境配置)
- [使用示例](#使用示例)

## 工作流程

本系统采用6步智能化视频制作流程：

### 1. 文档读取

- 自动识别并读取EPUB或PDF文件（支持10万字级别的长篇文档）
- 提取文档中的文本内容，过滤无关信息

### 2. 智能缩写（第一次LLM处理）

- 使用大语言模型将10万字级别的原文智能压缩为500-1000字的精炼口播稿
- 自动分成指定段数，保持内容连贯性和完整性
- 输出结构化JSON格式，便于后续处理
- **文件保存**：口播稿JSON数据保存到 `output/{title}_{时间}/text/script.json`

### 3. 关键词提取（第二次LLM处理）

- 对每个段落进行深度分析
- 提取核心关键词和视觉元素
- 为图像生成做准备
- **文件保存**：关键词和图像提示词数据保存到 `output/{title}_{时间}/text/keywords.json`

### 4. AI图像生成

- 结合段落关键词和预设风格提示词
- 调用豆包Seedream 3.0模型（`doubao-seedream-3-0-t2i-250415`）生成高质量图像
- 使用火山引擎方舟SDK进行API调用
- 每段对应一张图片
- **文件保存**：生成的图片保存到 `output/{title}_{时间}/images/segment_X.png`（X为段落序号）

### 5. 语音合成

- 使用字节语音合成大模型WebSocket协议合成语音
- 支持多种高质量中文音色（如：zh_male_yuanboxiaoshu_moon_bigtts）
- 为每个段落生成对应的音频文件
- **文件保存**：语音文件保存到 `output/{title}_{时间}/voice/{title}_{序号}.wav`

### 6. 视频合成

- 将对应的音频和图像进行匹配
- 使用MoviePy合成完整的短视频内容
- 支持自动添加字幕功能
- **文件保存**：最终视频保存到 `output/{title}_{时间}/final_video.mp4`

**背景音乐（BGM）支持**：

- BGM 文件从项目根目录 `music/` 读取（参数 `bgm_filename`）
- 常见支持格式：`mp3`, `wav`, `m4a`, `aac`, `ogg`, `flac`（具体取决于本机 ffmpeg 的编解码支持）
- 默认 BGM 音量由 `config.BGM_DEFAULT_VOLUME` 控制

## 输入参数说明

主函数 `main()`接受以下参数：

```python
def main(
    input_file=None,    # 输入文件路径（EPUB或PDF文件），如为None则自动从input文件夹读取
    target_length=800,  # 缩写后的目标字数，范围500-1000字
    num_segments=10,    # 分段数量，默认10段
    image_size="1280x720",  # 生成图片的尺寸，支持多种比例
    llm_model="google/gemini-2.5-pro",  # 大语言模型
    image_model="doubao-seedream-3-0-t2i-250415",  # 图像生成模型
    voice="zh_male_yuanboxiaoshu_moon_bigtts",      # 语音音色
    output_dir="output",  # 输出目录，默认为当前目录下的output文件夹
    image_style_preset="cinematic",  # 图像风格预设，可选：cinematic, documentary, artistic等
    enable_subtitles=True  # 是否启用字幕，默认启用
)
```

### 参数详细说明

**基础参数**：

- `input_file`: 输入文档路径，支持EPUB和PDF格式。为None时自动从input文件夹读取
- `target_length`: 目标字数，范围500-1000字
- `num_segments`: 分段数量，范围5-20段
- `enable_subtitles`: 是否启用字幕功能

**AI模型参数**（系统会自动检测服务商）：

- `llm_model`: 大语言模型选择
  - OpenRouter服务商: `google/gemini-2.5-pro`, `anthropic/claude-sonnet-4`
  - SiliconFlow服务商: `zai-org/GLM-4.5`, `moonshotai/Kimi-K2-Instruct`
  - aihubmix代理: `gpt-5`
- `image_model`: 图像生成模型，当前支持 `doubao-seedream-3-0-t2i-250415`
- `voice`: 语音音色，如 `zh_male_yuanboxiaoshu_moon_bigtts`, `zh_female_linjianvhai_moon_bigtts`

**视觉参数**：

- `image_size`: 图像尺寸，支持多种比例（1024x1024, 1280x720, 720x1280等）
- `image_style_preset`: 预设风格（cinematic, documentary, artistic, minimalist, vintage）

**背景音乐参数**：

- `bgm_filename`: 背景音乐文件名，放在项目根目录 `music/` 中。常见支持格式：`mp3/wav/m4a/aac/ogg/flac`（以本机 ffmpeg 支持为准）

## 输出结构说明

### 1. 文件夹结构

```
output/
└── {title}_{月日_时分}/     # 按文档标题和时间命名的项目文件夹
    ├── images/              # 生成的图片文件夹
    │   ├── segment_1.png   # 第1段对应图片
    │   ├── segment_2.png   # 第2段对应图片
    │   └── ...             # 共10张图片
    ├── voice/              # 生成的语音文件夹
    │   ├── {title}_1.wav   # 第1段口播音频（以标题命名）
    │   ├── {title}_2.wav   # 第2段口播音频
    │   └── ...             # 共10个音频文件
    ├── text/               # 生成的文本信息文件夹
    │   ├── script.json     # 缩写后的口播稿JSON文件
    │   └── keywords.json   # 关键词提取结果JSON文件
    └── final_video.mp4     # 最终合成的视频文件
```

**文件夹命名规则：**

- 每次运行都会在 `output` 目录下创建一个新的项目文件夹
- 文件夹名格式：`{title}_{月日_时分}`
- `title` 来自LLM第一次处理时生成的文档标题
- 时间格式为：月日_时分（如：0820_1430 表示 8月20日14:30）
- 特殊字符会被替换为下划线（空格、斜杠等）

**示例：**

- 文档标题："三体科幻小说" → 文件夹名："三体科幻小说_0820_1430"
- 文档标题："My Novel/Part 1" → 文件夹名："My_Novel_Part_1_0820_1430"

### 2. 口播稿JSON结构（text/script.json）

**LLM输出格式（核心内容）：**

```json
{
    "title": "文档标题",
    "segments": [
        {
            "content": "这是第一段口播内容，大约80字左右，需要保持语言流畅自然，适合语音播报。"
        },
        {
            "content": "这是第二段口播内容，继续讲述故事的主要情节和关键信息。"
        },
        {
            "content": "这是第三段口播内容..."
        }
    ]
}
```

**最终保存格式（系统处理后）：**

```json
{
    "title": "文档标题",
    "total_length": 800,
    "target_segments": 10,
    "actual_segments": 10,
    "created_time": "2024-01-15T10:30:00Z",
    "model_info": {
        "llm_server": "openrouter",
        "llm_model": "google/gemini-2.5-pro",
        "generation_type": "script_generation"
    },
    "segments": [
        {
            "index": 1,
            "content": "这是第一段口播内容，大约80字左右，需要保持语言流畅自然，适合语音播报。",
            "length": 42,
            "estimated_duration": 8.4
        },
        {
            "index": 2,
            "content": "这是第二段口播内容，继续讲述故事的主要情节和关键信息。",
            "length": 38,
            "estimated_duration": 7.6
        }
    ]
}
```

**字段说明：**

**LLM输出字段**（必须）：

- `title`: 字符串，从原文档提取或生成的标题
- `segments`: 数组，包含所有段落的口播内容
  - `content`: 字符串，该段的口播文本内容

**系统补充字段**（程序自动添加）：

- `total_length`: 整数，所有段落内容的总字数
- `target_segments`: 整数，用户指定的目标分段数
- `actual_segments`: 整数，实际生成的段落数
- `created_time`: 字符串，ISO 8601格式的创建时间
- `model_info`: 对象，使用的模型信息
  - `llm_server`: 字符串，LLM服务商（openrouter/siliconflow/aihubmix）
  - `llm_model`: 字符串，具体的LLM模型名称
  - `generation_type`: 字符串，生成类型（script_generation）
- `segments[].index`: 整数，段落序号（从1开始）
- `segments[].length`: 整数，该段的字符数
- `segments[].estimated_duration`: 浮点数，预估播放时长（秒）

**播放时长计算规则：**

- 语速标准：一分钟300字（中文普通话正常语速）
- 计算公式：`estimated_duration = length / 300 * 60`
- 示例：42字的内容 = 42 ÷ 300 × 60 = 8.4秒

### 3. 关键词JSON结构（text/keywords.json）

**LLM输出格式（核心内容）：**

```json
{
    "segments": [
        {
            "keywords": ["古代建筑", "红墙黄瓦", "庭院深深"],
            "atmosphere": ["庄严肃穆", "古韵悠长", "金辉洒地"]
        },
        {
            "keywords": ["江南水乡", "小桥流水", "青石板路"],
            "atmosphere": ["烟雨朦胧", "宁静致远", "诗意盎然"]
        },
        {
            "keywords": ["现代都市", "霓虹闪烁", "高楼大厦"],
            "atmosphere": ["繁华喧嚣", "光影交错", "现代感"]
        }
    ]
}
```

**保存格式（系统处理后）：**

```json
{
    "model_info": {
        "llm_server": "openrouter",
        "llm_model": "google/gemini-2.5-pro",
        "generation_type": "keywords_extraction"
    },
    "created_time": "2024-01-15T10:35:00Z",
    "segments": [
        {
            "keywords": ["古代建筑", "红墙黄瓦", "庭院深深"],
            "atmosphere": ["庄严肃穆", "古韵悠长", "金辉洒地"]
        },
        {
            "keywords": ["江南水乡", "小桥流水", "青石板路"],
            "atmosphere": ["烟雨朦胧", "宁静致远", "诗意盎然"]
        },
        {
            "keywords": ["现代都市", "霓虹闪烁", "高楼大厦"],
            "atmosphere": ["繁华喧嚣", "光影交错", "现代感"]
        }
    ]
}
```

**字段说明：**

- `model_info`: 对象，使用的模型信息
  - `llm_server`: 字符串，LLM服务商
  - `llm_model`: 字符串，具体的LLM模型名称
  - `generation_type`: 字符串，生成类型（keywords_extraction）
- `created_time`: 字符串，文件创建时间
- `segments`: 数组，每段的关键词信息
  - `keywords`: 字符串数组，画面内容关键词（物体、场景、人物等具象元素）
  - `atmosphere`: 字符串数组，氛围感关键词（情感、氛围、感觉等抽象元素）

**图片生成流程：**

1. LLM提取关键词 → 直接保存到keywords.json
2. 生成图片时：结合预设模板 + 用户风格设置 + 关键词 → 调用Seedream 3.0
3. 模板词组合规则：`[预设模板] + [用户风格] + [keywords] + [atmosphere] + [质量后缀]`

**关键词分类说明：**

- **keywords**：画面中可见的具体内容（如：古代建筑、红墙黄瓦、人物、动作等）
- **atmosphere**：画面的情感和氛围表达（如：庄严肃穆、温馨浪漫、紧张刺激等）

### 4. 程序返回值结构

```python
{
    "success": True,
    "message": "视频制作完成",
    "execution_time": 245.6,
    "script": {
        "file_path": "output/text/script.json",
        "total_length": 800,
        "segments_count": 10
    },
    "keywords": {
        "file_path": "output/text/keywords.json",
        "total_keywords": 28,
        "avg_per_segment": 2.8
    },
    "images": [
        "output/images/segment_1.png",
        "output/images/segment_2.png",
        "... (共10个文件)"
    ],
    "audio_files": [
        "output/voice/segment_1.wav",
        "output/voice/segment_2.wav",
        "... (共10个文件)"
    ],
    "final_video": "output/final_video.mp4",
    "statistics": {
        "original_length": 102345,
        "compression_ratio": "99.2%",
        "total_processing_time": 245.6,
        "llm_calls": 2,
        "image_generation_time": 120.3,
        "audio_generation_time": 45.2,
        "video_composition_time": 15.8
    }
}
```

**字段说明：**

- `success`: 布尔值，处理是否成功
- `message`: 字符串，处理结果消息
- `execution_time`: 浮点数，总执行时间（秒）
- `script`: 对象，口播稿相关信息
- `keywords`: 对象，关键词相关信息
- `images`: 字符串数组，生成图片的完整路径列表
- `audio_files`: 字符串数组，音频文件的完整路径列表
- `final_video`: 字符串，最终视频文件的完整路径
- `statistics`: 对象，详细的处理统计信息

## AI服务商支持

系统采用**自动服务商检测**机制，根据模型名称自动选择对应的服务商，无需手动指定。

### 大语言模型 (LLM)

**OpenRouter 服务商**（推荐）

- 通过OpenRouter统一调用多个顶级模型
- 支持模型：
  - `google/gemini-2.5-pro` - 最新Gemini模型，支持大容量文档处理
  - `anthropic/claude-sonnet-4` - Claude最新版本，擅长文学作品理解
  - `anthropic/claude-3.7-sonnet:thinking` - 支持思维链推理的Claude模型

**SiliconFlow 服务商**

- 兼容OpenAI SDK接口，国内访问稳定
- 推荐模型：
  - `zai-org/GLM-4.5` - 智谱AI最新版本
  - `moonshotai/Kimi-K2-Instruct` - 月之暗面Kimi模型
  - `Qwen/Qwen3-235B-A22B-Thinking-2507` - 阿里通义千问思维链模型

**aihubmix 代理服务商**（OpenAI兼容）

- 支持模型：`gpt-5`
- 通过代理访问OpenAI API

### 图像生成

**豆包 Seedream 3.0**

- 模型：`doubao-seedream-3-0-t2i-250415`
- 字节跳动旗下图像生成模型，支持中文提示词优化
- 基于火山引擎方舟SDK调用，生成质量高且响应速度快
- 支持参数：图像尺寸、引导强度、随机种子、水印控制

### 语音合成

**字节语音合成大模型**

- 使用WebSocket协议进行实时语音合成
- 支持多种高质量中文音色：
  - `zh_male_yuanboxiaoshu_moon_bigtts` - 男声（元伯小叔风格）
  - `zh_female_linjianvhai_moon_bigtts` - 女声（林建海风格）
  - `zh_male_yangguangqingnian_moon_bigtts` - 男声（阳光青年风格）
- 专为中文内容优化，发音自然流畅

## 环境与密钥

在 `.env` 中配置 LLM / 图像 / TTS 对应的密钥；具体示例见上方“快速开始”。

## 使用示例

最简用法：直接运行 `python main.py` 按提示操作；如需编程式调用，参考 `main()` 的参数简表。

## 支持的模型和参数

### 选项速览

- **尺寸**：使用 `config.SUPPORTED_IMAGE_SIZES` 列表中的任一值。
- **风格**：使用 `prompts.IMAGE_STYLE_PRESETS` 中的预设名。
- **音色**：选择 `_bigtts` 系列中文音色（如 `zh_male_yuanboxiaoshu_moon_bigtts`）。

## 注意事项

### 使用限制

- **文档格式**：支持EPUB和PDF格式（PDF建议为文本格式，非扫描件）
- **文档大小**：可处理10万字级别的长篇文档
- **目标字数**：500-1000字（系统会自动验证）
- **分段数量**：5-20段
- **图像生成**：受内容政策限制，避免敏感内容

### 系统需求

- **API密钥**：确保配置了所需的API密钥
- **网络连接**：需要稳定的互联网连接访问AI服务
- **存储空间**：每个视频项目约需要50-200MB空间
- **处理时间**：根据文档长度和分段数，处理时间约2-10分钟

### 错误处理

- 支持错误捕获与提示，建议先运行 `check_config.py` 验证配置。

## 项目结构

```
AIGC_Video/
├── main.py              # 主程序入口
├── functions.py         # 核心功能模块
├── config.py           # 配置管理
├── genai_api.py        # AI服务API接口
├── utils.py            # 工具函数
├── prompts.py          # AI提示词模板
├── check_config.py     # 配置检查工具
├── requirements.txt    # 依赖包列表
├── README.md          # 项目说明文档
├── .env               # 环境变量配置（需要自己创建）
├── input/             # 输入文件目录
└── output/            # 输出文件目录
    └── {项目名}_{时间}/
        ├── images/     # 生成的图片
        ├── voice/      # 生成的语音
        ├── text/       # 脚本和关键词
        └── final_video.mp4  # 最终视频
```
