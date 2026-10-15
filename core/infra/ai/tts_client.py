"""TTS orchestration: API request + local post-processing + file output."""

import os
import json
import base64
import struct

import requests

from core.config import config
from core.shared import logger, APIError, retry_on_failure, ensure_directory_exists


def remove_silence_from_pcm(
    pcm_data: bytes,
    sample_rate: int = 48000,
    threshold: int = 400,
    min_silence_ms: int = 200,
    remain_ms: int = 100,
) -> bytes:
    """
    从PCM音频中移除过长的静音段（内存处理）

    规则：
    1. 只切除连续静音 > min_silence_ms 的段落
    2. 在真正的静音段前后各保留 remain_ms
    3. 短暂的弱音不会被切除
    """
    if not pcm_data or threshold <= 0:
        return pcm_data

    try:
        import numpy as np

        # 转为int16数组并计算音量
        audio = np.frombuffer(pcm_data, dtype=np.int16)
        volume = np.abs(audio)

        # 滑动窗口平滑（避免误切单个采样点）
        window = max(1, sample_rate // 100)  # 10ms窗口
        smoothed = np.convolve(volume, np.ones(window) / window, mode="same")

        # 标记静音点
        is_silence = smoothed <= threshold

        # 检测所有静音段的起止位置
        silence_bounds = np.diff(np.concatenate([[0], is_silence.astype(int), [0]]))
        silence_starts = np.where(silence_bounds == 1)[0]
        silence_ends = np.where(silence_bounds == -1)[0]

        if len(silence_starts) == 0:
            return pcm_data

        # 只处理长静音段
        min_silence_samples = int(sample_rate * min_silence_ms / 1000)
        remain_samples = int(sample_rate * remain_ms / 1000)

        # 构建保留区域（默认全部保留）
        keep_ranges = []
        last_end = 0

        for sil_start, sil_end in zip(silence_starts, silence_ends):
            silence_len = sil_end - sil_start

            if silence_len > min_silence_samples:
                # 长静音：保留语音段 + 静音前后各remain_ms
                keep_ranges.append((last_end, sil_start + remain_samples))
                last_end = sil_end - remain_samples
            # 短静音：不切除，自然包含在keep_ranges中

        # 添加最后一段到结尾
        keep_ranges.append((last_end, len(audio)))

        # 拼接所有保留段
        segments = [audio[start:end] for start, end in keep_ranges if end > start]
        if not segments:
            return pcm_data

        return np.concatenate(segments).tobytes()
    except Exception as e:
        logger.warning(f"静音切除失败: {e}")
        return pcm_data


def _create_wav_header(pcm_data_size, sample_rate=48000, channels=1, bits_per_sample=16):
    """创建 WAV 文件头（44 字节）"""
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8

    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + pcm_data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        pcm_data_size,
    )


def _request_bytedance_tts_pcm(
    *,
    api_key: str,
    resource_id: str,
    text: str,
    voice: str,
    model: str,
    speech_rate: int,
    loudness_rate: int,
    emotion: str,
    emotion_scale: int,
) -> bytes:
    """调用火山引擎TTS API并返回PCM音频数据。"""
    url = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
    headers = {
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": resource_id,
        "Content-Type": "application/json",
    }
    payload = {
        "user": {"uid": "aigc_video_user"},
        "req_params": {
            "text": text,
            "speaker": voice,
            "audio_params": {
                "format": "pcm",
                "sample_rate": 48000,
                "emotion": emotion,
                "emotion_scale": emotion_scale,
                "speech_rate": speech_rate,
                "loudness_rate": loudness_rate,
            },
            "additions": json.dumps({"silence_duration": 0}),
        },
    }
    if model:
        payload["req_params"]["model"] = model

    session = requests.Session()
    response = None
    try:
        response = session.post(url, headers=headers, json=payload, stream=True, timeout=30)
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"TTS API请求失败 - 状态码: {response.status_code}, 错误: {error_text}")
            raise APIError(f"TTS API请求失败（{response.status_code}）: {error_text}",
                           retryable=response.status_code in (408, 429) or response.status_code >= 500)

        logid = response.headers.get("X-Tt-Logid", "N/A")
        logger.debug(f"TTS 请求成功 - X-Tt-Logid: {logid}")

        audio_data = bytearray()
        for chunk in response.iter_lines(decode_unicode=True):
            if not chunk:
                continue
            try:
                data = json.loads(chunk)
            except json.JSONDecodeError:
                logger.warning(f"无法解析响应数据: {chunk[:100]}")
                continue

            if data.get("code", 0) == 0 and "data" in data and data["data"]:
                audio_data.extend(base64.b64decode(data["data"]))
                continue
            if data.get("code", 0) == 20000000:
                break
            if data.get("code", 0) > 0:
                error_msg = data.get("message", "未知错误")
                logger.error(f"TTS API返回错误: code={data.get('code')}, message={error_msg}")
                raise APIError(f"TTS API错误: {error_msg}")

        if not audio_data:
            raise APIError("未接收到音频数据")
        return bytes(audio_data)
    finally:
        if response is not None:
            response.close()
        session.close()


