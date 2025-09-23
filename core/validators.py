"""
Lightweight validators and server detection for startup-time checks.
Keep this minimal to simplify main.py.
"""

from typing import Tuple

from config import config


def auto_detect_server_from_model(model_name: str, model_type: str) -> str:
    """Infer provider from model name.

    model_type: "llm" | "image" | "voice"
    """
    if model_type == "llm":
        if any(prefix in model_name for prefix in ["google/", "anthropic/", "meta/"]):
            return "openrouter"
        if any(prefix in model_name for prefix in ["zai-org/", "moonshotai/", "Qwen/"]):
            return "siliconflow"
        return "openrouter"

    if model_type == "image":
        lower_name = model_name.lower()
        if "doubao" in lower_name or "seedream" in lower_name:
            return "doubao"
        if lower_name.startswith("qwen/") or "qwen-image" in lower_name:
            return "siliconflow"
        return "doubao"

    if model_type == "voice":
        if "_bigtts" in model_name:
            return "bytedance"
        return "bytedance"

    return "unknown"


def validate_startup_args(
    target_length: int,
    num_segments: int,
    image_size: str,
    llm_model: str,
    image_model: str,
    voice: str,
    images_method: str = None,
) -> Tuple[str, str, str]:
    """Validate top-level args once at startup and return detected servers.

    Uses config-driven limits and supported providers. No hardcoded ranges here.
    Returns: (llm_server, image_server, tts_server)
    """
    # Detect providers from model names
    llm_server = auto_detect_server_from_model(llm_model, "llm")
    image_server = auto_detect_server_from_model(image_model, "image")
    tts_server = auto_detect_server_from_model(voice, "voice")

    # Delegate validation to config to avoid hardcoded limits
    config.validate_parameters(
        int(target_length),
        int(num_segments),
        llm_server,
        image_server,
        tts_server,
        image_size,
        images_method,
    )

    return llm_server, image_server, tts_server


__all__ = [
    "auto_detect_server_from_model",
    "validate_startup_args",
]
