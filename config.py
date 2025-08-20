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
    ARK_API_KEY = os.getenv('ARK_API_KEY')
    SILICONFLOW_KEY = os.getenv('SILICONFLOW_KEY')
    AIHUBMIX_API_KEY = os.getenv('AIHUBMIX_API_KEY')
    AIHUBMIX_URL = "https://aihubmix.com/v1"
    
    # 字节语音合成大模型配置
    BYTEDANCE_TTS_APPID = os.getenv('BYTEDANCE_TTS_APPID')
    BYTEDANCE_TTS_ACCESS_TOKEN = os.getenv('BYTEDANCE_TTS_ACCESS_TOKEN')
    BYTEDANCE_TTS_SECRET_KEY = os.getenv('BYTEDANCE_TTS_SECRET_KEY')
    
    # API 端点配置
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
    ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    
    # 默认参数配置
    DEFAULT_TARGET_LENGTH = 800  # 默认目标字数
    DEFAULT_NUM_SEGMENTS = 10    # 默认分段数
    DEFAULT_IMAGE_SIZE = "1024x1024"  # 默认图像尺寸
    DEFAULT_VOICE = "zh_male_yuanboxiaoshu_moon_bigtts"  # 默认语音（字节语音合成大模型）
    
    # 支持的服务商和模型
    SUPPORTED_LLM_SERVERS = ["openrouter", "siliconflow", "openai"]  # 都使用OpenAI兼容接口
    SUPPORTED_IMAGE_SERVERS = ["doubao"]  # 只支持火山引擎豆包
    SUPPORTED_TTS_SERVERS = ["doubao"]    # 只支持豆包TTS（字节语音合成大模型）
    
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
            "openai": ["gpt-4o", "gpt-4-turbo"]
        },
        "image": {
            "doubao": ["doubao-seedream-3-0-t2i-250415"]
        },
        "tts": {
            "doubao": ["doubao-tts", "bytedance-bigtts"]  # 豆包TTS（字节语音合成大模型）
        }
    }
    
    # 语音配置 - 豆包TTS（字节语音合成大模型）
    AVAILABLE_VOICES = {
        "doubao": [
            # 方舟豆包TTS音色
            "zh_female_qingxin",  # 清新女声
            "zh_male_qingxin",    # 清新男声
            "zh_female_wenwen",   # 温温女声
            "zh_male_sunshine",   # 阳光男声
            # 字节语音合成大模型音色（豆包TTS的另一套接口）
            "zh_male_yuanboxiaoshu_moon_bigtts",  # 元博小叔月亮音色
            "zh_female_standard_bigtts",  # 标准女声
            "zh_male_standard_bigtts"     # 标准男声
        ]
    }
    
    # 文件格式支持
    SUPPORTED_INPUT_FORMATS = [".epub", ".pdf"]
    SUPPORTED_IMAGE_SIZES = ["512x512", "1024x1024", "1024x576", "1024x768"]
    
    # 输出路径配置
    DEFAULT_OUTPUT_DIR = "output"
    OUTPUT_STRUCTURE = {
        "images": "images",
        "voice": "voice", 
        "text": "text"
    }
    
    # 处理限制
    MIN_TARGET_LENGTH = 500
    MAX_TARGET_LENGTH = 1000
    MIN_NUM_SEGMENTS = 5
    MAX_NUM_SEGMENTS = 20
    
    # 语音时长估算 (每分钟字数)
    SPEECH_SPEED_WPM = 300  # 中文普通话正常语速
    
    @classmethod
    def validate_api_keys(cls) -> Dict[str, bool]:
        """验证API密钥配置"""
        return {
            "openrouter": bool(cls.OPENROUTER_API_KEY),
            "ark": bool(cls.ARK_API_KEY),  # 用于豆包图像和TTS
            "siliconflow": bool(cls.SILICONFLOW_KEY),
            "aihubmix": bool(cls.AIHUBMIX_API_KEY)
        }
    
    @classmethod
    def get_required_keys_for_config(cls, llm_server: str, image_server: str, tts_server: str) -> list:
        """获取指定配置所需的API密钥"""
        required_keys = []
        
        if llm_server == "openrouter":
            required_keys.append("OPENROUTER_API_KEY")
        elif llm_server == "openai":
            required_keys.append("AIHUBMIX_API_KEY")
        elif llm_server == "siliconflow":
            required_keys.append("SILICONFLOW_KEY")
            
        if image_server == "doubao":
            required_keys.append("ARK_API_KEY")
            
        if tts_server == "doubao":
            required_keys.append("ARK_API_KEY")
            
        return list(set(required_keys))  # 去重
    
    @classmethod
    def validate_parameters(cls, target_length: int, num_segments: int, 
                          llm_server: str, image_server: str, tts_server: str) -> None:
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

# 创建配置实例
config = Config()

# 导出常用配置
__all__ = [
    'Config', 'config',
    'SUPPORTED_LLM_SERVERS', 'SUPPORTED_IMAGE_SERVERS', 'SUPPORTED_TTS_SERVERS',
    'RECOMMENDED_MODELS', 'AVAILABLE_VOICES'
]