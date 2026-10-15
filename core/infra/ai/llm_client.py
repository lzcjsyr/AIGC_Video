"""
Core services: unified entry points for model calls (migrated from genai_api).
"""

from typing import Dict, Optional, Tuple
import os
import random
from openai import OpenAI

from core.config import config
from core.shared import logger, APIError, http_status, retry_on_failure

def _get_openai_api_key(server: str) -> str:
    server = (server or "").strip().lower()
    if server == "openrouter":
        if not config.OPENROUTER_API_KEY:
            raise APIError("OPENROUTER_API_KEY未配置", retryable=False)
        return config.OPENROUTER_API_KEY
    elif server == "siliconflow":
        if not config.SILICONFLOW_KEY:
            raise APIError("SILICONFLOW_KEY未配置", retryable=False)
        return config.SILICONFLOW_KEY
    elif server == "mimo":
        if not config.MIMO_API_KEY:
            raise APIError("MIMO_API_KEY未配置", retryable=False)
        return config.MIMO_API_KEY
    elif server == "kimi":
        if not config.KIMI_API_KEY:
            raise APIError("KIMI_API_KEY 或 MOONSHOT_API_KEY 未配置", retryable=False)
        return config.KIMI_API_KEY
    elif server == "deepseek":
        if not config.DEEPSEEK_API_KEY:
            raise APIError("DEEPSEEK_API_KEY未配置", retryable=False)
        return config.DEEPSEEK_API_KEY
    elif server == "volcengine":
        if not config.VOLCENGINE_API_KEY:
            raise APIError("VOLCENGINE_API_KEY未配置", retryable=False)
        return config.VOLCENGINE_API_KEY
    else:
        raise ValueError(f"不支持的服务商: {server}，支持的服务商: {config.SUPPORTED_LLM_SERVERS}")


@retry_on_failure(max_retries=1, delay=2.0)
def text_to_text(
    server,
    model,
    prompt,
    system_message="",
    max_tokens=4000,
    temperature=0.5,
    base_url="",
):
    logger.info(f"调用{server}的{model}模型生成文本，提示词长度: {len(prompt)}字符")
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
    try:
        api_key = _get_openai_api_key(server)
        if not base_url:
            base_url = config.LLM_SERVER_URLS.get(server.strip().lower(), "")
        if not base_url:
            raise APIError("LLM base URL未配置", retryable=False)

        client = OpenAI(api_key=api_key, base_url=base_url)
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

        response = client.chat.completions.create(**request_params)
        result = response.choices[0].message.content
        logger.info(f"{server} API调用成功，返回内容长度: {len(result)}字符")
        return result
    except Exception as e:
        logger.error(f"文本生成失败: {str(e)}")
        raise APIError(f"文本生成失败: {str(e)}") from e


@retry_on_failure(max_retries=1, delay=2.0)
def text_to_image_doubao(prompt, size="1024x1024", model="doubao-seedream-3-0-t2i-250415"):
    if not config.VOLCENGINE_API_KEY:
        raise APIError("VOLCENGINE_API_KEY未配置，无法使用豆包图像生成服务", retryable=False)
    logger.info(f"使用豆包Seedream生成图像，模型: {model}，尺寸: {size}，提示词长度: {len(prompt)}字符")
    try:
        from volcenginesdkarkruntime import Ark
        client = Ark(
            base_url=config.ARK_BASE_URL,
            api_key=config.VOLCENGINE_API_KEY,
        )

        # Seedream 4/5 使用新版图片生成参数；旧版 V3 仍保留 guidance_scale。
        lower_model = model.lower()
        is_new_seedream_model = "seedream-4" in lower_model or "seedream-5" in lower_model

        if is_new_seedream_model:
            response = client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                response_format="url",
                watermark=False
            )
        else:
            # V3模型：保持原有参数
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
        raise APIError("缺少依赖包volcenginesdkarkruntime", retryable=False)
    except Exception as e:
        logger.error(f"豆包图像生成失败: {str(e)}")
        raise APIError(f"豆包图像生成失败: {str(e)}") from e


