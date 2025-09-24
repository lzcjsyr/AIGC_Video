"""
智能视频制作系统 - 配置管理模块
统一管理所有配置项、API密钥和系统参数
"""

import os
from dotenv import load_dotenv
from typing import Dict
from copy import deepcopy

# 加载环境变量
load_dotenv()

# ████████████████████████████████████████████████████████████████████████████████
# ██                            用户常调参数区域                                  ██
# ██                     (经常需要调整的参数放在这里)                               ██
# ████████████████████████████████████████████████████████████████████████████████

# ==================== 默认生成参数 ====================
DEFAULT_GENERATION_PARAMS = {
    "target_length": 1500,                          # 目标字数
    "num_segments": 10,                             # 视频分段数量
    "image_size": "2560x1440",                      # 图像尺寸 (常用 16:9 横屏，Qwen-Image固定支持)
    "video_size": "1280x720",                      # 最终视频导出尺寸（可与image_size不同）
    "llm_model": "moonshotai/Kimi-K2-Instruct-0905",          # 文本生成模型
    "image_model": "doubao-seedream-4-0-250828",              # 图像生成模型
    "voice": "zh_male_yuanboxiaoshu_moon_bigtts",  # 语音音色
    "image_style_preset": "style05",               # 图像风格预设 (详见 prompts.py)
    "opening_image_style": "des01",                # 开场图像风格 (详见 prompts.py)
    "images_method": "keywords",                   # 配图生成方式: keywords / description
    "enable_subtitles": True,                      # 是否启用字幕
    "opening_quote": True,                         # 是否加入开场金句
    "bgm_filename": "Under No Flag.mp3"  # 背景音乐文件名 (music/ 下，可为 None)
}

# 常用 LLM 模型: google/gemini-2.5-pro, anthropic/claude-sonnet-4, openai/gpt-5, moonshotai/Kimi-K2-Instruct-0905
# 常用图像模型尺寸规则说明：
# - doubao-seedream-4-0-250828：支持任意 WxH，范围 [1280x720, 4096x4096]，包含端点
# - doubao-seedream-3-0-t2i-250415：支持任意 WxH，范围 [512x512, 2048x2048]，包含端点
# - Qwen/Qwen-Image：仅支持固定尺寸集合（见 SUPPORTED_QWEN_IMAGE_SIZES）
# 常用语音音色: zh_male_yuanboxiaoshu_moon_bigtts, zh_male_haoyuxiaoge_moon_bigtts, zh_female_sajiaonvyou_moon_bigtts

# ==================== LLM 模型生成参数 ====================
LLM_TEMPERATURE_SCRIPT = 0.7            # 脚本生成随机性 (0-1，越大越随机)
LLM_TEMPERATURE_KEYWORDS = 0.5          # 要点提取随机性 (0-1，越大越随机)

# ==================== 音频控制参数 ====================
BGM_DEFAULT_VOLUME = 0.23                # 背景音乐音量 (0=静音, 1=原音, >1放大, 推荐0.03-0.20)
NARRATION_DEFAULT_VOLUME = 2.0          # 口播音量 (0.5-3.0, 推荐0.8-1.5, >2.0有削波风险)
AUDIO_DUCKING_ENABLED = False           # 口播时是否压低BGM
AUDIO_DUCKING_STRENGTH = 0.3            # BGM压低强度 (0-1)
AUDIO_DUCKING_SMOOTH_SECONDS = 0.12     # 音量过渡平滑时间 (秒)

# ==================== 视觉效果时间参数 ====================
OPENING_FADEIN_SECONDS = 2.0                    # 开场渐显时长 (秒)
OPENING_HOLD_AFTER_NARRATION_SECONDS = 2.0      # 开场口播后停留时长 (秒)
ENDING_FADE_SECONDS = 2.5                       # 片尾淡出时长 (秒)

