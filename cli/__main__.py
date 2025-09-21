"""
🚀 智能视频制作系统 - CLI参数配置
"""

# ====================================================================
#                           核心参数配置区
# ====================================================================
PARAMS = {
    # 内容生成参数
    "target_length": 800,                               # 目标字数 (500-3000)
    "num_segments": 6,                                  # 分段数量 (5-20)
    
    # 媒体参数
    "image_size": "1664x928",                           # 图像尺寸 (推荐横屏)
    "llm_model": "google/gemini-2.5-pro",               # LLM模型
    "image_model": "Qwen/Qwen-Image",                   # 图像模型 (见下方说明)
    "voice": "zh_male_yuanboxiaoshu_moon_bigtts",       # 语音音色
    
    # 风格参数
    "image_style_preset": "style05",                    # 图像风格预设
    "opening_image_style": "des01",                     # 开场图像风格
    
    # 输出参数
    "enable_subtitles": True,                           # 启用字幕
    "opening_quote": True,                               # 开场金句开关，True=包含, False=跳过
    "bgm_filename": "Ramin Djawadi - Light of the Seven.mp3"  # 背景音乐 (可为None)
}

"""
📝 核心参数说明：
- target_length: 目标字数 (500-3000，影响视频时长)
- num_segments: 分段数量 (5-20，影响内容结构)
- image_size: 图像尺寸 (见下方完整列表)
- llm_model: LLM模型 (推荐 google/gemini-2.5-pro)
- image_model: 图像生成模型 (见下方可选模型)
- voice: 语音音色 (字节大模型音色)
- image_style_preset: 图像风格 (style01-style10)，具体风格请查看 prompts.py
- opening_image_style: 开场图像风格 (des01-des10)，开场图像风格请查看 prompts.py

- enable_subtitles: 是否启用字幕
- opening_quote: 是否包含开场金句 (True=包含, False=跳过)
- bgm_filename: 背景音乐文件名 (放在项目根目录 music/ 下，不填则无BGM)

🧠 可选 LLM 模型（按服务商划分，自动根据模型名前缀识别服务商）
- openrouter:
  - google/gemini-2.5-pro
  - openai/gpt-5
  - anthropic/claude-sonnet-4
  - anthropic/claude-3.7-sonnet:thinking
- siliconflow:
  - zai-org/GLM-4.5
  - moonshotai/Kimi-K2-Instruct
  - Qwen/Qwen3-235B-A22B-Thinking-2507

🤖 可选图像模型：
- doubao-seedream-3-0-t2i-250415: V3模型，支持guidance_scale参数，单价0.275
- doubao-seedream-4-0-250828: V4模型，新版API，单价0.2
- Qwen/Qwen-Image: 通过 SiliconFlow 调用（已支持）

🎤 可选语音音色（字节 BigTTS 示例，可在 GUI 中查看更多预设）
- zh_male_yuanboxiaoshu_moon_bigtts (渊博小叔)
- zh_male_haoyuxiaoge_moon_bigtts (浩宇小哥)
- zh_female_sajiaonvyou_moon_bigtts (柔美女友)
- zh_female_yuanqinvyou_moon_bigtts (撒娇学妹)
- zh_female_gaolengyujie_moon_bigtts (高冷御姐)

🎨 图像风格配置：
- image_style_preset: 可选 style01-style10
- opening_image_style: 可选 des01-des10

📐 支持的图像尺寸 (豆包Seedream 3.0)：
- 1280x720: 16:9 宽屏横屏 (推荐，适合YouTube、B站等)
- 720x1280: 9:16 竖屏视频 (推荐，适合抖音、快手、小红书等)
- 1024x1024: 1:1 方形 (适合Instagram、微博等)
- 1152x864: 4:3 传统横屏 (适合传统屏幕比例)
- 864x1152: 3:4 竖屏 (适合手机竖屏内容)
- 1248x832: 3:2 横屏摄影 (适合摄影作品展示)
- 832x1248: 2:3 竖屏海报 (适合海报、书籍封面)
- 1512x648: 21:9 超宽屏 (适合横幅、封面图)

📐 支持的图像尺寸 (Qwen/Qwen-Image)：
- 1328x1328: 1:1 方形
- 1664x928: 16:9 横屏
- 928x1664: 9:16 竖屏
- 1472x1140: 4:3 横屏
- 1140x1472: 3:4 竖屏
- 1584x1056: 3:2 横屏
- 1056x1584: 2:3 竖屏
"""

# ====================================================================
#                           程序启动入口
# ====================================================================
if __name__ == "__main__":
    print("🚀 智能视频制作系统启动 (CLI)")
    
    # 设置项目路径
    import os
    import sys
    current_dir = os.path.dirname(__file__)
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    try:
        from cli.ui_helpers import run_cli_main, setup_cli_logging

        # 初始化 CLI 日志，使后续模块共享统一配置
        setup_cli_logging()

        result = run_cli_main(**PARAMS)
        
        # 处理结果
        if result.get("success"):
            if result.get("final_video"):
                print("\n🎉 视频制作完成！")
            else:
                step_msg = result.get("message") or "已完成当前步骤"
                print(f"\n✅ {step_msg}")
        else:
            msg = result.get('message', '未知错误')
            if isinstance(msg, str) and ("用户取消" in msg or "返回上一级" in msg):
                print("\n👋 已返回上一级")
            elif result.get('needs_prior_steps') or (isinstance(msg, str) and "需要先完成前置步骤" in msg):
                print(f"\nℹ️ {msg}")
            else:
                print(f"\n❌ 处理失败: {msg}")
                
    except ImportError as e:
        print(f"\n❌ 导入失败: {e}")
        print("请确保在项目根目录下运行此脚本")
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