_GOOGLE_IMAGE_SIZE_TABLE_PRO: Dict[str, Dict[str, Tuple[int, int]]] = {
    "1:1": {"1K": (1024, 1024), "2K": (2048, 2048), "4K": (4096, 4096)},
    "4:3": {"1K": (1280, 960), "2K": (2560, 1920), "4K": (5120, 3840)},
    "3:4": {"1K": (960, 1280), "2K": (1920, 2560), "4K": (3840, 5120)},
    "16:9": {"1K": (1376, 768), "2K": (2752, 1536), "4K": (5504, 3072)},
    "9:16": {"1K": (768, 1376), "2K": (1536, 2752), "4K": (3072, 5504)},
    "3:2": {"1K": (1152, 768), "2K": (2304, 1536), "4K": (4608, 3072)},
    "2:3": {"1K": (768, 1152), "2K": (1536, 2304), "4K": (3072, 4608)},
    "5:4": {"1K": (1280, 1024), "2K": (2560, 2048), "4K": (5120, 4096)},
    "4:5": {"1K": (1024, 1280), "2K": (2048, 2560), "4K": (4096, 5120)},
    "21:9": {"1K": (1792, 768), "2K": (3584, 1536), "4K": (7168, 3072)},
    "9:21": {"1K": (768, 1792), "2K": (1536, 3584), "4K": (3072, 7168)},
}


_GOOGLE_IMAGE_SIZE_TABLE_FLASH: Dict[str, Dict[str, Tuple[int, int]]] = {
    **_GOOGLE_IMAGE_SIZE_TABLE_PRO,
    "1:1": {"0.5K": (512, 512), "1K": (1024, 1024), "2K": (2048, 2048), "4K": (4096, 4096)},
    "4:3": {"0.5K": (640, 480), "1K": (1280, 960), "2K": (2560, 1920), "4K": (5120, 3840)},
    "3:4": {"0.5K": (480, 640), "1K": (960, 1280), "2K": (1920, 2560), "4K": (3840, 5120)},
    "16:9": {"0.5K": (688, 384), "1K": (1376, 768), "2K": (2752, 1536), "4K": (5504, 3072)},
    "9:16": {"0.5K": (384, 688), "1K": (768, 1376), "2K": (1536, 2752), "4K": (3072, 5504)},
    "3:2": {"0.5K": (576, 384), "1K": (1152, 768), "2K": (2304, 1536), "4K": (4608, 3072)},
    "2:3": {"0.5K": (384, 576), "1K": (768, 1152), "2K": (1536, 2304), "4K": (3072, 4608)},
    "5:4": {"0.5K": (640, 512), "1K": (1280, 1024), "2K": (2560, 2048), "4K": (5120, 4096)},
    "4:5": {"0.5K": (512, 640), "1K": (1024, 1280), "2K": (2048, 2560), "4K": (4096, 5120)},
    "21:9": {"0.5K": (896, 384), "1K": (1792, 768), "2K": (3584, 1536), "4K": (7168, 3072)},
    "9:21": {"0.5K": (384, 896), "1K": (768, 1792), "2K": (1536, 3584), "4K": (3072, 7168)},
    "1:4": {"0.5K": (256, 1024), "1K": (512, 2048), "2K": (1024, 4096), "4K": (2048, 8192)},
    "1:8": {"0.5K": (128, 1024), "1K": (256, 2048), "2K": (512, 4096), "4K": (1024, 8192)},
    "4:1": {"0.5K": (1024, 256), "1K": (2048, 512), "2K": (4096, 1024), "4K": (8192, 2048)},
    "8:1": {"0.5K": (1024, 128), "1K": (2048, 256), "2K": (4096, 512), "4K": (8192, 1024)},
}


def _parse_wxh_size(size: str) -> Optional[Tuple[int, int]]:
    size_text = str(size or "").strip().lower()
    for separator in ("×", "✕", "✖", "*"):
        size_text = size_text.replace(separator, "x")
    size_text = size_text.replace(" ", "")
    if "x" not in size_text:
        return None
    try:
        w_text, h_text = size_text.split("x", 1)
        width, height = int(w_text), int(h_text)
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _map_custom_size_to_google(size: str, model: str) -> Tuple[str, str, Tuple[int, int]]:
    """将 WxH 自定义尺寸映射到 Google image_config 所支持的 aspect_ratio + image_size。"""
    parsed = _parse_wxh_size(size)
    if not parsed:
        return "1:1", "1K", (1024, 1024)

    width, height = parsed
    lower_model = str(model or "").lower()
    table = _GOOGLE_IMAGE_SIZE_TABLE_PRO if "pro-image" in lower_model else _GOOGLE_IMAGE_SIZE_TABLE_FLASH

    best_ratio = "1:1"
    best_size = "1K"
    best_dims = (1024, 1024)
    best_score = float("inf")
    target_ratio = width / height

    for ratio, size_map in table.items():
        rw_text, rh_text = ratio.split(":", 1)
        ratio_value = int(rw_text) / int(rh_text)
        ratio_error = abs((target_ratio / ratio_value) - 1.0)
        for size_tag, dims in size_map.items():
            dw, dh = dims
            size_error = abs(width - dw) + abs(height - dh)
            score = ratio_error * 10000 + size_error
            if score < best_score:
                best_score = score
                best_ratio = ratio
                best_size = size_tag
                best_dims = dims

    return best_ratio, best_size, best_dims


