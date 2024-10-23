# 故事可视化程序

一个基于多种AI技术，将文本故事转换为富媒体内容的Python程序。本程序能够解析故事情节，生成相应的图像，创建语音叙述，并可选择性地将其组合成视频。

## 目录
- [输入参数说明](#输入参数说明)
- [输出结构说明](#输出结构说明)
- [AI服务商说明](#ai服务商说明)
- [环境配置](#环境配置)
- [使用示例](#使用示例)

## 输入参数说明

主函数`main()`接受以下参数：

```python
def main(
    story,              # 输入故事文本，至少1000字符
    num_plots=5,        # 故事分段数量，范围2-20
    num_images=1,       # 每个情节生成的图片数量，范围0-5
    image_size="1024x1024",  # 生成图片的尺寸
    llm_server="siliconflow",  # 大语言模型服务商
    llm_model="Qwen/Qwen2.5-72B-Instruct-128K",  # 大语言模型
    image_server="siliconflow",  # 图像生成服务商
    image_model="black-forest-labs/FLUX.1-schnell",  # 图像生成模型
    tts_server="openai",  # 语音合成服务商
    voice="alloy",      # 语音音色
    generate_video=False,  # 是否生成视频
    output_dir=None     # 输出目录，默认为桌面
)
```

## 输出结构说明

### 1. 文件夹结构
```
Story Visualization/
├── Images/           # 生成的图片文件夹
├── Audio/           # 生成的音频文件夹
├── Video/           # 生成的视频文件夹（如果启用）
├── [故事标题].docx    # 故事解析文档
└── image_prompts.docx  # 图片生成提示词文档
```

### 2. 故事解析输出（parsed_story）
```python
{
    "title": str,           # 故事标题
    "story_elements": list, # 故事元素列表
    "key_characters": [     # 关键角色列表
        {
            "name": str,    # 角色名称
            "role": str,    # 角色定位
            "traits": list  # 性格特征
        }
    ],
    "Segmentation": [      # 故事分段
        {
            "plot": str,    # 情节内容
            "plot_theme": list,  # 情节主题
            "characters_name": list  # 涉及角色
        }
    ]
}
```

### 3. 返回值结构
```python
{
    "parsed_story": dict,  # 故事解析结果
    "images": list,       # 生成图片的路径列表
    "image_prompts": str, # 图片提示词文档路径
    "final_video": str    # 最终视频路径（如果生成）
}
```

## AI服务商说明

### 大语言模型服务商 (llm_server)
- OpenAI
  - 建议直接选择“gpt-4o"
- SiliconFlow
  - 有大量模型可供选择，请参考[siliconflow.com](https://siliconflow.cn/zh-cn/models)。

### 图像生成服务商 (image_server)
- OpenAI
  - 建议直接选择"dall-e-3"
- SiliconFlow
  - 有大量模型可供选择，请参考[siliconflow.com](https://siliconflow.cn/zh-cn/models)。

### 语音合成服务商 (tts_server)
- OpenAI
  - 多个音色可选，每个音色都可以直接支持多种语言。具体介绍可在[OpenAI官方文档](https://platform.openai.com/docs/guides/text-to-speech)。
- Azure
  - 多个音色可选，详情请见[Azure Speech Studio](https://speech.microsoft.com/portal/)。

## 环境配置

### API密钥配置
在`.env`文件中配置以下环境变量：
```
AZURE_OPENAI_ENDPOINT=你的azure_openai终端点
AZURE_SPEECH_KEY=你的azure语音密钥
AZURE_SPEECH_REGION=你的azure区域
SILICONFLOW_KEY=你的硅流密钥
AIPROXY_API_KEY=你的代理密钥
AIPROXY_URL=你的代理地址
```

### 依赖包安装
```bash
pip install openai python-dotenv pillow python-docx moviepy azure-cognitiveservices-speech requests
```

## 使用示例

### 基础用法
```python
from main import main
from input_text_en import story

result = main(
    story,
    num_plots=5,
    num_images=1,
    image_size="1024x576",
    generate_video=False
)

if result:
    print("故事解析完成！")
    print(f"生成图片数量: {len(result['images'])}")
    if result["final_video"]:
        print(f"视频保存于: {result['final_video']}")
```

### 高级配置示例
```python
result = main(
    story,
    num_plots=5,
    num_images=2,
    image_size="1024x1024",
    llm_server="openai",
    llm_model="gpt-4",
    image_server="siliconflow",
    image_model="black-forest-labs/FLUX.1-schnell",
    tts_server="azure",
    voice="zh-CN-XiaoxiaoNeural",
    generate_video=True,
    output_dir="path/to/output"
)
```

## 注意事项

1. 输入限制
   - 故事文本至少1000字符
   - 分段数量限制在2-20之间
   - 每段图片数量限制在0-5之间

2. 服务限制
   - 需要确保所有相关API密钥可用
   - 图像生成受内容政策限制
   - 视频生成需要足够的磁盘空间

3. 错误处理
   - 程序会对各类错误进行处理并提供相应提示
   - 建议在使用前测试API连接状态

## 许可证

[待补充]