# ==================== 字幕样式配置 ====================
SUBTITLE_CONFIG = {
    "enabled": True,                       # 是否启用字幕
    "font_size": 36,                       # 字体大小
    # 字体路径建议：
    # macOS 苹方字体: /System/Library/Fonts/PingFang.ttc
    # macOS 宋体: /System/Library/Fonts/Supplemental/Songti.ttc
    # Windows 微软雅黑: C:/Windows/Fonts/msyh.ttc
    "font_family": "/System/Library/Fonts/PingFang.ttc",
    "color": "white",                      # 文字颜色
    "stroke_color": "black",               # 描边颜色
    "stroke_width": 3,                     # 描边粗细
    "position": ("center", "bottom"),      # 位置 (水平, 垂直)
    "margin_bottom": 50,                   # 距底部距离 (像素)
    "max_chars_per_line": 25,              # 每行最大字符数
    "max_lines": 1,                        # 最大行数
    "line_spacing": 15,                    # 行间距 (像素)
    "background_color": (0, 0, 0),         # 背景色 (RGB, None=透明)
    "background_opacity": 0.8,             # 背景不透明度 (0-1)
    "background_horizontal_padding": 20,   # 背景水平内边距 (像素)
    "background_vertical_padding": 10,     # 背景垂直内边距 (像素)
    "shadow_enabled": False,               # 是否启用文字阴影
    "shadow_color": "black",               # 阴影颜色
    "shadow_offset": (2, 2)                # 阴影偏移 (x, y)
}

# ==================== 开场金句样式配置 ====================
OPENING_QUOTE_STYLE = {
    "enabled": True,                              # 是否显示开场金句
    "font_family": "/System/Library/Fonts/PingFang.ttc",  # 字体路径
    "font_size": 48,                              # 基础字体大小
    "font_scale": 1.3,                            # 相对字幕字体的缩放倍数
    "color": "white",                             # 文字颜色
    "stroke_color": "black",                      # 描边颜色
    "stroke_width": 4,                            # 描边粗细
    "position": ("center", "center"),             # 位置 (居中显示)
    "max_lines": 6,                               # 最大行数
    "max_chars_per_line": 20,                     # 每行最大字符数
    "line_spacing": 20,                           # 行间距 (像素)
    "letter_spacing": 0,                          # 字间距 (0=正常)
}

# ==================== 性能控制参数 ====================
MAX_CONCURRENT_IMAGE_GENERATION = 5  # 图片生成最大并发数
MAX_CONCURRENT_VOICE_SYNTHESIS = 5   # 语音合成最大并发数

