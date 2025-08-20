"""
智能视频制作系统 - AI服务API模块
集成LLM、图像生成、语音合成等AI服务
"""

import os
import random
from openai import OpenAI

from config import config
from utils import logger, APIError, retry_on_failure


@retry_on_failure(max_retries=2, delay=2.0)
def text_to_text(server, model, prompt, system_message="", max_tokens=4000, temperature=0.5, output_format="text"):
    """
    统一的文本生成接口 - 使用OpenAI兼容接口
    
    Args:
        server: 服务商 ('openrouter', 'siliconflow', 'openai')
        model: 模型名称
        prompt: 用户提示词
        system_message: 系统提示词
        max_tokens: 最大输出长度
        temperature: 温度参数
        output_format: 输出格式
    """
    logger.info(f"调用{server}的{model}模型生成文本，提示词长度: {len(prompt)}字符")
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
    
    try:
        # 根据服务商获取对应的API配置
        if server == "openrouter":
            if not config.OPENROUTER_API_KEY:
                raise APIError("OPENROUTER_API_KEY未配置")
            api_key = config.OPENROUTER_API_KEY
            base_url = config.OPENROUTER_BASE_URL
            
        elif server == "siliconflow":
            if not config.SILICONFLOW_KEY:
                raise APIError("SILICONFLOW_KEY未配置")
            api_key = config.SILICONFLOW_KEY
            base_url = config.SILICONFLOW_BASE_URL
            
        elif server == "openai":
            if not config.AIHUBMIX_API_KEY:
                raise APIError("AIHUBMIX_API_KEY未配置")
            api_key = config.AIHUBMIX_API_KEY
            base_url = config.AIHUBMIX_URL
            
        else:
            raise ValueError(f"不支持的服务商: {server}，支持的服务商: {config.SUPPORTED_LLM_SERVERS}")
        
        # 统一使用OpenAI兼容接口调用
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        # 构建请求参数
        request_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "seed": random.randint(1, 1000000000)
        }
        
        # 如果是aihubmix代理，添加developer角色消息
        if server == "openai" and "aihubmix" in base_url.lower():
            messages = [
                {"role": "developer", "content": "Always reply in Chinese"},
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
            request_params["messages"] = messages
        
        response = client.chat.completions.create(**request_params)
        
        result = response.choices[0].message.content
        logger.info(f"{server} API调用成功，返回内容长度: {len(result)}字符")
        return result
    
    except Exception as e:
        logger.error(f"文本生成失败: {str(e)}")
        raise APIError(f"文本生成失败: {str(e)}")

# 注意：旧版本的图像生成和TTS函数已移除
# 现在支持的服务：
# - 图像生成：使用 text_to_image_doubao() 函数
# - 语音合成：使用 text_to_audio_doubao() 或 text_to_audio_bytedance() 函数

################ Doubao (ByteDance) API Functions ################
@retry_on_failure(max_retries=2, delay=2.0)
def text_to_image_doubao(prompt, size="1024x1024", model="doubao-seedream-3-0-t2i-250415"):
    """
    使用豆包Seedream 3.0生成图像
    
    Args:
        prompt: 图像生成提示词
        size: 图像尺寸 (如 "1024x1024")
        model: 模型名称
    
    Returns:
        str: 图像URL，失败时返回None
    """
    if not config.ARK_API_KEY:
        raise APIError("ARK_API_KEY未配置，无法使用豆包图像生成服务")
    
    logger.info(f"使用豆包Seedream 3.0生成图像，尺寸: {size}，提示词长度: {len(prompt)}字符")
    
    try:
        # 火山引擎方舟SDK调用
        from volcenginesdkarkruntime import Ark
        
        # 初始化客户端
        client = Ark(
            base_url=config.ARK_BASE_URL,
            api_key=config.ARK_API_KEY,
        )
        
        # 调用图像生成API
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            guidance_scale=7.5,
            watermark=False
        )
        
        if response and response.data:
            image_url = response.data[0].url
            logger.info(f"豆包图像生成成功，返回URL: {image_url[:50]}...")
            return image_url
        
        raise APIError("豆包图像生成API返回空响应")
        
    except ImportError:
        logger.error("未安装volcenginesdkarkruntime，请运行: pip install volcengine-python-sdk[ark]")
        raise APIError("缺少依赖包volcenginesdkarkruntime")
    except Exception as e:
        logger.error(f"豆包图像生成失败: {str(e)}")
        raise APIError(f"豆包图像生成失败: {str(e)}")

