# 智能视频制作系统

一个基于LLM和多媒体AI的自动化视频制作平台，可将文档（EPUB/PDF/MOBI等）智能转换为带字幕、配音、BGM的专业短视频。

![系统架构](docs/architecture.png)

## ✨ 特性亮点

### 🤖 智能化流程
- **LLM智能缩写**：使用Google Gemini/Claude等模型将长文档压缩为口播稿
- **关键词提取**：自动提取每段落的视觉关键词和氛围词  
- **AI图像生成**：集成豆包Seedream 3.0，支持多种尺寸和风格预设
- **语音合成**：字节跳动TTS大模型，高质量中文语音输出
- **视频合成**：基于MoviePy 2.x，支持字幕、开场金句、背景音乐

### 📱 双端支持
- **CLI版本**：命令行界面，支持自动和分步执行模式
- **Web版本**：Vue3 + Flask，提供可视化操作界面和实时进度

### 🔧 灵活配置
- **多服务商支持**：OpenRouter、SiliconFlow、AIHubMix等
- **丰富的参数配置**：字数、段数、画面风格、音色选择
- **项目管理**：支持项目保存、重新执行指定步骤
- **文件格式支持**：PDF、EPUB、MOBI、AZW3、DOCX等

## 🚀 快速开始

### 环境要求
- Python 3.8+
- Node.js 16+（Web版）
- FFmpeg（视频处理）

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置API密钥
创建 `.env` 文件并配置必要的API密钥：
```env
# LLM服务（至少配置一个）
OPENROUTER_API_KEY=your_openrouter_key
SILICONFLOW_KEY=your_siliconflow_key  
AIHUBMIX_API_KEY=your_aihubmix_key

# 图像生成（必需）
SEEDREAM_API_KEY=your_seedream_key

# 语音合成（必需）
BYTEDANCE_TTS_APPID=your_appid
BYTEDANCE_TTS_ACCESS_TOKEN=your_access_token
```

### 3. 验证配置
```bash
python check_config.py
```

### 4. 启动系统

**CLI版本（推荐）**：
```bash
python -m cli
```

**Web版本**：
```bash
cd web && python start_web.py
```
然后访问 http://localhost:3000

## 📋 工作流程

### 标准5步处理流程

1. **📖 文档读取与智能缩写**
   - 支持多种文档格式解析
   - LLM智能压缩为目标字数的口播稿
   - 生成标题、开场金句、正文内容

2. **✂️ 脚本分段处理**  
   - 基于标点符号的智能分段算法
   - 保持语义完整性的同时均衡段落长度
   - 生成时长估算和段落索引

3. **🏷️ 关键词提取**
   - 为每个段落提取视觉关键词
   - 生成氛围词增强画面表现力
   - 优化图像生成提示词质量

4. **🎨 AI图像生成**
   - 豆包Seedream 3.0多尺寸图像生成
   - 6种预设风格（概念极简、俯视古典等）
   - 自动重试机制处理敏感内容

5. **🎵 音频与视频合成**
   - 高质量TTS语音合成
   - MoviePy视频合成与字幕添加
   - 背景音乐混合与音频效果处理

### 输出结构
```
output/
└── {title}_{MMDD_HHMM}/
    ├── images/
    │   ├── opening.png              # 开场图像
    │   └── segment_{1..N}.png       # 段落图像
    ├── voice/
    │   ├── opening.wav              # 开场金句音频
    │   └── voice_{1..N}.wav         # 段落配音
    ├── text/
    │   ├── raw.json                 # 原始LLM输出
    │   ├── raw.docx                 # 可编辑版本
    │   ├── script.json              # 分段脚本
    │   ├── script.docx              # 阅读版本
    │   └── keywords.json            # 关键词数据
    └── final_video.mp4              # 最终视频
```

## ⚙️ 配置参数

### 核心参数
```python
# 文本处理
target_length = 1000      # 目标字数 (500-3000)
num_segments = 10         # 分段数量 (5-20)

# 模型配置
llm_model = "google/gemini-2.5-pro"           # LLM模型
image_model = "doubao-seedream-3-0-t2i-250415" # 图像模型  
voice = "zh_male_yuanboxiaoshu_moon_bigtts"   # 音色

# 视觉效果
image_size = "1280x720"           # 图像尺寸
image_style_preset = "style05"    # 风格预设
opening_image_style = "des01"     # 开场图像风格

# 音频视频
enable_subtitles = True          # 启用字幕
bgm_filename = "bgm.mp3"        # 背景音乐
```

### 支持的图像尺寸
- `1024x1024` - 正方形，适合头像、产品图
- `1280x720` - 16:9横屏，适合视频内容
- `720x1280` - 9:16竖屏，适合短视频平台
- `864x1152` - 3:4竖屏，适合手机内容
- `832x1248` - 2:3竖屏，适合海报封面
- `1152x864` - 4:3横屏，适合传统比例
- `1248x832` - 3:2横屏，适合摄影作品
- `1512x648` - 21:9超宽屏，适合横幅图

