"""Configuration loading, validation, and runtime parameter objects.

User-facing settings live in config.yaml; config.example.yaml holds the built-in
defaults. Read values through `from core.config import config`.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Mapping
from dotenv import load_dotenv
import yaml

# 加载环境变量
load_dotenv()


# =============================================================================
# 静态声明配置常量占位符，以消除 IDE 未定义变量报警。
# 运行时会被 globals().update(...) 动态加载的 YAML 默认值覆盖。
# =============================================================================
OPENING_QUOTE: bool = True

LLM_SERVER_STEP1: str = ""
LLM_MODEL_STEP1: str = ""
STEP1_AGENT_SKILL: str = ""

NUM_SEGMENTS: int = 10
STEP1_5_SPLIT_MODE: str = "punctuation"
LLM_SERVER_STEP1_5: str = ""
LLM_MODEL_STEP1_5: str = ""

LLM_SERVER_STEP2: str = ""
LLM_MODEL_STEP2: str = ""
LLM_TEMPERATURE_DESCRIPTION: float = 0.5

VOICE: str = ""
RESOURCE_ID: str = ""
TTS_MODEL: str = ""
TTS_EMOTION: str = ""
TTS_EMOTION_SCALE: int = 0
TTS_SPEECH_RATE: int = 0
TTS_LOUDNESS_RATE: int = 0
MUTE_CUT_THRESHOLD: int = 0
MUTE_CUT_MIN_SILENCE_MS: int = 0
MUTE_CUT_REMAIN_MS: int = 0
MAX_CONCURRENT_VOICE_SYNTHESIS: int = 1

OPENING_MOTION_IP_NAME: str = ""
OPENING_MOTION_DURATION_SECONDS: float = 0.0
OPENING_MOTION_FPS: int = 0
OPENING_MOTION_FIRST_LINE_SECONDS: float = 0.0
OPENING_MOTION_LAST_LINE_SECONDS: float = 0.0
OPENING_MOTION_MAX_LINES: int = 0
OPENING_MOTION_MAX_CHARS_PER_LINE: int = 0

VISUAL_MODE: str = ""
MOTION_STYLE_PRESET: str = ""
MOTION_MAX_TURNS: int = 60
MOTION_RENDER_FPS: int = 0
MOTION_CONCURRENCY: int = 1
IMAGE_SERVER: str = ""
IMAGE_SIZE: str = ""
IMAGE_MODEL: str = ""
IMAGE_STYLE_PRESET: str = ""
IMAGE_PROMPT_TEMPLATE: str = "keywords"
MAX_CONCURRENT_IMAGE_GENERATION: int = 1
SEEDREAM_MAX_CONCURRENT_IMAGE_GENERATION: int = 5
LLM_SERVER_STEP4: str = ""
LLM_MODEL_STEP4: str = ""

VIDEO_SIZE: str = ""
VIDEO_OUTPUT_FPS: int = 0
VIDEO_CODEC: str = ""
VIDEO_BITRATE_MODE: str = ""
VIDEO_QUALITY_LEVEL: int = 0
THREE_BY_FOUR_QUALITY_LEVEL: int = 86
THREE_BY_FOUR_ENABLED: bool = True
THREE_BY_FOUR_THEME: str = "ink"
THREE_BY_FOUR_TOP_SHARE: float = 0.5
THREE_BY_FOUR_TOP_CONTENT: str = "title_subtitle"
THREE_BY_FOUR_TITLE_TEXT: str = ""
THREE_BY_FOUR_SUBTITLE_TEXT: str = ""
THREE_BY_FOUR_BOTTOM_CONTENT: str = "quote"
THREE_BY_FOUR_BOTTOM_TEXT: str = ""
THREE_BY_FOUR_ACCENT_COLOR: str = "#C45A47"
ENABLE_SUBTITLES: bool = True
DEFAULT_BGM_FILENAME: str = ""
BGM_DEFAULT_VOLUME: float = 0.0
NARRATION_DEFAULT_VOLUME: float = 0.0
NARRATION_SPEED_FACTOR: float = 1.0
IMAGE_ZOOM_IN_RATIO: float = 1.0
BGM_NORMALIZE_LOUDNESS: bool = False
BGM_TARGET_LOUDNESS: float = 0.0
BGM_LOUDNESS_RANGE: float = 0.0
AUDIO_DUCKING_ENABLED: bool = False
AUDIO_DUCKING_STRENGTH: float = 0.0
AUDIO_DUCKING_SMOOTH_SECONDS: float = 0.0
OPENING_FADEIN_SECONDS: float = 0.0
ENDING_FADE_SECONDS: float = 0.0
ENABLE_TRANSITIONS: bool = False
TRANSITION_DURATION: float = 0.0
TRANSITION_STYLE: str = ""
VIDEO_MATERIAL_REMOVE_AUDIO: bool = False
VIDEO_MATERIAL_LONGER_THAN_AUDIO_MODE: str = ""

SUBTITLE_FONT_SIZE: int = 0
SUBTITLE_STYLE: str = "classic"
SUBTITLE_FONT_FAMILY: str = ""
SUBTITLE_FONT_TTC_INDEX: int = 0
SUBTITLE_COLOR: str = ""
SUBTITLE_STROKE_COLOR: str = ""
SUBTITLE_STROKE_WIDTH: int = 0
SUBTITLE_POSITION: tuple = ("center", "bottom")
SUBTITLE_MARGIN_BOTTOM: int = 0
SUBTITLE_MAX_CHARS_PER_LINE: int = 0
SUBTITLE_MAX_LINES: int = 0
SUBTITLE_LINE_SPACING: int = 0
SUBTITLE_LETTER_SPACING: int = 0
SUBTITLE_BACKGROUND_COLOR: tuple = (0, 0, 0)
SUBTITLE_BACKGROUND_OPACITY: float = 0.0
SUBTITLE_BACKGROUND_H_PADDING: int = 0
SUBTITLE_BACKGROUND_V_PADDING: int = 0
SUBTITLE_SHADOW_ENABLED: bool = False
SUBTITLE_SHADOW_COLOR: str = ""
SUBTITLE_SHADOW_OFFSET: tuple = (0, 0)

COVER_IMAGE_SIZE_PRESETS: dict = {}
COVER_IMAGE_SIZE_KEYS: list = []
COVER_IMAGE_MODEL: str = ""
COVER_IMAGE_SERVER: str = ""
COVER_IMAGE_STYLE: str = ""
COVER_IMAGE_COUNT: int = 1




_YAML_SCHEMA: Dict[str, Dict[str, str]] = {
    "global": {"opening_quote": "OPENING_QUOTE"},
    "step1": {
        "llm_server": "LLM_SERVER_STEP1",
        "llm_model": "LLM_MODEL_STEP1",
        "agent_skill": "STEP1_AGENT_SKILL",
    },
    "step1_5": {
        "num_segments": "NUM_SEGMENTS",
        "split_mode": "STEP1_5_SPLIT_MODE",
        "llm_server": "LLM_SERVER_STEP1_5",
        "llm_model": "LLM_MODEL_STEP1_5",
    },
    "step2": {
        "llm_server": "LLM_SERVER_STEP2",
        "llm_model": "LLM_MODEL_STEP2",
        "llm_temperature_description": "LLM_TEMPERATURE_DESCRIPTION",
    },
    "step3": {
        "voice": "VOICE",
        "resource_id": "RESOURCE_ID",
        "tts_model": "TTS_MODEL",
        "emotion": "TTS_EMOTION",
        "emotion_scale": "TTS_EMOTION_SCALE",
        "speech_rate": "TTS_SPEECH_RATE",
        "loudness_rate": "TTS_LOUDNESS_RATE",
        "mute_cut_threshold": "MUTE_CUT_THRESHOLD",
        "mute_cut_min_silence_ms": "MUTE_CUT_MIN_SILENCE_MS",
        "mute_cut_remain_ms": "MUTE_CUT_REMAIN_MS",
        "max_concurrent_voice_synthesis": "MAX_CONCURRENT_VOICE_SYNTHESIS",
    },
    "motion_opening": {
        "ip_name": "OPENING_MOTION_IP_NAME",
        "duration_seconds": "OPENING_MOTION_DURATION_SECONDS",
        "fps": "OPENING_MOTION_FPS",
        "first_line_seconds": "OPENING_MOTION_FIRST_LINE_SECONDS",
        "last_line_seconds": "OPENING_MOTION_LAST_LINE_SECONDS",
        "max_lines": "OPENING_MOTION_MAX_LINES",
        "max_chars_per_line": "OPENING_MOTION_MAX_CHARS_PER_LINE",
    },
    "step4": {
        "visual_mode": "VISUAL_MODE",
        "motion_style_preset": "MOTION_STYLE_PRESET",
        "motion_max_turns": "MOTION_MAX_TURNS",
        "motion_render_fps": "MOTION_RENDER_FPS",
        "motion_concurrency": "MOTION_CONCURRENCY",
        "image_server": "IMAGE_SERVER",
        "image_size": "IMAGE_SIZE",
        "image_model": "IMAGE_MODEL",
        "image_style_preset": "IMAGE_STYLE_PRESET",
        "image_prompt_template": "IMAGE_PROMPT_TEMPLATE",
        "max_concurrent_image_generation": "MAX_CONCURRENT_IMAGE_GENERATION",
        "seedream_max_concurrent_image_generation": "SEEDREAM_MAX_CONCURRENT_IMAGE_GENERATION",
        "llm_server": "LLM_SERVER_STEP4",
        "llm_base_url": "LLM_BASE_URL_STEP4_OVERRIDE",
        "llm_model": "LLM_MODEL_STEP4",
    },
    "step5": {
        "video_size": "VIDEO_SIZE",
        "video_output_fps": "VIDEO_OUTPUT_FPS",
        "video_codec": "VIDEO_CODEC",
        "video_bitrate_mode": "VIDEO_BITRATE_MODE",
        "video_quality_level": "VIDEO_QUALITY_LEVEL",
        "three_by_four_quality_level": "THREE_BY_FOUR_QUALITY_LEVEL",
        "enable_subtitles": "ENABLE_SUBTITLES",
        "bgm_filename": "DEFAULT_BGM_FILENAME",
        "bgm_default_volume": "BGM_DEFAULT_VOLUME",
        "narration_default_volume": "NARRATION_DEFAULT_VOLUME",
        "narration_speed_factor": "NARRATION_SPEED_FACTOR",
        "image_zoom_in_ratio": "IMAGE_ZOOM_IN_RATIO",
        "bgm_normalize_loudness": "BGM_NORMALIZE_LOUDNESS",
        "bgm_target_loudness": "BGM_TARGET_LOUDNESS",
        "bgm_loudness_range": "BGM_LOUDNESS_RANGE",
        "audio_ducking_enabled": "AUDIO_DUCKING_ENABLED",
        "audio_ducking_strength": "AUDIO_DUCKING_STRENGTH",
        "audio_ducking_smooth_seconds": "AUDIO_DUCKING_SMOOTH_SECONDS",
        "opening_fadein_seconds": "OPENING_FADEIN_SECONDS",
        "ending_fade_seconds": "ENDING_FADE_SECONDS",
        "enable_transitions": "ENABLE_TRANSITIONS",
        "transition_duration": "TRANSITION_DURATION",
        "transition_style": "TRANSITION_STYLE",
        "video_material_remove_audio": "VIDEO_MATERIAL_REMOVE_AUDIO",
        "video_material_longer_than_audio_mode": "VIDEO_MATERIAL_LONGER_THAN_AUDIO_MODE",
    },
    "three_by_four": {
        "enabled": "THREE_BY_FOUR_ENABLED",
        "theme": "THREE_BY_FOUR_THEME",
        "top_share": "THREE_BY_FOUR_TOP_SHARE",
        "top_content": "THREE_BY_FOUR_TOP_CONTENT",
        "title_text": "THREE_BY_FOUR_TITLE_TEXT",
        "subtitle_text": "THREE_BY_FOUR_SUBTITLE_TEXT",
        "bottom_content": "THREE_BY_FOUR_BOTTOM_CONTENT",
        "bottom_text": "THREE_BY_FOUR_BOTTOM_TEXT",
        "accent_color": "THREE_BY_FOUR_ACCENT_COLOR",
    },
    "subtitles": {
        "style": "SUBTITLE_STYLE",
        "font_size": "SUBTITLE_FONT_SIZE",
        "font_family": "SUBTITLE_FONT_FAMILY",
        "font_ttc_index": "SUBTITLE_FONT_TTC_INDEX",
        "color": "SUBTITLE_COLOR",
        "stroke_color": "SUBTITLE_STROKE_COLOR",
        "stroke_width": "SUBTITLE_STROKE_WIDTH",
        "position": "SUBTITLE_POSITION",
        "margin_bottom": "SUBTITLE_MARGIN_BOTTOM",
        "max_chars_per_line": "SUBTITLE_MAX_CHARS_PER_LINE",
        "max_lines": "SUBTITLE_MAX_LINES",
        "line_spacing": "SUBTITLE_LINE_SPACING",
        "letter_spacing": "SUBTITLE_LETTER_SPACING",
        "background_color": "SUBTITLE_BACKGROUND_COLOR",
        "background_opacity": "SUBTITLE_BACKGROUND_OPACITY",
        "background_h_padding": "SUBTITLE_BACKGROUND_H_PADDING",
        "background_v_padding": "SUBTITLE_BACKGROUND_V_PADDING",
        "shadow_enabled": "SUBTITLE_SHADOW_ENABLED",
        "shadow_color": "SUBTITLE_SHADOW_COLOR",
        "shadow_offset": "SUBTITLE_SHADOW_OFFSET",
    },
    "step6": {
        "cover_image_size_presets": "COVER_IMAGE_SIZE_PRESETS",
        "cover_image_size_keys": "COVER_IMAGE_SIZE_KEYS",
        "cover_image_model": "COVER_IMAGE_MODEL",
        "cover_image_server": "COVER_IMAGE_SERVER",
        "cover_image_style": "COVER_IMAGE_STYLE",
        "cover_image_count": "COVER_IMAGE_COUNT",
    },
}

# Settings that no longer do anything. Older config.yaml files and the desktop
# app's saved job configs still carry them, so loading skips them instead of failing.
_RETIRED_YAML_KEYS = {
    "step5": {"image_material_target_fps", "video_material_duration_adjust", "video_material_resize_method"},
    "step6": {"default_cover_image_size_key"},
}

_STRUCTURED_YAML_SCHEMA = {
    "step1": {"subagents": "STEP1_SUBAGENTS"},
}

STEP1_SUBAGENTS = {"enabled": False, "agents": {}}

_PARAM_CONSTANTS = {
    "num_segments": "NUM_SEGMENTS",
    "step1_5_split_mode": "STEP1_5_SPLIT_MODE",
    "llm_server_step1_5": "LLM_SERVER_STEP1_5",
    "llm_model_step1_5": "LLM_MODEL_STEP1_5",
    "image_size": "IMAGE_SIZE",
    "video_size": "VIDEO_SIZE",
    "llm_model_step2": "LLM_MODEL_STEP2",
    "llm_server_step2": "LLM_SERVER_STEP2",
    "image_server": "IMAGE_SERVER",
    "image_model": "IMAGE_MODEL",
    "visual_mode": "VISUAL_MODE",
    "motion_style_preset": "MOTION_STYLE_PRESET",
    "motion_max_turns": "MOTION_MAX_TURNS",
    "motion_render_fps": "MOTION_RENDER_FPS",
    "motion_concurrency": "MOTION_CONCURRENCY",
    "llm_server_step4": "LLM_SERVER_STEP4",
    "llm_base_url_step4": "LLM_BASE_URL_STEP4_OVERRIDE",
    "llm_model_step4": "LLM_MODEL_STEP4",
    "voice": "VOICE",
    "resource_id": "RESOURCE_ID",
    "tts_model": "TTS_MODEL",
    "tts_emotion": "TTS_EMOTION",
    "tts_emotion_scale": "TTS_EMOTION_SCALE",
    "tts_speech_rate": "TTS_SPEECH_RATE",
    "tts_loudness_rate": "TTS_LOUDNESS_RATE",
    "mute_cut_threshold": "MUTE_CUT_THRESHOLD",
    "mute_cut_min_silence_ms": "MUTE_CUT_MIN_SILENCE_MS",
    "mute_cut_remain_ms": "MUTE_CUT_REMAIN_MS",
    "image_style_preset": "IMAGE_STYLE_PRESET",
    "image_prompt_template": "IMAGE_PROMPT_TEMPLATE",
    "enable_subtitles": "ENABLE_SUBTITLES",
    "bgm_filename": "DEFAULT_BGM_FILENAME",
    "opening_quote": "OPENING_QUOTE",
    "cover_image_model": "COVER_IMAGE_MODEL",
    "cover_image_server": "COVER_IMAGE_SERVER",
    "cover_image_style": "COVER_IMAGE_STYLE",
    "cover_image_count": "COVER_IMAGE_COUNT",
}

_KNOWN_CONFIG_CONSTANTS = {
    constant for section in _YAML_SCHEMA.values() for constant in section.values()
} | {constant for section in _STRUCTURED_YAML_SCHEMA.values() for constant in section.values()}


def _normalize_step1_subagents(value: object) -> dict:
    if value is None:
        return dict(STEP1_SUBAGENTS)
    if not isinstance(value, Mapping):
        raise ValueError("配置项 step1.subagents 必须是对象")

    allowed_top = {"enabled", "agents"}
    unknown = set(value) - allowed_top
    if unknown:
        raise ValueError(f"未知配置项: step1.subagents.{sorted(unknown)[0]}")

    agents_value = value.get("agents", {})
    if not isinstance(agents_value, Mapping):
        raise ValueError("配置项 step1.subagents.agents 必须是对象")

    allowed_agent = {"enabled", "description", "prompt_file", "model", "max_turns", "tools", "background"}
    agents: Dict[str, dict] = {}
    for name, agent_config in agents_value.items():
        if not isinstance(agent_config, Mapping):
            raise ValueError(f"配置项 step1.subagents.agents.{name} 必须是对象")
        unknown = set(agent_config) - allowed_agent
        if unknown:
            raise ValueError(f"未知配置项: step1.subagents.agents.{name}.{sorted(unknown)[0]}")
        tools = agent_config.get("tools")
        if tools is not None and not (
            isinstance(tools, list) and all(isinstance(tool, str) for tool in tools)
        ):
            raise ValueError(f"配置项 step1.subagents.agents.{name}.tools 必须是字符串列表")
        max_turns = agent_config.get("max_turns")
        if max_turns is not None and not isinstance(max_turns, int):
            raise ValueError(f"配置项 step1.subagents.agents.{name}.max_turns 必须是整数")
        background = agent_config.get("background")
        if background is not None and not isinstance(background, bool):
            raise ValueError(f"配置项 step1.subagents.agents.{name}.background 必须是布尔值")
        agents[str(name)] = dict(agent_config)

    return {
        "enabled": bool(value.get("enabled", False)),
        "agents": agents,
    }


def _coerce_yaml_value(constant_name: str, value: object) -> object:
    if constant_name in {"SUBTITLE_POSITION", "SUBTITLE_SHADOW_OFFSET", "SUBTITLE_BACKGROUND_COLOR"}:
        if isinstance(value, list):
            return tuple(value)
    if constant_name in {"IMAGE_SIZE", "VIDEO_SIZE"} and isinstance(value, str):
        return value.lower().replace("×", "x").replace("*", "x").replace(" ", "")
    return value


def _load_yaml_overrides(config_path: str | os.PathLike[str]) -> Dict[str, object]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, Mapping):
        raise ValueError("YAML配置必须是对象")

    # Read existing project configs using the new motion option names.
    data = dict(data)
    if "hyperframes_opening" in data:
        data.setdefault("motion_opening", data.pop("hyperframes_opening"))
    if isinstance(data.get("step4"), Mapping):
        values = dict(data["step4"])
        for suffix in ("style_preset", "max_turns", "render_fps", "concurrency"):
            old = "hyperframes_" + suffix
            if old in values:
                values.setdefault("motion_" + suffix, values.pop(old))
        if values.get("visual_mode") == "hyperframes_agent":
            values["visual_mode"] = "motion_agent"
        data["step4"] = values
    for old in list(data):
        if isinstance(old, str) and (old.startswith("OPENING_HYPERFRAMES_") or old.startswith("HYPERFRAMES_")):
            new = old.replace("OPENING_HYPERFRAMES_", "OPENING_MOTION_").replace("HYPERFRAMES_", "MOTION_")
            data.setdefault(new, data.pop(old))

    overrides: Dict[str, object] = {}
    for section, values in data.items():
        if isinstance(section, str) and section.isupper():
            if section not in _KNOWN_CONFIG_CONSTANTS:
                raise ValueError(f"未知配置项: {section}")
            overrides[section] = _coerce_yaml_value(section, values)
            continue
        if section not in _YAML_SCHEMA:
            raise ValueError(f"未知配置分组: {section}")
        if not isinstance(values, Mapping):
            raise ValueError(f"配置分组 {section} 必须是对象")
        allowed = _YAML_SCHEMA[section]
        structured = _STRUCTURED_YAML_SCHEMA.get(section, {})
        retired = _RETIRED_YAML_KEYS.get(section, set())
        for key, value in values.items():
            if key in retired:
                continue
            if key in structured:
                overrides[structured[key]] = _normalize_step1_subagents(value)
                continue
            if key not in allowed:
                raise ValueError(f"未知配置项: {section}.{key}")
            constant_name = allowed[key]
            overrides[constant_name] = _coerce_yaml_value(constant_name, value)
    return overrides


LLM_BASE_URL_STEP4_OVERRIDE = ""
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.example.yaml"
globals().update(_load_yaml_overrides(_DEFAULT_CONFIG_PATH))

# .env may override the TTS voice so personal voice IDs do not need to live in YAML.
VOICE = os.getenv("BYTEDANCE_TTS_VOICE_ID", str(globals().get("VOICE", ""))).strip() or globals().get("VOICE", "")
globals()["VOICE"] = VOICE


def _llm_base_url_for(server: str) -> str:
    return Config.LLM_SERVER_URLS.get((server or "").strip().lower(), "")


def _resolve_step4_llm_base_url(params: Mapping[str, object]) -> str:
    override = str(params.get("llm_base_url_step4") or "").strip()
    if override:
        return override
    return _llm_base_url_for(str(params.get("llm_server_step4") or ""))


def _base_generation_params() -> Dict[str, object]:
    values = globals()
    params = {key: values[constant] for key, constant in _PARAM_CONSTANTS.items()}
    params["llm_base_url_step2"] = config.LLM_BASE_URL_STEP2
    params["llm_base_url_step4"] = _resolve_step4_llm_base_url(params)
    params["output_dir"] = "output"
    return params


def _apply_param_overrides(params: Dict[str, object], overrides: Dict[str, object]) -> Dict[str, object]:
    constant_to_param = {constant: key for key, constant in _PARAM_CONSTANTS.items()}
    for constant, value in overrides.items():
        key = constant_to_param.get(constant)
        if key:
            params[key] = value
    params["llm_base_url_step2"] = _llm_base_url_for(str(params.get("llm_server_step2") or ""))
    if "LLM_BASE_URL_STEP4_OVERRIDE" not in overrides:
        params["llm_base_url_step4"] = ""
    params["llm_base_url_step4"] = _resolve_step4_llm_base_url(params)
    return params


def get_generation_params(config_path: Optional[str | os.PathLike[str]] = None) -> Dict[str, object]:
    """返回生成参数字典（供 CLI 使用）。"""
    params = _base_generation_params()
    if config_path:
        _apply_param_overrides(params, _load_yaml_overrides(config_path))
    return params


class Config:
    """系统配置类：用户参数由模块常量注入，密钥与校验逻辑定义在类上。"""

    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    MIMO_API_KEY = os.getenv("MIMO_API_KEY")
    KIMI_API_KEY = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    VOLCENGINE_API_KEY = os.getenv("VOLCENGINE_API_KEY") or os.getenv("SEEDREAM_API_KEY")
    SILICONFLOW_KEY = os.getenv("SILICONFLOW_KEY")
    GOOGLE_CLOUD_API_KEY = os.getenv("GOOGLE_CLOUD_API_KEY")
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_PROJECT_ID")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
    BYTEDANCE_TTS_API_KEY = os.getenv("BYTEDANCE_TTS_API_KEY")

    ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    DEFAULT_IMAGE_SIZE = "1664x928"
    DEFAULT_VOICE = VOICE
    DEFAULT_OUTPUT_DIR = "output"

    SUPPORTED_LLM_SERVERS = ["openrouter", "siliconflow", "mimo", "kimi", "deepseek", "volcengine"]
    SUPPORTED_IMAGE_SERVERS = ["doubao", "google", "google_adc"]
    SUPPORTED_TTS_SERVERS = ["bytedance"]
    RECOMMENDED_MODELS = {
        "llm": {
            "openrouter": [LLM_MODEL_STEP2],
            "siliconflow": [LLM_MODEL_STEP2],
        },
        "image": {
            "doubao": [
                "doubao-seedream-5-0-pro-260628",
                "doubao-seedream-5-0-260128",
                "doubao-seedream-5-0-flash-260915",
                "doubao-seedream-4-0-250828",
                "doubao-seedream-3-0-t2i-250415",
            ],
            "google": [
                "gemini-3.1-flash-image",
                "gemini-3-pro-image",
                "gemini-3.1-flash-lite-image",
                "gemini-nano-banana-2.1",
            ],
            "google_adc": [
                "gemini-3.1-flash-image",
                "gemini-3-pro-image",
                "gemini-3.1-flash-lite-image",
                "gemini-nano-banana-2.1",
            ],
        },
        "voice": [
            "zh_female_vv_uranus_bigtts",
            "zh_male_yuanboxiaoshu_moon_bigtts",
            "zh_male_haoyuxiaoge_moon_bigtts",
            "zh_female_wenrouxiaoya_moon_bigtts",
            "zh_female_daimengchuanmei_moon_bigtts",
        ],
    }
    SEEDREAM_V5_MIN_PIXELS = 3686400
    MIN_NUM_SEGMENTS = 5
    MAX_NUM_SEGMENTS = 100
    SPEECH_SPEED_WPM = 250

    @classmethod
    def validate_image_size(cls, size: str, model: str) -> bool:
        """验证图像尺寸是否符合模型要求"""
        if not size:
            return False
        size = size.lower().replace("×", "x").replace("*", "x")
        if "x" not in size:
            return False
        try:
            width, height = map(int, size.split("x"))
        except ValueError:
            return False
        if "doubao" in model.lower():
            if "seedream-5" in model.lower():
                return width * height >= cls.SEEDREAM_V5_MIN_PIXELS and width <= 4096 and height <= 4096
            if "seedream-4" in model.lower():
                return 1280 <= width <= 4096 and 720 <= height <= 4096
            if "seedream-3" in model.lower():
                return 512 <= width <= 2048 and 512 <= height <= 2048
        return True

    @classmethod
    def validate_model_provider_pair(cls, model_type: str, server: str, model: str) -> None:
        """严格校验模型与供应商组合，不允许自动推断。"""
        server = (server or "").strip().lower()
        model = (model or "").strip()
        lower_model = model.lower()

        if not server:
            raise ValueError(f"{model_type} 的供应商不能为空")
        if not model:
            raise ValueError(f"{model_type} 的模型不能为空")

        if model_type == "image":
            if server == "doubao":
                if "doubao" not in lower_model and "seedream" not in lower_model:
                    raise ValueError(f"图像模型 {model} 与供应商 {server} 不匹配")
                return
            if server in {"google", "google_adc"}:
                if "gemini" not in lower_model and "imagen" not in lower_model:
                    raise ValueError(f"图像模型 {model} 与供应商 {server} 不匹配")
                return
            raise ValueError(f"不支持的图像服务商: {server}，支持的服务商: {cls.SUPPORTED_IMAGE_SERVERS}")

        if model_type == "voice":
            if server not in cls.SUPPORTED_TTS_SERVERS:
                raise ValueError(f"不支持的TTS服务商: {server}，支持的服务商: {cls.SUPPORTED_TTS_SERVERS}")
            return

        raise ValueError(f"不支持的模型类型: {model_type}")

    @classmethod
    def validate_image_prompt_template(cls, template_name: str) -> str:
        """Validate and normalize a configured step-4 image prompt template name."""
        from core.prompts import (
            DEFAULT_STEP4_IMAGE_PROMPT_TEMPLATE,
            get_step4_image_description_prompt_template,
        )

        name = str(template_name or DEFAULT_STEP4_IMAGE_PROMPT_TEMPLATE).strip()
        name = name or DEFAULT_STEP4_IMAGE_PROMPT_TEMPLATE
        get_step4_image_description_prompt_template(name)
        return name

    @classmethod
    def validate_parameters(
        cls,
        num_segments: int,
        llm_server: str,
        image_server: str,
        tts_server: str,
        image_model: str,
        image_size: str,
        *,
        llm_model: str = None,
        image_prompt_template: str = None,
    ) -> None:
        """验证所有参数的有效性"""
        if not cls.MIN_NUM_SEGMENTS <= num_segments <= cls.MAX_NUM_SEGMENTS:
            raise ValueError(f"num_segments必须在{cls.MIN_NUM_SEGMENTS}-{cls.MAX_NUM_SEGMENTS}之间")
        if llm_server not in cls.SUPPORTED_LLM_SERVERS:
            raise ValueError(f"不支持的LLM服务商: {llm_server}，支持的服务商: {cls.SUPPORTED_LLM_SERVERS}")
        if llm_model is not None and not str(llm_model).strip():
            raise ValueError("LLM模型不能为空")
        if image_server not in cls.SUPPORTED_IMAGE_SERVERS:
            raise ValueError(f"不支持的图像服务商: {image_server}，支持的服务商: {cls.SUPPORTED_IMAGE_SERVERS}")
        if tts_server not in cls.SUPPORTED_TTS_SERVERS:
            raise ValueError(f"不支持的TTS服务商: {tts_server}，支持的服务商: {cls.SUPPORTED_TTS_SERVERS}")
        cls.validate_model_provider_pair("image", image_server, image_model)
        if image_prompt_template is not None:
            cls.validate_image_prompt_template(image_prompt_template)
        if not cls.validate_image_size(image_size, image_model):
            raise ValueError(
                f"图像尺寸 {image_size} 不符合模型 {image_model} 的要求。\n"
                f"Doubao-5模型支持: 总像素不少于 {cls.SEEDREAM_V5_MIN_PIXELS}，宽高不超过 4096\n"
                f"Doubao-4模型支持: 1280x720 到 4096x4096 之间的任意尺寸\n"
                f"Doubao-3模型支持: 512x512 到 2048x2048 之间的任意尺寸"
            )

    # 统一管理 OpenAI SDK 格式的 Base URL 映射
    LLM_SERVER_URLS = {
        "siliconflow": "https://api.siliconflow.cn/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "mimo": "https://api.xiaomimimo.com/anthropic",
        "kimi": "https://api.moonshot.cn/v1",
        "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
        "deepseek": "https://api.deepseek.com/v1",
    }

    @property
    def LLM_BASE_URL_STEP2(self) -> str:
        """根据 LLM_SERVER_STEP2 自动匹配 base URL"""
        return self.LLM_SERVER_URLS.get((getattr(self, "LLM_SERVER_STEP2", "") or "").strip().lower(), "")

# 将用户配置区的模块常量挂到 Config，避免在类体内逐字段复制
for _name, _value in list(globals().items()):
    if _name.isupper() and not hasattr(Config, _name) and not isinstance(_value, type):
        setattr(Config, _name, _value)

config = Config()


def apply_yaml_config(config_path: str | os.PathLike[str]) -> Dict[str, object]:
    """加载 YAML 配置，并覆盖仍读取全局 config 的旧代码路径。"""
    overrides = _load_yaml_overrides(config_path)
    for name, value in overrides.items():
        globals()[name] = value
        setattr(Config, name, value)
        setattr(config, name, value)
    return overrides


def find_yaml_config(project_root: Optional[str | os.PathLike[str]] = None) -> Optional[Path]:
    """查找默认 YAML 配置：优先 AIGC_VIDEO_CONFIG，其次项目根目录 config.yaml。"""
    env_path = os.getenv("AIGC_VIDEO_CONFIG")
    if env_path:
        return Path(env_path).expanduser()
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[1]
    candidate = root / "config.yaml"
    return candidate if candidate.exists() else None


def _infer_image_server_from_model(model: str) -> str:
    """根据图像模型名推断供应商（用于兼容旧参数缺省场景）。"""
    lower_model = (model or "").strip().lower()
    if "doubao" in lower_model or "seedream" in lower_model:
        return "doubao"
    if "gemini" in lower_model or "imagen" in lower_model:
        return "google"
    return ""


def _resolve_cover_image_server(image_server: str, cover_model: str) -> str:
    inferred = _infer_image_server_from_model(cover_model)
    if inferred == "google" and image_server == "google_adc":
        return "google_adc"
    return inferred or image_server


# get_generation_params() 键名 -> VideoGenerationConfig 字段名
_CLI_PARAM_ALIASES = (
    ("tts_emotion", "emotion"),
    ("tts_emotion_scale", "emotion_scale"),
    ("tts_speech_rate", "speech_rate"),
    ("tts_loudness_rate", "loudness_rate"),
)


@dataclass
class VideoGenerationConfig:
    """视频生成配置类，封装所有生成参数"""
    
    # ==================== 输入输出配置 ====================
    input_file: str
    output_dir: str
    
    # ==================== 内容生成参数 ====================
    num_segments: int = NUM_SEGMENTS
    step1_5_split_mode: str = STEP1_5_SPLIT_MODE
    llm_server_step1_5: str = LLM_SERVER_STEP1_5
    llm_model_step1_5: str = LLM_MODEL_STEP1_5
    extra_requirements: str = ""
    
    # ==================== LLM 配置 ====================
    llm_server_step2: str = LLM_SERVER_STEP2
    llm_base_url_step2: str = ""
    llm_model_step2: str = LLM_MODEL_STEP2
    llm_server_step4: str = LLM_SERVER_STEP4
    llm_base_url_step4: str = ""
    llm_model_step4: str = LLM_MODEL_STEP4
    
    # ==================== 图像生成配置 ====================
    visual_mode: str = VISUAL_MODE
    motion_style_preset: str = MOTION_STYLE_PRESET
    motion_max_turns: int = MOTION_MAX_TURNS
    motion_render_fps: int = MOTION_RENDER_FPS
    motion_concurrency: int = MOTION_CONCURRENCY
    image_server: str = IMAGE_SERVER
    image_model: str = IMAGE_MODEL
    image_size: str = IMAGE_SIZE
    image_style_preset: str = IMAGE_STYLE_PRESET
    image_prompt_template: str = IMAGE_PROMPT_TEMPLATE
    
    # ==================== 语音合成配置 ====================
    tts_server: str = "bytedance"
    voice: str = VOICE
    tts_model: str = TTS_MODEL
    speech_rate: int = TTS_SPEECH_RATE
    loudness_rate: int = TTS_LOUDNESS_RATE
    emotion: str = TTS_EMOTION
    emotion_scale: int = TTS_EMOTION_SCALE
    mute_cut_remain_ms: int = MUTE_CUT_REMAIN_MS
    mute_cut_threshold: int = MUTE_CUT_THRESHOLD

    # ==================== 视频合成配置 ====================
    video_size: Optional[str] = None  # None 则使用 image_size
    enable_subtitles: bool = ENABLE_SUBTITLES
    opening_quote: bool = OPENING_QUOTE
    bgm_filename: Optional[str] = DEFAULT_BGM_FILENAME
    
    # ==================== 封面图配置 ====================
    cover_image_size: Optional[str] = None  # None 则使用 image_size
    cover_image_model: Optional[str] = None  # None 则使用 image_model
    cover_image_server: str = ""
    cover_image_style: str = COVER_IMAGE_STYLE
    cover_image_count: int = COVER_IMAGE_COUNT
    
    def __post_init__(self):
        """初始化后的验证和默认值设置"""
        self.image_prompt_template = Config.validate_image_prompt_template(self.image_prompt_template)

        # 规格化尺寸字符串中的分隔符
        if self.image_size:
            self.image_size = str(self.image_size).lower().replace("×", "x").replace("*", "x").replace(" ", "")
        if self.video_size:
            self.video_size = str(self.video_size).lower().replace("×", "x").replace("*", "x").replace(" ", "")
        if self.cover_image_size:
            self.cover_image_size = str(self.cover_image_size).lower().replace("×", "x").replace("*", "x").replace(" ", "")

        # 设置默认值
        if self.video_size is None:
            self.video_size = self.image_size
        if self.cover_image_size is None:
            self.cover_image_size = self.image_size
        if self.cover_image_model is None:
            self.cover_image_model = self.image_model
        if not self.cover_image_server:
            self.cover_image_server = _resolve_cover_image_server(self.image_server, self.cover_image_model)
    
    @classmethod
    def from_cli_params(
        cls,
        params: dict,
        *,
        input_file: str,
        output_dir: str,
        **overrides,
    ) -> "VideoGenerationConfig":
        """从 get_generation_params() 风格字典创建配置（含 CLI 字段别名，忽略未知键）。"""
        data = dict(params)
        for src, dst in _CLI_PARAM_ALIASES:
            if src in data:
                data[dst] = data.pop(src)
        data.update(input_file=input_file, output_dir=output_dir, **overrides)
        fields = cls.__dataclass_fields__
        return cls(**{k: v for k, v in data.items() if k in fields})

    def get_effective_video_size(self) -> str:
        """获取实际使用的视频尺寸"""
        return self.video_size or self.image_size
    
    def get_effective_cover_size(self) -> str:
        """获取实际使用的封面尺寸"""
        return self.cover_image_size or self.image_size
    
    def get_effective_cover_model(self) -> str:
        """获取实际使用的封面模型"""
        return self.cover_image_model or self.image_model

    def get_effective_cover_server(self) -> str:
        """获取实际使用的封面供应商"""
        return self.cover_image_server or _resolve_cover_image_server(
            self.image_server,
            self.cover_image_model or "",
        )
