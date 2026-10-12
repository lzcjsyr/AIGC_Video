from core.config import config, get_generation_params
from core.config import VideoGenerationConfig


def test_builtin_defaults_are_loaded_from_yaml_template():
    from pathlib import Path

    import core.config as config_module
    from core.config import get_generation_params, config

    template_path = Path(config_module.__file__).resolve().parents[1] / "config.example.yaml"

    defaults = get_generation_params()
    template_defaults = get_generation_params(template_path)
    defaults.pop("voice", None)
    template_defaults.pop("voice", None)

    assert defaults == template_defaults
    assert config.SUBTITLE_FONT_FAMILY == "auto"
    assert config.SUBTITLE_STYLE == "editorial"


def test_generation_params_can_be_loaded_from_nested_yaml(tmp_path):
    from core.config import get_generation_params

    config_path = tmp_path / "video.yaml"
    config_path.write_text(
        """
step1_5:
  num_segments: 12
  llm_server: kimi
  llm_model: kimi-k2.6
step2:
  llm_server: siliconflow
  llm_model: Pro/moonshotai/Kimi-K2.6
step3:
  voice: S_TEST
  tts_model: seed-tts-2.0-expressive
  speech_rate: 15
step4:
  image_server: google_adc
  image_model: gemini-3.1-flash-image
  image_size: 1920x1080
  image_style_preset: style08
  image_prompt_template: pure_images
step5:
  video_size: 1280x720
  three_by_four_quality_level: 82
  enable_subtitles: false
  bgm_filename: null
step6:
  cover_image_server: google_adc
  cover_image_model: gemini-3.1-flash-image
  cover_image_count: 2
""",
        encoding="utf-8",
    )

    params = get_generation_params(config_path)

    assert params["num_segments"] == 12
    assert params["llm_server_step1_5"] == "kimi"
    assert params["llm_model_step1_5"] == "kimi-k2.6"
    assert params["image_server"] == "google_adc"
    assert params["image_style_preset"] == "style08"
    assert params["image_prompt_template"] == "pure_images"
    assert params["voice"] == "S_TEST"
    assert params["tts_speech_rate"] == 15
    assert params["enable_subtitles"] is False
    assert params["bgm_filename"] is None
    assert config.THREE_BY_FOUR_QUALITY_LEVEL == 86
    assert params["cover_image_count"] == 2


def test_yaml_runtime_overrides_update_global_config_for_legacy_readers(tmp_path):
    import core.config as config_module
    from core.config import Config, apply_yaml_config, config

    original = {
        "SUBTITLE_FONT_SIZE": config.SUBTITLE_FONT_SIZE,
        "OPENING_HYPERFRAMES_IP_NAME": config.OPENING_HYPERFRAMES_IP_NAME,
        "MAX_CONCURRENT_IMAGE_GENERATION": config.MAX_CONCURRENT_IMAGE_GENERATION,
        "BGM_DEFAULT_VOLUME": config.BGM_DEFAULT_VOLUME,
        "IMAGE_ZOOM_IN_RATIO": config.IMAGE_ZOOM_IN_RATIO,
        "THREE_BY_FOUR_QUALITY_LEVEL": config.THREE_BY_FOUR_QUALITY_LEVEL,
    }
    config_path = tmp_path / "video.yaml"
    config_path.write_text(
        """
subtitles:
  font_size: 56
hyperframes_opening:
  ip_name: 测试刊头
step4:
  max_concurrent_image_generation: 4
step5:
  bgm_default_volume: 0.25
  image_zoom_in_ratio: 1.08
  three_by_four_quality_level: 82
""",
        encoding="utf-8",
    )

    try:
        apply_yaml_config(config_path)

        assert config.SUBTITLE_FONT_SIZE == 56
        assert config.OPENING_HYPERFRAMES_IP_NAME == "测试刊头"
        assert config.MAX_CONCURRENT_IMAGE_GENERATION == 4
        assert config.BGM_DEFAULT_VOLUME == 0.25
        assert config.IMAGE_ZOOM_IN_RATIO == 1.08
        assert config.THREE_BY_FOUR_QUALITY_LEVEL == 82
    finally:
        for key, value in original.items():
            setattr(Config, key, value)
            setattr(config, key, value)
            setattr(config_module, key, value)


def test_yaml_config_rejects_unknown_keys(tmp_path):
    import pytest

    from core.config import get_generation_params

    config_path = tmp_path / "bad.yaml"
    config_path.write_text("step4:\n  typo_image_model: nope\n", encoding="utf-8")

    with pytest.raises(ValueError, match="未知配置项"):
        get_generation_params(config_path)


def test_from_cli_params_maps_tts_aliases():
    params = get_generation_params()
    gen = VideoGenerationConfig.from_cli_params(
        params,
        input_file="input/book.pdf",
        output_dir="output",
        tts_server="bytedance",
    )
    assert gen.speech_rate == params["tts_speech_rate"]
    assert gen.emotion == params["tts_emotion"]
    assert gen.input_file == "input/book.pdf"
    assert gen.num_segments == params["num_segments"]
    assert gen.image_prompt_template == params["image_prompt_template"] == "keywords"


def test_video_generation_config_rejects_unknown_image_prompt_template():
    import pytest

    with pytest.raises(ValueError, match="不支持的步骤4生图提示词模板"):
        VideoGenerationConfig(
            input_file="input/book.pdf",
            output_dir="output",
            image_prompt_template="missing-template",
        )