@retry_on_failure(max_retries=2, delay=1.0)
def text_to_audio_doubao(text, output_filename, voice="zh_female_qingxin"):
    """
    使用豆包TTS合成语音
    
    Args:
        text: 要合成的文本
        output_filename: 输出文件路径
        voice: 语音音色
    
    Returns:
        bool: 成功返回True，失败返回False
    """
    if not config.ARK_API_KEY:
        raise APIError("ARK_API_KEY未配置，无法使用豆包语音合成服务")
    
    logger.info(f"使用豆包TTS合成语音，音色: {voice}，文本长度: {len(text)}字符")
    
    try:
        # 火山引擎方舟SDK调用
        from volcenginesdkarkruntime import Ark
        
        # 初始化客户端
        client = Ark(
            base_url=config.ARK_BASE_URL,
            api_key=config.ARK_API_KEY,
        )
        
        # 调用语音合成API
        response = client.audio.speech.create(
            model="doubao-tts",
            input=text,
            voice=voice
        )
        
        if response and response.content:
            # 保存音频文件
            with open(output_filename, 'wb') as f:
                f.write(response.content)
            logger.info(f"豆包TTS合成成功，音频已保存: {output_filename}")
            return True
        
        raise APIError("豆包TTS API返回空响应")
        
    except ImportError:
        logger.error("未安装volcenginesdkarkruntime，请运行: pip install volcengine-python-sdk[ark]")
        raise APIError("缺少依赖包volcenginesdkarkruntime")
    except Exception as e:
        logger.error(f"豆包语音合成失败: {str(e)}")
        raise APIError(f"豆包语音合成失败: {str(e)}")

################ ByteDance TTS BigModel API Functions ################
@retry_on_failure(max_retries=2, delay=1.0)
def text_to_audio_bytedance(text, output_filename, voice="zh_male_yuanboxiaoshu_moon_bigtts"):
    """
    使用字节语音合成大模型合成语音
    
    Args:
        text: 要合成的文本
        output_filename: 输出文件路径
        voice: 语音音色
    
    Returns:
        bool: 成功返回True，失败返回False
    """
    if not all([config.BYTEDANCE_TTS_APPID, config.BYTEDANCE_TTS_ACCESS_TOKEN, config.BYTEDANCE_TTS_SECRET_KEY]):
        raise APIError("字节语音合成大模型配置不完整，请检查BYTEDANCE_TTS相关配置")
    
    logger.info(f"使用字节语音合成大模型，音色: {voice}，文本长度: {len(text)}字符")
    
    try:
        import requests
        import json
        import base64
        
        # 字节语音合成大模型API端点
        url = "https://openspeech.bytedance.com/api/v1/tts"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer;{config.BYTEDANCE_TTS_ACCESS_TOKEN}"
        }
        
        # 生成唯一的reqid
        import uuid
        reqid = str(uuid.uuid4())
        
        payload = {
            "app": {
                "appid": config.BYTEDANCE_TTS_APPID,
                "token": config.BYTEDANCE_TTS_ACCESS_TOKEN,
                "cluster": "volcano_tts"
            },
            "user": {
                "uid": "aigc_video_user"
            },
            "audio": {
                "voice_type": voice,
                "encoding": "mp3",
                "speed_ratio": 1.0
            },
            "request": {
                "reqid": reqid,
                "text": text,
                "operation": "query"
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("code") == 3000:
            # 成功获取音频数据 (根据实际响应格式调整)
            audio_data = result.get("data")
            if audio_data:
                # 解码base64音频数据
                audio_bytes = base64.b64decode(audio_data)
                
                # 保存音频文件
                with open(output_filename, 'wb') as f:
                    f.write(audio_bytes)
                    
                # 获取音频时长信息
                duration = result.get("addition", {}).get("duration", "未知")
                logger.info(f"字节语音合成成功，音频已保存: {output_filename}，时长: {duration}ms")
                return True
            else:
                raise APIError("字节语音合成返回的音频数据为空")
        else:
            error_msg = result.get("message", "未知错误")
            error_code = result.get("code", "未知")
            raise APIError(f"字节语音合成API错误 (code: {error_code}): {error_msg}")
            
    except ImportError:
        logger.error("缺少requests依赖包，请运行: pip install requests")
        raise APIError("缺少依赖包requests")
    except Exception as e:
        logger.error(f"字节语音合成大模型失败: {str(e)}")
        raise APIError(f"字节语音合成大模型失败: {str(e)}")