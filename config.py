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
    SUPPORTED_INPUT_FORMATS = [".epub", ".pdf"]
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
    MAX_TARGET_LENGTH = 2000
    MIN_NUM_SEGMENTS = 5
    MAX_NUM_SEGMENTS = 20
    
    # 语音时长估算 (每分钟字数)
    SPEECH_SPEED_WPM = 300  # 中文普通话正常语速
    
    # 字幕配置
    SUBTITLE_CONFIG = {
        "enabled": True,                       # 是否启用字幕
        "font_size": 36,                       # 字体大小
        "font_family": None,                   # 字体（None使用系统默认字体）
        "color": "white",                      # 字体颜色
        "stroke_color": "black",               # 描边颜色
        "stroke_width": 3,                     # 描边宽度
        "position": ("center", "bottom"),      # 字幕位置
        "margin_bottom": 50,                   # 底部边距
        "max_chars_per_line": 25,              # 每行最大字符数
        "max_lines": 2,                        # 最大行数
        "line_spacing": 15,                    # 行间距
        "background_color": None,              # 背景色（None为透明）
        "background_opacity": 0.8,             # 背景透明度
        "shadow_enabled": False,               # 是否启用阴影效果（暂时禁用以解决位置问题）
        "shadow_color": "black",               # 阴影颜色
        "shadow_offset": (2, 2)                # 阴影偏移(x, y)，单位像素
    }
    
    # 音频混音配置（MoviePy 2.x）
    # BGM_DEFAULT_VOLUME: 背景音乐线性增益系数（通过 MultiplyVolume 应用，幅度相乘）。
    #   - 0.0 = 静音；1.0 = 原始电平；>1.0 = 放大（可能导致削波）。
    #   - 推荐区间: 0.03 ~ 0.20（常用 0.06 ~ 0.12）。
    #   - 背景音乐应显著低于口播；如需更响，建议同时降低口播or启用更弱 ducking。
    BGM_DEFAULT_VOLUME = 0.1

    # NARRATION_DEFAULT_VOLUME: 口播音轨线性增益系数（同上，混音前整体增益）。
    #   - 0.5 ~ 3.0 可用；推荐区间: 0.8 ~ 1.5（1.0 为原始电平）。
    #   - >2.0 易削波（若原始语音接近满幅）；建议同时下调 BGM。
    #   - 如追求响度一致，建议后续引入 limiter 或 loudness 正规化（非本项目默认）。
    NARRATION_DEFAULT_VOLUME = 2.0

    # 自动 Ducking（口播期间自动压低 BGM）：MoviePy 2.x 通过 transform 做时间变增益
    #   - AUDIO_DUCKING_ENABLED: 是否启用 ducking
    #   - AUDIO_DUCKING_STRENGTH: 压低强度（0~1），1 表示口播时将 BGM 完全压到 0；0.7 表示压到 30%（1-0.7）
    #   - AUDIO_DUCKING_SMOOTH_SECONDS: 包络平滑时间（秒），防止跳变突兀
    AUDIO_DUCKING_ENABLED = True
    AUDIO_DUCKING_STRENGTH = 0.3
    AUDIO_DUCKING_SMOOTH_SECONDS = 0.12
    
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