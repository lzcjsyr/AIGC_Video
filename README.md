# 智能故事可视化项目

## 项目简介

这个项目是一个智能故事可视化工具，它能够将长篇故事转化为简洁的摘要，并生成相应的图像和音频内容。项目利用了多种人工智能技术，包括自然语言处理、图像生成和语音合成，为用户提供了一种全新的故事体验方式。

## 主要功能

1. **故事摘要生成**：将长篇故事浓缩为2000-3000字的摘要，保留关键情节和主题。
2. **情节分割**：将故事划分为多个关键情节点。
3. **图像生成**：根据每个情节点生成相应的图像。
4. **语音合成**：将故事摘要转换为语音。

## 文件结构和变量说明

### input_text_cn.py 和 input_text_en.py

这两个文件分别包含中文和英文版本的输入文本和系统提示。它们包含以下重要变量：

1. **环境变量**：
   - `AZURE_OPENAI_ENDPOINT`：Azure OpenAI 服务的端点 URL。
   - `AZURE_OPENAI_KEY`：用于访问 Azure OpenAI 服务的 API 密钥。
   - `AZURE_SPEECH_KEY`：用于 Azure 语音服务的 API 密钥。
   - `AZURE_SPEECH_REGION`：Azure 语音服务所在的地理区域。
   - `SILICONFLOW_KEY`：用于访问 SiliconFlow API 的密钥（用于 FLUX 图像生成）。

2. **系统提示**：
   - `summarize_story_system_prompt`：用于指导 AI 模型如何总结故事的系统提示。
   - `plot_splitter_system_prompt`：用于指导 AI 模型如何分割故事情节的系统提示。
   - `generate_image_system_prompt`：用于指导 AI 模型如何生成图像提示的系统提示。

3. **故事文本**：
   - `story`：包含完整的故事文本，这是程序处理的主要输入。

这些变量在中英文版本中的结构相同，但内容会根据语言有所不同。

### functions.py

这个文件包含了项目的核心功能函数：

1. `summarize_story(client, story)`：生成故事摘要。
2. `plot_splitter(client, story, num_plots)`：将故事分割为指定数量的情节点。
3. `write_summary_and_plots(folder_path, summary_json, plots_json)`：将摘要和情节写入文件。
4. `generate_image_prompt(client, plot, regenerate=False)`：生成图像提示词。
5. `image_API(client, model_type, prompt)`：调用图像生成 API。
6. `generate_and_save_images(client, plots_json, plot_index, num_images, images_folder, model_type)`：生成和保存图像。
7. `text_to_speech(text, output_filename, voice_name)`：将文本转换为语音。

### main.py

这是项目的主要入口点，包含 `main()` 函数，该函数协调整个处理流程。

## 使用说明

### 主函数参数

在 `main.py` 中的 `main` 函数接受以下参数：

- `story` (字符串)：输入的故事文本，至少1000个字符。
- `model_type` (字符串)：图像生成模型类型，可选"FLUX"或"OpenAI"。默认为"FLUX"。
- `num_plots` (整数)：要生成的情节点数量，范围2-20。默认为5。
- `num_images` (整数)：每个情节点生成的图像数量，范围0-5。默认为1。
- `output_dir` (字符串)：输出目录路径。默认为用户桌面。
- `voice_name` (字符串)：语音合成使用的声音名称。默认为"en-US-JennyNeural"。如果设为None，则跳过音频生成。

### 环境变量设置

确保在项目根目录下的 `.env` 文件中正确设置以下环境变量：

```
AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
AZURE_OPENAI_KEY=your_azure_openai_key
AZURE_SPEECH_KEY=your_azure_speech_key
AZURE_SPEECH_REGION=your_azure_speech_region
SILICONFLOW_KEY=your_siliconflow_key
```

### 运行示例

```python
from main import main
from input_text_cn import story as chinese_story

result = main(chinese_story, 
              model_type="FLUX", 
              num_plots=5, 
              num_images=3, 
              output_dir=None, 
              voice_name="zh-CN-XiaoxiaoNeural")
```

## 输出内容

程序会在指定的输出目录（默认为桌面）创建一个名为"Story Visualization"的文件夹，其中包含：

1. `summary & plots.txt`：包含故事摘要和情节描述的文本文件。
2. `Images/`：存放生成的图像文件。
3. `image_prompts.txt`：记录用于生成图像的提示词。
4. `story_summary.wav`：故事摘要的音频文件。

## 注意事项

- 确保已安装所有必要的Python库和依赖项。您可能需要运行 `pip install -r requirements.txt`（假设您有一个 requirements.txt 文件）。
- 图像生成可能需要一些时间，特别是在生成多张图像时。
- 如果遇到内容政策违规，程序会尝试重新生成更安全的图像提示词。
- 音频生成依赖于网络连接和Azure服务的可用性。
- 对于中文故事，建议使用中文语音模型，如 "zh-CN-XiaoxiaoNeural"。

## 错误处理

程序包含了基本的错误处理机制。如果遇到问题，会在控制台输出相应的错误信息。常见的错误包括：

- 输入验证错误（如故事长度不足，参数超出范围等）
- API调用失败
- 文件读写错误

如果遇到无法解决的问题，请检查您的环境设置和输入参数，或联系开发团队寻求帮助。

## 扩展和自定义

- 您可以通过修改 `input_text_cn.py` 或 `input_text_en.py` 中的 `story` 变量来处理不同的故事。
- 可以通过调整系统提示（如 `summarize_story_system_prompt`）来改变 AI 模型的行为。
- 如果需要支持其他语言，可以创建新的输入文本文件，并相应地调整语音模型。

## 贡献

欢迎对本项目进行贡献！请遵循标准的 Git 工作流程，提交 pull requests 以供审核。

## 许可

[在此处添加您的许可信息]