## 🛠️ 高级功能

### 项目管理
- **重跑机制**：支持从任意步骤重新执行
- **文件编辑**：可编辑生成的DOCX文件后重新处理
- **进度检测**：智能检测项目完成状态
- **资源管理**：自动清理下游产物避免冲突

### 字幕系统
```python
SUBTITLE_CONFIG = {
    "font_family": "/System/Library/Fonts/PingFang.ttc",
    "font_size": 36,
    "color": "white", 
    "stroke_color": "black",
    "stroke_width": 3,
    "max_chars_per_line": 25,
    "position": ("center", "bottom")
}
```

### 音频增强
- **音量控制**：独立调节BGM和口播音量
- **自动Ducking**：口播时自动降低BGM音量  
- **淡入淡出**：开场渐显和片尾淡出效果
- **音频循环**：BGM自动循环匹配视频时长

## 🌐 Web版特性

### 前端界面
- 📁 拖拽上传文档文件
- ⚙️ 可视化参数配置界面  
- 📊 实时任务进度显示
- 📋 项目历史管理
- 🎬 在线视频预览和下载

### 后端API
- 🔄 异步任务处理
- 📡 WebSocket实时通信
- 🌐 RESTful API设计
- 🔌 完全复用CLI核心功能

### 技术栈
- **前端**：Vue3 + Element Plus + Vite + Pinia
- **后端**：Flask + SocketIO + 多线程任务队列
- **通信**：REST API + WebSocket实时推送

## 🧰 工具集

### 独立工具
- **文档统计工具**：`tools/check_text_stats.py` - 分析文档字数和Token数量
- **单独生成工具**：`tools/gen_single_media.py` - 独立测试图像和音频生成
- **配置检查工具**：`check_config.py` - 验证API密钥和环境配置

### 开发工具
```bash
# 文档统计
python tools/check_text_stats.py --interactive

# 单独测试图像生成
python tools/gen_single_media.py

# 配置验证
python check_config.py
```

## 📚 架构设计

### 核心模块
```
core/
├── document_reader.py    # 统一文档解析器
├── text.py              # 文本处理和分段算法  
├── services.py          # API服务调用封装
├── media.py             # 图像和音频生成
├── video_composer.py    # 视频合成和特效
├── pipeline.py          # 流程编排和状态管理
├── validators.py        # 参数验证和服务商检测
└── routers.py           # 公共API路由
```

### 配置管理
- `config.py` - 全局配置管理类
- `prompts.py` - 提示词模板和图像风格
- `utils.py` - 通用工具函数和项目管理

### 接口层
- `cli/` - 命令行界面和交互逻辑
- `web/` - Web界面和API服务

## 📝 使用技巧

### 文档准备
- PDF文件建议使用可复制文本版本（非扫描版）
- EPUB和MOBI格式支持更好的文本提取
- 文档内容建议在5000-50000字之间

### 参数调优
- **目标字数**：根据最终视频时长需求调整（1000字约3-4分钟）
- **分段数量**：建议10-15段，保持每段20-30秒
- **图像风格**：根据内容类型选择合适的预设风格

### 性能优化
- 大文档建议使用分步模式，可随时调整参数
- 图像生成失败时会自动重试，敏感内容会被跳过
- 可通过编辑DOCX文件精细调整内容

## 🔍 故障排除

### 常见问题
1. **API调用失败**：检查网络连接和API密钥配置
2. **文档读取错误**：确认文件格式和编码正确
3. **视频合成失败**：检查FFmpeg安装和音视频文件完整性
4. **内存不足**：处理大文档时建议增加系统内存

### 日志调试
- CLI模式：查看 `cli/cli.log`
- Web模式：查看 `web/backend/web.log`
- 通用日志：查看项目根目录 `aigc_video.log`

## 🤝 贡献指南

### 开发环境设置
```bash
# 克隆仓库
git clone <repository>
cd AIGC_Video

# 安装依赖
pip install -r requirements.txt
pip install -r web/backend/requirements.txt

# 安装前端依赖
cd web/frontend && npm install
```

### 代码结构规范
- 遵循现有的模块化架构设计
- 新功能优先考虑复用现有核心模块
- 添加适当的类型注解和文档字符串
- 确保CLI和Web版本功能一致性

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持

- 🐛 提交Bug：[GitHub Issues](https://github.com/your-repo/issues)
- 💡 功能建议：[GitHub Discussions](https://github.com/your-repo/discussions)  
- 📖 文档wiki：[项目Wiki](https://github.com/your-repo/wiki)

---

**智能视频制作系统** - 让AI为你的内容赋能 🚀
