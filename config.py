"""
智能视频制作系统 - 配置管理模块
统一管理所有配置项、API密钥和系统参数
"""

import os
from dotenv import load_dotenv
from typing import Dict, Any

# 加载环境变量
load_dotenv()

class Config:
    """系统配置类，统一管理所有配置项"""
    
    # API 配置
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    SEEDREAM_API_KEY = os.getenv('SEEDREAM_API_KEY')
    SILICONFLOW_KEY = os.getenv('SILICONFLOW_KEY')
    AIHUBMIX_API_KEY = os.getenv('AIHUBMIX_API_KEY')
    
    # 字节语音合成大模型配置
    BYTEDANCE_TTS_APPID = os.getenv('BYTEDANCE_TTS_APPID')
    BYTEDANCE_TTS_ACCESS_TOKEN = os.getenv('BYTEDANCE_TTS_ACCESS_TOKEN')
    BYTEDANCE_TTS_SECRET_KEY = os.getenv('BYTEDANCE_TTS_SECRET_KEY')
    
    # API 端点配置
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
    ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    AIHUBMIX_URL = "https://aihubmix.com/v1"
    
    # 默认参数配置
    DEFAULT_TARGET_LENGTH = 1000  # 默认目标字数
    DEFAULT_NUM_SEGMENTS = 10    # 默认分段数
    DEFAULT_IMAGE_SIZE = "1024x1024"  # 默认图像尺寸
    DEFAULT_VOICE = "zh_male_yuanboxiaoshu_moon_bigtts"  # 默认语音（字节语音合成大模型）
    
    # 支持的服务商和模型
    SUPPORTED_LLM_SERVERS = ["openrouter", "siliconflow", "aihubmix"]  # 都使用OpenAI兼容接口
    SUPPORTED_IMAGE_SERVERS = ["doubao"]  # 只支持火山引擎豆包
    SUPPORTED_TTS_SERVERS = ["bytedance"]    # 只支持字节语音合成大模型
    
    # 推荐的模型配置
    RECOMMENDED_MODELS = {
        "llm": {
            "openrouter": [
                "google/gemini-2.5-pro",
                "anthropic/claude-sonnet-4",
                "anthropic/claude-3.7-sonnet:thinking"
            ],
            "siliconflow": [
                "zai-org/GLM-4.5",
                "moonshotai/Kimi-K2-Instruct",
                "Qwen/Qwen3-235B-A22B-Thinking-2507"
            ],
            "aihubmix": ["gpt-5"]  # aihubmix代理仅支持gpt-5模型
        },
        "image": {
            "doubao": ["doubao-seedream-3-0-t2i-250415"]
        },
        "tts": {
            "bytedance": ["bytedance-bigtts"]  # 字节语音合成大模型
        }
    }
    
    
    # 文件格式支持
    SUPPORTED_INPUT_FORMATS = [".epub", ".pdf", ".mobi", ".docx", ".doc"]
    # 豆包Seedream 3.0支持的图像尺寸
    SUPPORTED_IMAGE_SIZES = [
        "1024x1024",  # 1:1 - 方形，适合头像、产品图
        "864x1152",   # 3:4 - 竖屏，适合手机竖屏内容
        "1152x864",   # 4:3 - 横屏，适合传统屏幕比例
        "1280x720",   # 16:9 - 宽屏，适合视频横屏内容
        "720x1280",   # 9:16 - 竖屏视频，适合抖音、快手等
        "832x1248",   # 2:3 - 竖屏，适合海报、书籍封面
        "1248x832",   # 3:2 - 横屏，适合摄影作品
        "1512x648"    # 21:9 - 超宽屏，适合横幅、封面图
    ]
    
    
    # 输出路径配置
    DEFAULT_OUTPUT_DIR = "output"
    OUTPUT_STRUCTURE = {
        "images": "images",
        "voice": "voice", 
        "text": "text"
    }
    
    # 处理限制
    MIN_TARGET_LENGTH = 500
    MAX_TARGET_LENGTH = 3000
    MIN_NUM_SEGMENTS = 5
    MAX_NUM_SEGMENTS = 20
    
    # 语音时长估算 (每分钟字数)
    SPEECH_SPEED_WPM = 250  # 中文普通话正常语速
    
    # LLM 生成参数配置
    LLM_TEMPERATURE_SCRIPT = 0.7   # 智能缩写(脚本生成)的temperature参数，范围0-1，越大越随机
    LLM_TEMPERATURE_KEYWORDS = 0.5 # 关键词提取的temperature参数，范围0-1，越大越随机
    
    # 字幕配置
    SUBTITLE_CONFIG = {
        "enabled": True,                       # 是否启用字幕
        "font_size": 36,                       # 字体大小
        # 字体设置：
        # - 建议填写“绝对路径”最稳妥，能确保在不同环境下渲染一致（以下为常见的 macOS 路径示例）：
        #     1) 宋体风格（接近思源宋体 Source Han Serif）：
        #        /System/Library/Fonts/Supplemental/Songti.ttc
        #     2) 黑体风格（接近思源黑体 Source Han Sans）：
        #        /System/Library/Fonts/PingFang.ttc
        #        /System/Library/Fonts/Hiragino Sans GB.ttc
        # - 也可以直接写字体名（稳定性略差，依赖 Pillow 的字体解析）：
        #     "Songti SC"、"PingFang SC"、"Hiragino Sans GB"
        # - 留空(None) 时使用系统默认字体，可能导致中文显示/风格不如预期。
        "font_family": "/System/Library/Fonts/PingFang.ttc",
        "color": "white",                      # 字体颜色
        "stroke_color": "black",               # 描边颜色
        "stroke_width": 3,                     # 描边宽度
        "position": ("center", "bottom"),      # 字幕位置
        "margin_bottom": 50,                   # 底部边距
        "max_chars_per_line": 25,              # 每行最大字符数
        "max_lines": 1,                        # 最大行数
        "line_spacing": 15,                    # 行间距
        "background_color": None,              # 背景色（None为透明）
        "background_opacity": 0.8,             # 背景透明度
        "shadow_enabled": False,               # 是否启用阴影效果（暂时禁用以解决位置问题）
        "shadow_color": "black",               # 阴影颜色
        "shadow_offset": (2, 2)                # 阴影偏移(x, y)，单位像素
    }
    
    # 背景音乐增益（0=静音, 1=原始, >1放大；推荐0.03~0.20）
    BGM_DEFAULT_VOLUME = 0.2

    # 口播增益（可用0.5~3.0，推荐0.8~1.5；>2.0有削波风险）
    NARRATION_DEFAULT_VOLUME = 2.0

    # 口播期间压低BGM（强度0~1；平滑秒数避免突兀）
    AUDIO_DUCKING_ENABLED = False
    AUDIO_DUCKING_STRENGTH = 0.3
    AUDIO_DUCKING_SMOOTH_SECONDS = 0.12   

    # 开场渐显秒数（对首帧/开场片段从黑到正常）
    OPENING_FADEIN_SECONDS = 2.0

    # 开场口播结束后画面停留秒数
    OPENING_HOLD_AFTER_NARRATION_SECONDS = 2.0

    # 开场金句样式参数
    OPENING_QUOTE_STYLE = {
        "enabled": True,                 # 是否显示开场金句
        "font_family": "/System/Library/Fonts/PingFang.ttc",  # 字体（建议绝对路径）
        "font_size": 48,                 # 字体大小（将基于字幕字号的放大系数补正）
        "font_scale": 1.3,               # 在字幕基础字号上的缩放系数
        "color": "white",                # 文字颜色
        "stroke_color": "black",         # 描边颜色
        "stroke_width": 4,               # 描边宽度
        "position": ("center", "center"),  # 居中
        "max_lines": 4,                  # 最大行数（过长自动换行）
        "max_chars_per_line": 18,        # 每行最大字符数（用于开场金句换行）
        "line_spacing": 8,               # 行间距（像素，开场金句专用）
        "letter_spacing": 0,             # 字间距（以空格数量近似控制，0 表示不加）
    }
    
    # 片尾参数: 片尾静帧与淡出秒数
    ENDING_FADE_SECONDS = 2.5
    
    # ================================================================================
    # 系统配置验证方法（一般无需修改）
    # ================================================================================
    
    @classmethod
    def validate_api_keys(cls) -> Dict[str, bool]:
        """验证API密钥配置"""
        return {
            "openrouter": bool(cls.OPENROUTER_API_KEY),
            "seedream": bool(cls.SEEDREAM_API_KEY),  # 用于豆包图像生成
            "bytedance_tts": bool(cls.BYTEDANCE_TTS_APPID and cls.BYTEDANCE_TTS_ACCESS_TOKEN),  # 用于字节语音合成
            "siliconflow": bool(cls.SILICONFLOW_KEY),
            "aihubmix": bool(cls.AIHUBMIX_API_KEY)
        }
    
    @classmethod
    def get_required_keys_for_config(cls, llm_server: str, image_server: str, tts_server: str) -> list:
        """获取指定配置所需的API密钥"""
        required_keys = []
        
        if llm_server == "openrouter":
            required_keys.append("OPENROUTER_API_KEY")
        elif llm_server == "aihubmix":
            required_keys.append("AIHUBMIX_API_KEY")
        elif llm_server == "siliconflow":
            required_keys.append("SILICONFLOW_KEY")
            
        if image_server == "doubao":
            required_keys.append("SEEDREAM_API_KEY")
            
        if tts_server == "bytedance":
            required_keys.append("BYTEDANCE_TTS_APPID")
            required_keys.append("BYTEDANCE_TTS_ACCESS_TOKEN")
            
        return list(set(required_keys))  # 去重
    
    
    @classmethod
    def validate_parameters(cls, target_length: int, num_segments: int, 
                          llm_server: str, image_server: str, tts_server: str, image_size: str = None) -> None:
        """验证参数有效性"""
        if not cls.MIN_TARGET_LENGTH <= target_length <= cls.MAX_TARGET_LENGTH:
            raise ValueError(f"target_length必须在{cls.MIN_TARGET_LENGTH}-{cls.MAX_TARGET_LENGTH}之间")
        
        if not cls.MIN_NUM_SEGMENTS <= num_segments <= cls.MAX_NUM_SEGMENTS:
            raise ValueError(f"num_segments必须在{cls.MIN_NUM_SEGMENTS}-{cls.MAX_NUM_SEGMENTS}之间")
        
        if llm_server not in cls.SUPPORTED_LLM_SERVERS:
            raise ValueError(f"不支持的LLM服务商: {llm_server}，支持: {cls.SUPPORTED_LLM_SERVERS}")
        
        if image_server not in cls.SUPPORTED_IMAGE_SERVERS:
            raise ValueError(f"不支持的图像服务商: {image_server}，支持: {cls.SUPPORTED_IMAGE_SERVERS}")
        
        if tts_server not in cls.SUPPORTED_TTS_SERVERS:
            raise ValueError(f"不支持的TTS服务商: {tts_server}，支持: {cls.SUPPORTED_TTS_SERVERS}")
        
        if image_size and image_size not in cls.SUPPORTED_IMAGE_SIZES:
            available_sizes = ", ".join(cls.SUPPORTED_IMAGE_SIZES)
            raise ValueError(f"不支持的图像尺寸: {image_size}，支持的尺寸: {available_sizes}")

# 创建配置实例
config = Config()

# 导出常用配置
__all__ = [
    'Config', 'config',
    'SUPPORTED_LLM_SERVERS', 'SUPPORTED_IMAGE_SERVERS', 'SUPPORTED_TTS_SERVERS',
    'RECOMMENDED_MODELS', 'SUPPORTED_IMAGE_SIZES'
]