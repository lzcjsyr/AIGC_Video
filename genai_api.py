"""
智能视频制作系统 - AI服务API模块
集成LLM、图像生成、语音合成等AI服务
"""

import os
import random
import asyncio
import json
import uuid
import websockets
import io
import struct
from dataclasses import dataclass
from enum import IntEnum
from openai import OpenAI

from config import config
from utils import logger, APIError, retry_on_failure


# ================================================================================
# 🤖 LLM 文本生成 API
# ================================================================================
# 支持多个服务商：OpenRouter、SiliconFlow、aihubmix代理
# 统一使用OpenAI兼容接口调用
# ================================================================================

@retry_on_failure(max_retries=2, delay=2.0)
def text_to_text(server, model, prompt, system_message="", max_tokens=4000, temperature=0.5, output_format="text"):
    """
    统一的文本生成接口 - 使用OpenAI兼容接口
    
    Args:
        server: 服务商 ('openrouter', 'siliconflow', 'aihubmix')
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
            
        elif server == "aihubmix":
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
        
        # 如果是aihubmix代理
        if server == "aihubmix" and "aihubmix" in base_url.lower():
            messages = [
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

# ================================================================================
# 🎨 图像生成 API - 豆包 Seedream 3.0
# ================================================================================
# 使用火山引擎方舟服务，支持高质量图像生成
# 模型：doubao-seedream-3-0-t2i-250415
# ================================================================================
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
    if not config.SEEDREAM_API_KEY:
        raise APIError("SEEDREAM_API_KEY未配置，无法使用豆包图像生成服务")
    
    logger.info(f"使用豆包Seedream 3.0生成图像，尺寸: {size}，提示词长度: {len(prompt)}字符")
    
    try:
        # 火山引擎方舟SDK调用
        from volcenginesdkarkruntime import Ark
        
        # 初始化客户端
        client = Ark(
            base_url=config.ARK_BASE_URL,
            api_key=config.SEEDREAM_API_KEY,
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


# ================================================================================
# 🔊 语音合成 API - 字节语音大模型 (WebSocket)
# ================================================================================
# 使用字节跳动语音合成大模型WebSocket协议
# 支持高质量语音合成和多种音色
# ================================================================================

# WebSocket 协议相关定义
class MsgType(IntEnum):
    Invalid = 0
    FullClientRequest = 0b1
    AudioOnlyClient = 0b10
    FullServerResponse = 0b1001
    AudioOnlyServer = 0b1011
    FrontEndResultServer = 0b1100
    Error = 0b1111

class MsgTypeFlagBits(IntEnum):
    NoSeq = 0
    PositiveSeq = 0b1
    LastNoSeq = 0b10
    NegativeSeq = 0b11
    WithEvent = 0b100

class VersionBits(IntEnum):
    Version1 = 1

class HeaderSizeBits(IntEnum):
    HeaderSize4 = 1

class SerializationBits(IntEnum):
    Raw = 0
    JSON = 0b1

class CompressionBits(IntEnum):
    None_ = 0

@dataclass
class Message:
    version: VersionBits = VersionBits.Version1
    header_size: HeaderSizeBits = HeaderSizeBits.HeaderSize4
    type: MsgType = MsgType.Invalid
    flag: MsgTypeFlagBits = MsgTypeFlagBits.NoSeq
    serialization: SerializationBits = SerializationBits.JSON
    compression: CompressionBits = CompressionBits.None_
    sequence: int = 0
    payload: bytes = b""
    
    def marshal(self) -> bytes:
        buffer = io.BytesIO()
        header = [
            (self.version << 4) | self.header_size,
            (self.type << 4) | self.flag,
            (self.serialization << 4) | self.compression,
            0  # padding
        ]
        buffer.write(bytes(header))
        
        if self.flag in [MsgTypeFlagBits.PositiveSeq, MsgTypeFlagBits.NegativeSeq]:
            buffer.write(struct.pack(">i", self.sequence))
        
        size = len(self.payload)
        buffer.write(struct.pack(">I", size))
        buffer.write(self.payload)
        return buffer.getvalue()
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        if len(data) < 3:
            raise ValueError(f"Data too short: expected at least 3 bytes, got {len(data)}")
        
        type_and_flag = data[1]
        msg_type = MsgType(type_and_flag >> 4)
        flag = MsgTypeFlagBits(type_and_flag & 0b00001111)
        
        msg = cls(type=msg_type, flag=flag)
        
        # 简化的解析逻辑
        buffer = io.BytesIO(data)
        buffer.read(4)  # skip header
        
        if flag in [MsgTypeFlagBits.PositiveSeq, MsgTypeFlagBits.NegativeSeq]:
            seq_bytes = buffer.read(4)
            if seq_bytes:
                msg.sequence = struct.unpack(">i", seq_bytes)[0]
        
        size_bytes = buffer.read(4)
        if size_bytes:
            size = struct.unpack(">I", size_bytes)[0]
            if size > 0:
                msg.payload = buffer.read(size)
        
        return msg

async def _send_full_request(websocket, payload: bytes):
    """发送完整请求"""
    msg = Message(type=MsgType.FullClientRequest, flag=MsgTypeFlagBits.NoSeq)
    msg.payload = payload
    await websocket.send(msg.marshal())

async def _receive_message(websocket) -> Message:
    """接收消息"""
    data = await websocket.recv()
    if isinstance(data, bytes):
        return Message.from_bytes(data)
    else:
        raise ValueError(f"Unexpected message type: {type(data)}")

def _get_cluster(voice: str) -> str:
    """根据音色确定集群"""
    if voice.startswith("S_"):
        return "volcano_icl"
    return "volcano_tts"

@retry_on_failure(max_retries=2, delay=1.0)
def text_to_audio_bytedance(text, output_filename, voice="zh_male_yuanboxiaoshu_moon_bigtts", encoding="wav"):
    """
    使用字节语音合成大模型WebSocket协议合成语音
    
    Args:
        text: 要合成的文本
        output_filename: 输出文件路径
        voice: 语音音色
        encoding: 音频编码格式 (wav/mp3)
    
    Returns:
        bool: 成功返回True，失败返回False
    """
    # 从环境变量读取配置
    if not config.BYTEDANCE_TTS_APPID or not config.BYTEDANCE_TTS_ACCESS_TOKEN:
        raise APIError("字节语音合成大模型配置不完整，请检查BYTEDANCE_TTS_APPID和BYTEDANCE_TTS_ACCESS_TOKEN")
    
    APPID = config.BYTEDANCE_TTS_APPID
    ACCESS_TOKEN = config.BYTEDANCE_TTS_ACCESS_TOKEN
    
    logger.info(f"使用字节语音合成大模型WebSocket，音色: {voice}，文本长度: {len(text)}字符")
    
    try:
        # 运行异步函数
        return asyncio.run(_async_text_to_audio(text, output_filename, voice, encoding, APPID, ACCESS_TOKEN))
    except Exception as e:
        logger.error(f"字节语音合成失败: {str(e)}")
        raise APIError(f"字节语音合成失败: {str(e)}")

async def _async_text_to_audio(text, output_filename, voice, encoding, appid, access_token):
    """异步语音合成实现"""
    endpoint = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"
    cluster = _get_cluster(voice)
    
    # WebSocket连接头
    headers = {
        "Authorization": f"Bearer;{access_token}",
    }
    
    logger.info(f"连接到 {endpoint}")
    
    try:
        websocket = await websockets.connect(
            endpoint, 
            additional_headers=headers, 
            max_size=10 * 1024 * 1024
        )
        
        # websockets client exposes response headers via `response_headers`
        logid = getattr(websocket, "response_headers", {}).get('x-tt-logid', 'unknown')
        logger.info(f"WebSocket连接成功，Logid: {logid}")
        
        # 准备请求数据
        request_data = {
            "app": {
                "appid": appid,
                "token": access_token,
                "cluster": cluster,
            },
            "user": {
                "uid": str(uuid.uuid4()),
            },
            "audio": {
                "voice_type": voice,
                "encoding": encoding,
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "operation": "submit",
                "with_timestamp": "1",
                "extra_param": json.dumps({
                    "disable_markdown_filter": False,
                }),
            },
        }
        
        # 发送请求
        await _send_full_request(websocket, json.dumps(request_data).encode())
        
        # 接收音频数据
        audio_data = bytearray()
        while True:
            msg = await _receive_message(websocket)
            
            if msg.type == MsgType.FrontEndResultServer:
                continue
            elif msg.type == MsgType.AudioOnlyServer:
                audio_data.extend(msg.payload)
                if msg.sequence < 0:  # 最后一个消息
                    break
            elif msg.type == MsgType.Error:
                error_msg = msg.payload.decode('utf-8', 'ignore')
                raise APIError(f"TTS转换失败: {error_msg}")
            else:
                logger.warning(f"收到未预期的消息类型: {msg.type}")
        
        # 检查是否收到音频数据
        if not audio_data:
            raise APIError("未收到音频数据")
        
        # 保存音频文件
        with open(output_filename, "wb") as f:
            f.write(audio_data)
        
        logger.info(f"语音合成成功，音频大小: {len(audio_data)} bytes，已保存: {output_filename}")
        return True
        
    except Exception as e:
        logger.error(f"WebSocket语音合成失败: {str(e)}")
        raise
    finally:
        if 'websocket' in locals():
            await websocket.close()
            logger.info("WebSocket连接已关闭")