def resource_for_voice(voice: str, configured: str) -> str:
    """音色所属的资源 ID。音色与资源不匹配时火山会拒绝（code=55000000），因此按音色类型选择。"""
    voice, configured = (voice or "").strip(), (configured or "").strip()
    if voice.startswith("S_"):  # 声音复刻音色
        return configured if configured.startswith("seed-icl") else "seed-icl-2.0"
    if "_uranus_" in voice or voice.startswith("saturn_"):  # 语音合成 2.0 音色
        return "seed-tts-2.0"
    if voice.endswith(("_moon_bigtts", "_mars_bigtts")):  # 语音合成 1.0 音色
        return "seed-tts-1.0"
    return configured


@retry_on_failure(max_retries=1, delay=1.0)
def text_to_audio_bytedance(
    text,
    output_filename,
    voice="zh_male_yuanboxiaoshu_moon_bigtts",
    model: str = "",
    speech_rate: int = 0,
    loudness_rate: int = 0,
    emotion: str = "neutral",
    emotion_scale: int = 4,
    mute_cut_threshold: int = 400,
    mute_cut_min_silence_ms: int = 200,
    mute_cut_remain_ms: int = 100,
):
    """
    使用火山引擎TTS API进行语音合成（HTTP 单向流式接口）

    Args:
        text: 要合成的文本
        output_filename: 输出文件路径（.wav格式）
        voice: 音色ID
        model: 复刻2.0效果模型（如 seed-tts-2.0-expressive / seed-tts-2.0-standard）
        speech_rate: 语速 (-50到100, 0=正常, 100=2倍速, -50=0.5倍速)
        loudness_rate: 音量 (-50到100, 0=正常, 100=2倍音量, -50=0.5倍音量)
        emotion: 情感类型 (neutral, happy, sad等)
        emotion_scale: 情感强度 (1-5)
        mute_cut_remain_ms: 静音切除后保留的静音时长 (毫秒, 默认400)
        mute_cut_threshold: 静音切除阈值 (默认100)

    Returns:
        bool: 成功返回True
    """
    # ============ 1. 验证配置 ============
    api_key = (getattr(config, "BYTEDANCE_TTS_API_KEY", "") or "").strip()
    if not api_key:
        raise APIError("豆包语音配置不完整，请检查 BYTEDANCE_TTS_API_KEY", retryable=False)

    voice = (voice or "").strip()
    if not voice:
        raise APIError("未设置配音音色，请在设置中填写音色 ID", retryable=False)
    RESOURCE_ID = resource_for_voice(voice, config.RESOURCE_ID)
    if RESOURCE_ID != config.RESOURCE_ID:
        logger.info(f"音色 {voice} 属于资源 {RESOURCE_ID}，已替换配置的 {config.RESOURCE_ID}")
    MODEL = str(model or getattr(config, "TTS_MODEL", "") or "").strip()

    # ============ 2. 参数验证和规范化 ============
    speech_rate = max(-50, min(100, int(speech_rate or 0)))
    loudness_rate = max(-50, min(100, int(loudness_rate or 0)))
    emotion = str(emotion or "neutral")
    emotion_scale = max(1, min(5, int(emotion_scale or 4)))

    logger.info(
        f"调用火山引擎TTS API - 资源: {RESOURCE_ID}, 音色: {voice}, "
        f"模型: {MODEL or '<default>'}, 文本长度: {len(text)}字符, 语速: {speech_rate}, 音量: {loudness_rate}, "
        f"情感: {emotion}({emotion_scale})"
    )

    try:
        # ============ 3. 请求TTS API，获取PCM ============
        audio_data = _request_bytedance_tts_pcm(
            api_key=api_key,
            resource_id=RESOURCE_ID,
            text=text,
            voice=voice,
            model=MODEL,
            speech_rate=speech_rate,
            loudness_rate=loudness_rate,
            emotion=emotion,
            emotion_scale=emotion_scale,
        )

        # ============ 4. 本地静音切除 ============
        original_size = len(audio_data)
        if mute_cut_threshold > 0:
            audio_data = remove_silence_from_pcm(
                pcm_data=audio_data,
                sample_rate=48000,
                threshold=mute_cut_threshold,
                min_silence_ms=mute_cut_min_silence_ms,
                remain_ms=mute_cut_remain_ms,
            )
            reduction = (1 - len(audio_data) / original_size) * 100 if original_size > 0 else 0
            logger.info(
                f"静音切除: {original_size/1024:.1f}KB → {len(audio_data)/1024:.1f}KB (-{reduction:.1f}%)"
            )

        # ============ 5. 保存音频文件 ============
        ensure_directory_exists(os.path.dirname(output_filename))

        # 添加 WAV header 并保存为 WAV 文件
        wav_header = _create_wav_header(len(audio_data), sample_rate=48000)
        with open(output_filename, "wb") as f:
            f.write(wav_header)
            f.write(audio_data)

        logger.info(f"语音合成成功 - 文件: {(len(audio_data) + 44)/1024:.1f} KB, 已保存: {output_filename}")

        return True

    except APIError:
        raise
    except Exception as e:
        logger.error(f"语音合成失败: {str(e)}")
        raise APIError(f"语音合成失败: {str(e)}") from e


__all__ = ["resource_for_voice", "text_to_audio_bytedance"]
