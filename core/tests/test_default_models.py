import re
from pathlib import Path

import yaml

EXAMPLE = yaml.safe_load((Path(__file__).resolve().parents[2] / "config.example.yaml").read_text(encoding="utf-8"))


def test_volcengine_defaults_use_pay_as_you_go_model_ids():
    """Ark's pay-as-you-go endpoints only accept dated IDs; doubao-seed-2.0-pro is a Coding Plan name (404 here)."""
    for section, values in EXAMPLE.items():
        if isinstance(values, dict) and values.get("llm_server") == "volcengine":
            assert re.search(r"-\d{6}$", values["llm_model"]), f"{section}.llm_model={values['llm_model']}"


def test_default_voice_is_set():
    """The desktop app has no .env; an empty voice cannot be synthesised."""
    assert EXAMPLE["step3"]["voice"]


def test_tts_resource_follows_the_voice():
    from core.infra.ai.tts_client import resource_for_voice

    assert resource_for_voice("S_abc12345", "seed-tts-2.0") == "seed-icl-2.0"
    assert resource_for_voice("S_abc12345", "seed-icl-1.0") == "seed-icl-1.0"
    assert resource_for_voice("zh_female_vv_uranus_bigtts", "seed-icl-2.0") == "seed-tts-2.0"
    assert resource_for_voice("zh_male_yuanboxiaoshu_moon_bigtts", "seed-tts-2.0") == "seed-tts-1.0"
    assert resource_for_voice("custom_voice", "seed-tts-2.0") == "seed-tts-2.0"


def test_empty_voice_fails_at_once(monkeypatch):
    import pytest
    from core.infra.ai import tts_client
    from core.shared import APIError

    monkeypatch.setattr(tts_client.config, "BYTEDANCE_TTS_API_KEY", "key", raising=False)
    monkeypatch.setattr(tts_client, "_request_bytedance_tts_pcm", lambda **kw: pytest.fail("no request without a voice"))
    with pytest.raises(APIError, match="音色") as raised:
        tts_client.text_to_audio_bytedance("文本", "/tmp/never.wav", voice="")
    assert raised.value.retryable is False