# ==================== 视频素材处理配置 ====================
VIDEO_MATERIAL_CONFIG = {
    "supported_formats": [".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".m4v"],
    "target_fps": 30,                     # 目标帧率 (有视频素材时)
    "remove_original_audio": True,        # 是否移除原音频
    "duration_adjustment": "stretch",     # 时长调整方式: stretch/crop
    "resize_method": "crop"               # 尺寸调整方式: crop/stretch
}

# ==================== 图片素材处理配置 ====================
IMAGE_MATERIAL_CONFIG = {
    "target_fps": 15  # 纯图片素材时的帧率
}

# ████████████████████████████████████████████████████████████████████████████████
# ██                            系统配置区域                                     ██
# ██                     (一般无需修改的系统参数)                                  ██
# ████████████████████████████████████████████████████████████████████████████████

def get_default_generation_params() -> Dict[str, object]:
    """返回默认生成参数的拷贝，避免调用方修改全局配置"""
    return deepcopy(DEFAULT_GENERATION_PARAMS)
    
class Config:
    """系统配置类，统一管理所有配置项"""

    # 引用模块级常量
    LLM_TEMPERATURE_SCRIPT = LLM_TEMPERATURE_SCRIPT
    LLM_TEMPERATURE_KEYWORDS = LLM_TEMPERATURE_KEYWORDS
    BGM_DEFAULT_VOLUME = BGM_DEFAULT_VOLUME
    NARRATION_DEFAULT_VOLUME = NARRATION_DEFAULT_VOLUME
    AUDIO_DUCKING_ENABLED = AUDIO_DUCKING_ENABLED
    AUDIO_DUCKING_STRENGTH = AUDIO_DUCKING_STRENGTH
    AUDIO_DUCKING_SMOOTH_SECONDS = AUDIO_DUCKING_SMOOTH_SECONDS
    OPENING_FADEIN_SECONDS = OPENING_FADEIN_SECONDS
    OPENING_HOLD_AFTER_NARRATION_SECONDS = OPENING_HOLD_AFTER_NARRATION_SECONDS
    ENDING_FADE_SECONDS = ENDING_FADE_SECONDS
    SUBTITLE_CONFIG = SUBTITLE_CONFIG
    OPENING_QUOTE_STYLE = OPENING_QUOTE_STYLE
    MAX_CONCURRENT_IMAGE_GENERATION = MAX_CONCURRENT_IMAGE_GENERATION
    MAX_CONCURRENT_VOICE_SYNTHESIS = MAX_CONCURRENT_VOICE_SYNTHESIS
    VIDEO_MATERIAL_CONFIG = VIDEO_MATERIAL_CONFIG
    IMAGE_MATERIAL_CONFIG = IMAGE_MATERIAL_CONFIG
    
    # ==================== API 密钥配置 ====================
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    SEEDREAM_API_KEY = os.getenv('SEEDREAM_API_KEY')
    SILICONFLOW_KEY = os.getenv('SILICONFLOW_KEY')
    
    # 字节语音合成大模型配置
    BYTEDANCE_TTS_APPID = os.getenv('BYTEDANCE_TTS_APPID')
    BYTEDANCE_TTS_ACCESS_TOKEN = os.getenv('BYTEDANCE_TTS_ACCESS_TOKEN')
    BYTEDANCE_TTS_SECRET_KEY = os.getenv('BYTEDANCE_TTS_SECRET_KEY')
    
    # ==================== API 端点配置 ====================
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
    SILICONFLOW_IMAGE_BASE_URL = "https://api.siliconflow.cn/v1/images/generations"
    ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    
    # ==================== 默认模型配置 ====================
    DEFAULT_IMAGE_SIZE = "1664x928"  # 默认图像尺寸（与 Qwen-Image 固定尺寸一致）
    DEFAULT_VOICE = "zh_male_yuanboxiaoshu_moon_bigtts"  # 默认语音
    
    # ==================== 支持的服务商配置 ====================
    SUPPORTED_LLM_SERVERS = ["openrouter", "siliconflow"]
    SUPPORTED_IMAGE_SERVERS = ["doubao", "siliconflow"]
    SUPPORTED_TTS_SERVERS = ["bytedance"]

    SUPPORTED_IMAGE_METHODS = ["keywords", "description"]
    
    # ==================== 推荐模型列表 ====================
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
            ]
        },
        "image": {
            "doubao": [
                "doubao-seedream-4-0-250828",
                "doubao-seedream-3-0-t2i-250415",
            ],
            "siliconflow": ["Qwen/Qwen-Image"]
        },
        "tts": {
            "bytedance": ["bytedance-bigtts"]
        }
    }
    
    # ==================== 文件格式支持 ====================
    SUPPORTED_INPUT_FORMATS = [".epub", ".pdf", ".mobi", ".azw3", ".docx", ".doc"]

    # Qwen-Image 固定支持的尺寸（用于强校验）
    SUPPORTED_QWEN_IMAGE_SIZES = [
        "1328x1328",
        "1664x928",
        "928x1664",
        "1472x1140",
        "1140x1472",
        "1584x1056",
        "1056x1584",
    ]

    # Seedream V4 尺寸范围（包含端点）
    SEEDREAM_V4_MIN_SIZE = (1280, 720)
    SEEDREAM_V4_MAX_SIZE = (4096, 4096)
    # Seedream V3 尺寸范围（包含端点）
    SEEDREAM_V3_MIN_SIZE = (512, 512)
    SEEDREAM_V3_MAX_SIZE = (2048, 2048)
    
    # ==================== 输出路径配置 ====================
    DEFAULT_OUTPUT_DIR = "output"
    OUTPUT_STRUCTURE = {
        "images": "images",
        "voice": "voice", 
        "text": "text"
    }
    
    # ==================== 参数范围限制 ====================
    MIN_TARGET_LENGTH = 500
    MAX_TARGET_LENGTH = 3000
    MIN_NUM_SEGMENTS = 5
    MAX_NUM_SEGMENTS = 30
    
    # 内部计算参数
    SPEECH_SPEED_WPM = 250  # 中文语速估算 (每分钟字数)
    
    # ================================================================================
    # 系统配置验证方法（一般无需修改）
    # ================================================================================
    
    @staticmethod
    def _parse_image_size(size: str):
        try:
            w_str, h_str = size.lower().split("x", 1)
            return int(w_str), int(h_str)
        except Exception:
            raise ValueError(f"图像尺寸格式不正确: {size}，应为 'WxH'，例如 1664x928")

    @classmethod
    def _validate_seedream_v4_size(cls, size: str) -> None:
        w, h = cls._parse_image_size(size)
        min_w, min_h = cls.SEEDREAM_V4_MIN_SIZE
        max_w, max_h = cls.SEEDREAM_V4_MAX_SIZE
        if not (min_w <= w <= max_w and min_h <= h <= max_h):
            raise ValueError(
                f"Doubao Seedream V4 尺寸必须在[{min_w}x{min_h}, {max_w}x{max_h}]范围内（包含端点），当前: {size}"
            )

    @classmethod
    def _validate_seedream_v3_size(cls, size: str) -> None:
        w, h = cls._parse_image_size(size)
        min_w, min_h = cls.SEEDREAM_V3_MIN_SIZE
        max_w, max_h = cls.SEEDREAM_V3_MAX_SIZE
        if not (min_w <= w <= max_w and min_h <= h <= max_h):
            raise ValueError(
                f"Doubao Seedream V3 尺寸必须在[{min_w}x{min_h}, {max_w}x{max_h}]范围内（包含端点），当前: {size}"
            )

    @classmethod
    def validate_api_keys(cls) -> Dict[str, bool]:
        """验证API密钥配置"""
        return {
            "openrouter": bool(cls.OPENROUTER_API_KEY),
            "seedream": bool(cls.SEEDREAM_API_KEY), 
            "bytedance_tts": bool(cls.BYTEDANCE_TTS_APPID and cls.BYTEDANCE_TTS_ACCESS_TOKEN), 
            "siliconflow": bool(cls.SILICONFLOW_KEY),
        }

    @classmethod
    def get_required_keys_for_config(cls, llm_server: str, image_server: str, tts_server: str) -> list:
        """获取指定配置所需的API密钥"""
        required_keys = []

        if llm_server == "openrouter":
            required_keys.append("OPENROUTER_API_KEY")
        elif llm_server == "siliconflow":
            required_keys.append("SILICONFLOW_KEY")
            
        if image_server == "doubao":
            required_keys.append("SEEDREAM_API_KEY")
        elif image_server == "siliconflow":
            required_keys.append("SILICONFLOW_KEY")
            
        if tts_server == "bytedance":
            required_keys.append("BYTEDANCE_TTS_APPID")
            required_keys.append("BYTEDANCE_TTS_ACCESS_TOKEN")
            
        return list(set(required_keys))  # 去重
    
    
    @classmethod
    def validate_parameters(cls, target_length: int, num_segments: int, 
                          llm_server: str, image_server: str, tts_server: str, image_model: str,
                          image_size: str = None, images_method: str = None) -> None:
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
        
        if image_size:
            model_lower = (image_model or "").lower()
            if image_server == "doubao":
                if ("seedream-4" in model_lower or "doubao-seedream-4" in model_lower):
                    # Doubao Seedream V4: 范围校验（包含端点）
                    cls._validate_seedream_v4_size(image_size)
                else:
                    # Doubao Seedream V3: 范围校验（包含端点）
                    cls._validate_seedream_v3_size(image_size)
            elif image_server == "siliconflow" and (model_lower.startswith("qwen/") or "qwen-image" in model_lower):
                # Qwen-Image: 固定集合
                if image_size not in cls.SUPPORTED_QWEN_IMAGE_SIZES:
                    available_sizes = ", ".join(cls.SUPPORTED_QWEN_IMAGE_SIZES)
                    raise ValueError(f"Qwen-Image 不支持的图像尺寸: {image_size}，支持的尺寸: {available_sizes}")

        if images_method and images_method not in cls.SUPPORTED_IMAGE_METHODS:
            raise ValueError(
                f"不支持的生图模式: {images_method}，支持: {cls.SUPPORTED_IMAGE_METHODS}"
            )

# 创建配置实例
config = Config()

# 模块级快捷引用
SUPPORTED_LLM_SERVERS = Config.SUPPORTED_LLM_SERVERS
SUPPORTED_IMAGE_SERVERS = Config.SUPPORTED_IMAGE_SERVERS
SUPPORTED_TTS_SERVERS = Config.SUPPORTED_TTS_SERVERS
SUPPORTED_IMAGE_METHODS = Config.SUPPORTED_IMAGE_METHODS

# 导出常用配置
__all__ = [
    'Config', 'config',
    'DEFAULT_GENERATION_PARAMS',
    'get_default_generation_params',
    'SUPPORTED_LLM_SERVERS', 'SUPPORTED_IMAGE_SERVERS', 'SUPPORTED_TTS_SERVERS',
    'RECOMMENDED_MODELS', 'SUPPORTED_IMAGE_METHODS'
]
