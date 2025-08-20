# 智能视频制作系统

一个基于多种AI技术的智能视频制作系统，将EPUB和PDF文档自动转换为短视频内容。系统通过LLM智能缩写、关键词提取、AI生图、语音合成等技术，实现从文档到视频的全自动化制作流程。

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

- 使用豆包TTS将口播稿转换为自然语音
- 为每个段落生成对应的音频文件
- **文件保存**：语音文件保存到 `output/{title}_{时间}/voice/segment_X.wav`（X为段落序号）

### 6. 视频合成

- 将对应的音频和图像进行匹配
- 合成完整的短视频内容
- **文件保存**：最终视频保存到 `output/{title}_{时间}/final_video.mp4`
- **处理摘要**：生成处理摘要信息保存到 `output/{title}_{时间}/text/summary.txt`

## 输入参数说明

主函数 `main()`接受以下参数：

```python
def main(
    input_file=None,    # 输入文件路径（EPUB或PDF文件），如为None则自动从input文件夹读取
    target_length=800,  # 缩写后的目标字数，范围500-1000字
    num_segments=10,    # 分段数量，默认10段
    image_style="",     # 图像风格提示词，用于统一视觉风格
    image_size="1024x1024",  # 生成图片的尺寸
    llm_server="openrouter",  # 大语言模型服务商
    llm_model="google/gemini-2.5-pro",  # 大语言模型
    image_server="doubao",  # 图像生成服务商
    image_model="Doubao-lite",  # 图像生成模型
    tts_server="doubao",  # 语音合成服务商
    voice="zh_female_qingxin",      # 语音音色
    output_dir="output"  # 输出目录，默认为当前目录下的output文件夹
)
```

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
    │   ├── segment_1.wav   # 第1段口播音频
    │   ├── segment_2.wav   # 第2段口播音频
    │   └── ...             # 共10个音频文件
    ├── text/               # 生成的文本信息文件夹
    │   ├── script.json     # 缩写后的口播稿JSON文件
    │   ├── keywords.json   # 关键词提取结果JSON文件
    │   └── summary.txt     # 处理摘要信息
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

**保存格式（直接保存LLM输出）：**

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

**字段说明：**

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

### 4. 处理摘要信息（text/summary.txt）

```
=== 文档处理摘要 ===
处理时间: 2024-01-15 10:30:00
原始文档: example.epub
原始字数: 102,345字
目标字数: 800字
实际字数: 798字
压缩比例: 99.2%
分段数量: 10段
```

### 5. 程序返回值结构

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
    "text_files": {
        "summary": "output/text/summary.txt"
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

## AI服务商说明

### 大语言模型服务商 (llm_server)

- OpenRouter（推荐）
  - 通过OpenRouter统一调用多个顶级模型
  - 支持模型：
    - `google/gemini-2.5-pro` - 最新Gemini模型，支持大容量文档处理
    - `anthropic/claude-sonnet-4` - Claude最新版本，擅长文学作品理解
    - `anthropic/claude-3.7-sonnet:thinking` - 支持思维链推理的Claude模型
- aihubmix代理（备选）
  - 仅支持"gpt-5"模型
  - 通过aihubmix代理访问OpenAI API
- SiliconFlow（备选）
  - Base URL: `https://api.siliconflow.cn/v1/`
  - 兼容OpenAI SDK接口
  - 推荐模型：
    - `zai-org/GLM-4.5` - 智谱AI最新版本
    - `moonshotai/Kimi-K2-Instruct` - 月之暗面Kimi模型
    - `Qwen/Qwen3-235B-A22B-Thinking-2507` - 阿里通义千问思维链模型
  - 更多模型可参考[siliconflow.com](https://siliconflow.cn/zh-cn/models)

### 图像生成服务商 (image_server)

- Doubao（豆包）
  - 使用豆包Seedream 3.0图像生成模型：`doubao-seedream-3-0-t2i-250415`
  - 字节跳动旗下的图像生成模型，支持中文提示词优化
  - 基于火山引擎方舟SDK调用，生成质量高且响应速度快
  - 支持参数：`size`（图像尺寸）、`guidance_scale`（引导强度）、`seed`（随机种子）、`watermark`（水印）

### 语音合成服务商 (tts_server)

- Doubao（豆包）
  - 字节跳动旗下的语音合成服务
  - 支持多种中文音色：zh_female_qingxin（清新女声）、zh_male_qingxin（清新男声）等
  - 专为中文内容优化，发音自然流畅
- OpenAI（备选）
  - 多个音色可选，每个音色都可以直接支持多种语言。具体介绍可在[OpenAI官方文档](https://platform.openai.com/docs/guides/text-to-speech)。

## 环境配置

### API密钥配置

在 `.env`文件中配置以下环境变量：

```
# 主要服务商配置
OPENROUTER_API_KEY=你的OpenRouter API密钥
ARK_API_KEY=你的火山引擎方舟API密钥

# 备选服务商配置
SILICONFLOW_KEY=你的硅流密钥
AIHUBMIX_API_KEY=你的aihubmix代理API密钥
```

### 依赖包安装

```bash
pip install openai python-dotenv pillow python-docx moviepy azure-cognitiveservices-speech requests google-generativeai anthropic ebooklib PyPDF2 pdfplumber
pip install --upgrade "volcengine-python-sdk[ark]"
```

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
    image_style="电影级质感，温暖色调，细腻画风",
    image_size="1024x576",
    llm_server="openrouter",
    llm_model="google/gemini-2.5-pro",
    image_server="doubao",
    image_model="Doubao-lite",
    tts_server="doubao",
    voice="zh_female_qingxin"
)

if result:
    print("视频制作完成！")
    print(f"口播稿段数: {len(result['script']['segments'])}")
    print(f"生成图片数量: {len(result['images'])}")
    print(f"音频文件数量: {len(result['audio_files'])}")
    print(f"最终视频: {result['final_video']}")
```

### 高级配置示例

```python
# 指定具体文件路径和自定义参数
result = main(
    input_file="input/my_novel.epub",
    target_length=900,  # 生成900字口播稿
    num_segments=12,    # 分成12段
    image_style="卡通风格，明亮色彩，Q版人物",
    image_size="1024x1024",
    llm_server="openrouter",
    llm_model="anthropic/claude-sonnet-4",
    image_server="doubao",
    image_model="Doubao-pro",
    tts_server="doubao",
    voice="zh_male_qingxin",
    output_dir="custom_output"
)

# 使用思维链模型进行更精确的内容处理
result = main(
    input_file="input/complex_story.pdf",
    target_length=500,  # 生成500字短视频
    num_segments=8,     # 分成8段
    image_style="科幻风格，未来感，霓虹灯光效果",
    llm_server="openrouter",
    llm_model="anthropic/claude-3.7-sonnet:thinking",
    image_server="doubao",
    image_model="Doubao-lite",
    tts_server="doubao",
    voice="zh_female_qingxin"
)
```

## 注意事项

1. 输入限制

   - 支持EPUB和PDF格式文件（可处理10万字级别的长篇文档）
   - 自动提取文档内容，从长篇内容中智能压缩核心要点
   - 目标字数范围：500-2000字
   - 分段数量范围：5-20段
   - PDF文件建议为文本格式（非扫描件）
2. 服务限制

   - 需要确保所有相关API密钥可用
   - 图像生成受内容政策限制
   - 视频生成需要足够的磁盘空间
3. 错误处理

   - 程序会对各类错误进行处理并提供相应提示
   - 建议在使用前测试API连接状态

## 许可证

[待补充]
