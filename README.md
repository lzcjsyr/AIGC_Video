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
  - OpenAI代理: `gpt-5`
- `image_model`: 图像生成模型，当前支持 `doubao-seedream-3-0-t2i-250415`
- `voice`: 语音音色，如 `zh_male_yuanboxiaoshu_moon_bigtts`, `zh_female_linjianvhai_moon_bigtts`

**视觉参数**：
- `image_size`: 图像尺寸，支持多种比例（1024x1024, 1280x720, 720x1280等）
- `image_style_preset`: 预设风格（cinematic, documentary, artistic, minimalist, vintage）

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
  - `llm_server`: 字符串，LLM服务商（openrouter/siliconflow/openai）
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

**OpenAI 代理服务商**（aihubmix）
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

## 环境配置

### API密钥配置

在 `.env`文件中配置以下环境变量：

```env
# LLM服务商API密钥
OPENROUTER_API_KEY=你的OpenRouter API密钥
SILICONFLOW_KEY=你的SiliconFlow API密钥
AIHUBMIX_API_KEY=你的aihubmix代理API密钥

# 图像生成服务（豆包Seedream 3.0）
SEEDREAM_API_KEY=你的火山引擎方舟API密钥

# 语音合成服务（字节语音合成大模型）
BYTEDANCE_TTS_APPID=你的字节语音APPID
BYTEDANCE_TTS_ACCESS_TOKEN=你的字节语音ACCESS_TOKEN
BYTEDANCE_TTS_SECRET_KEY=你的字节语音SECRET_KEY（可选）
```

### 必需的API密钥

根据你选择的模型，需要配置对应的API密钥：

**LLM模型**：
- OpenRouter模型：需要 `OPENROUTER_API_KEY`
- SiliconFlow模型：需要 `SILICONFLOW_KEY`
- OpenAI代理模型：需要 `AIHUBMIX_API_KEY`

**图像生成**：
- 豆包Seedream 3.0：需要 `SEEDREAM_API_KEY`

**语音合成**：
- 字节语音合成：需要 `BYTEDANCE_TTS_APPID` 和 `BYTEDANCE_TTS_ACCESS_TOKEN`

### 依赖包安装

```bash
# 安装所有依赖包
pip install -r requirements.txt

# 或者手动安装
pip install openai>=1.12.0 requests>=2.31.0 python-dotenv>=1.0.0 Pillow>=10.0.0 \
            moviepy>=2.0.0 ebooklib>=0.18 PyPDF2>=3.0.1 pdfplumber>=0.9.0 \
            websockets>=11.0.0 "volcengine-python-sdk[ark]">=1.0.94
```

### 系统要求

- Python 3.8+
- 操作系统：macOS, Linux, Windows
- 内存：建议8GB以上（处理大型文档时）
- 硬盘：至少2GB可用空间（存储生成的视频文件）

## 使用示例

### 基础用法

**步骤1：准备输入文件**

```bash
# 在项目根目录创建input文件夹
mkdir input
# 将EPUB或PDF文件放入input文件夹
cp your_book.epub input/
# 或
cp your_book.pdf input/
```

**步骤2：运行程序**

```python
from main import main

# 自动读取input文件夹中的文件，生成800字10段视频
result = main(
    target_length=800,
    num_segments=10,
    image_size="1280x720",
    llm_model="google/gemini-2.5-pro",
    image_model="doubao-seedream-3-0-t2i-250415",
    voice="zh_male_yuanboxiaoshu_moon_bigtts",
    image_style_preset="cinematic",
    enable_subtitles=True
)

if result["success"]:
    print("视频制作完成！")
    print(f"口播稿段数: {result['script']['segments_count']}")
    print(f"生成图片数量: {len(result['images'])}")
    print(f"音频文件数量: {len(result['audio_files'])}")
    print(f"最终视频: {result['final_video']}")
    print(f"处理时间: {result['execution_time']:.1f}秒")
else:
    print(f"处理失败: {result['message']}")
```

### 高级配置示例

```python
# 指定具体文件路径和自定义参数
result = main(
    input_file="input/my_novel.epub",
    target_length=900,  # 生成900字口播稿
    num_segments=12,    # 分成12段
    image_size="1024x1024",
    llm_model="anthropic/claude-sonnet-4",
    image_model="doubao-seedream-3-0-t2i-250415",
    voice="zh_female_linjianvhai_moon_bigtts",
    image_style_preset="artistic",
    enable_subtitles=True,
    output_dir="custom_output"
)

# 使用思维链模型进行更精确的内容处理
result = main(
    input_file="input/complex_story.pdf",
    target_length=500,  # 生成500字短视频
    num_segments=8,     # 分成8段
    image_size="720x1280",  # 竖屏格式，适合短视频平台
    llm_model="anthropic/claude-3.7-sonnet:thinking",
    image_model="doubao-seedream-3-0-t2i-250415",
    voice="zh_male_yangguangqingnian_moon_bigtts",
    image_style_preset="documentary",
    enable_subtitles=False  # 禁用字幕
)

# 使用SiliconFlow的国产模型
result = main(
    input_file="input/history_book.pdf",
    target_length=800,
    num_segments=10,
    image_size="1280x720",
    llm_model="zai-org/GLM-4.5",  # 智谱AI模型
    image_model="doubao-seedream-3-0-t2i-250415",
    voice="zh_male_yuanboxiaoshu_moon_bigtts",
    image_style_preset="vintage",  # 复古风格
    enable_subtitles=True
)
```

## 支持的模型和参数

### 图像尺寸选项
```
"1024x1024"    # 1:1 方形，适合社交媒体
"1280x720"     # 16:9 横屏，适合YouTube等视频平台
"720x1280"     # 9:16 竖屏，适合抖音、快手等短视频
"864x1152"     # 3:4 竖屏，适合手机观看
"1152x864"     # 4:3 横屏，适合传统屏幕
"832x1248"     # 2:3 竖屏，适合海报风格
"1248x832"     # 3:2 横屏，适合摄影作品
"1512x648"     # 21:9 超宽屏，适合电影风格
```

### 图像风格预设
```
"cinematic"    # 电影级质感，温暖色调，细腻画风
"documentary"  # 纪录片风格，自然真实，高清摄影
"artistic"     # 艺术插画风格，色彩丰富，创意表现
"minimalist"   # 简约现代风格，干净构图，简洁配色
"vintage"      # 复古怀旧风格，胶片质感，暖色调
```

### 语音音色选项
```
"zh_male_yuanboxiaoshu_moon_bigtts"      # 男声（元伯小叔风格）
"zh_female_linjianvhai_moon_bigtts"      # 女声（林建海风格）
"zh_male_yangguangqingnian_moon_bigtts"  # 男声（阳光青年风格）
"ICL_zh_female_heainainai_tob"           # 女声（可爱风格）
```

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
- 程序具备完整的错误处理机制
- 支持API调用失败重试
- 详细的日志记录，便于问题排查
- 建议运行前使用 `check_config.py` 验证配置

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