def _resolve_google_adc_project() -> Optional[str]:
    project = getattr(config, "GOOGLE_CLOUD_PROJECT", "") or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_PROJECT_ID")
    if project:
        return project
    try:
        import google.auth
        credentials, detected_project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        # 找不到 gcloud 命令时（如桌面版），用户登录凭据只能通过 quota_project_id 给出项目。
        return detected_project or getattr(credentials, "quota_project_id", None)
    except Exception:
        return None


# Google 图像接口常因限流返回 429：至少重试 5 次，等待约 5→10→20→40→60 秒。
@retry_on_failure(max_retries=5, delay=5.0)
def text_to_image_google(prompt, size="1024x1024", model="gemini-3.1-flash-image", use_adc=False):
    aspect_ratio, image_size, mapped_dims = _map_custom_size_to_google(size, model)
    if not _parse_wxh_size(size):
        logger.warning(f"Google图像尺寸格式无法解析: {size}，已回退到 {aspect_ratio}/{image_size}")
    logger.info(f"使用Google官方GenAI生成图像，模型: {model}，请求尺寸: {size} -> {aspect_ratio}/{image_size} ({mapped_dims[0]}x{mapped_dims[1]})")
    logger.info(f"Google图像提示词长度: {len(prompt)}字符")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        logger.error("未安装google-genai，请运行: pip install google-genai")
        raise APIError("缺少依赖包google-genai", retryable=False) from exc

    if use_adc:
        project = _resolve_google_adc_project()
        if not project:
            raise APIError("Google ADC项目未配置，请运行 gcloud auth application-default login 或设置 GOOGLE_CLOUD_PROJECT", retryable=False)
        location = getattr(config, "GOOGLE_CLOUD_LOCATION", "") or os.getenv("GOOGLE_CLOUD_LOCATION") or "global"
        target = f"项目 {project}（{location}）"
    elif not config.GOOGLE_CLOUD_API_KEY:
        raise APIError("GOOGLE_CLOUD_API_KEY未配置", retryable=False)
    else:
        target = "该 API 密钥"

    try:
        if use_adc:
            client = genai.Client(vertexai=True, project=project, location=location)
        else:
            client = genai.Client(vertexai=True, api_key=config.GOOGLE_CLOUD_API_KEY)

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            )
        ]
        generate_content_config = types.GenerateContentConfig(
            temperature=1.0,
            top_p=0.95,
            max_output_tokens=32768,
            response_modalities=["TEXT", "IMAGE"],
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
            ],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                output_mime_type="image/png",
            ),
            thinking_config=types.ThinkingConfig(
                thinking_level="MINIMAL",
            ),
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                image_bytes = getattr(inline_data, "data", None) if inline_data else None
                if not image_bytes:
                    continue
                if isinstance(image_bytes, memoryview):
                    image_bytes = image_bytes.tobytes()
                if isinstance(image_bytes, (bytes, bytearray)):
                    return {"type": "bytes", "data": bytes(image_bytes)}
    except Exception as e:
        status = http_status(e)
        if status == 404:
            message = f"Google图像模型 {model} 对{target}不可用（404）。请在设置中改用可用的模型，例如 gemini-3.1-flash-image"
        elif status in (401, 403):
            message = f"Google拒绝了{target}的请求（{status}），请检查凭据和 Vertex AI 权限: {e}"
        else:
            message = f"Google官方图像生成失败: {e}"
        logger.error(message)
        raise APIError(message) from e

    raise APIError("Google官方图像生成未返回图片数据")



__all__ = [
    'text_to_text',
    'text_to_image_doubao',
    'text_to_image_google',
]
