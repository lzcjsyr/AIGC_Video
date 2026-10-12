import pytest


def test_image_provider_registry_only_keeps_doubao_and_google_variants():
    from core.config import Config
    from core.infra.ai import image_client

    assert Config.SUPPORTED_IMAGE_SERVERS == ["doubao", "google", "google_adc"]
    assert sorted(image_client.IMAGE_PROVIDERS) == ["doubao", "google", "google_adc"]
    assert "siliconflow" not in Config.RECOMMENDED_MODELS["image"]


def test_request_image_result_uses_registered_provider(monkeypatch):
    from core.infra.ai import image_client

    captured = {}

    class FakeProvider:
        def generate(self, *, prompt, size, model):
            captured.update(prompt=prompt, size=size, model=model)
            return {"type": "bytes", "data": b"png"}

    monkeypatch.setitem(image_client.IMAGE_PROVIDERS, "google", FakeProvider())

    result = image_client._request_image_result(
        "google",
        "prompt",
        "1024x1024",
        "gemini-3.1-flash-image",
    )

    assert result == {"type": "bytes", "data": b"png"}
    assert captured == {
        "prompt": "prompt",
        "size": "1024x1024",
        "model": "gemini-3.1-flash-image",
    }


def test_siliconflow_image_provider_is_rejected():
    from core.infra.ai import image_client

    with pytest.raises(ValueError, match="不支持的图像服务商: siliconflow"):
        image_client._request_image_result(
            "siliconflow",
            "prompt",
            "1024x1024",
            "black-forest-labs/FLUX.1-schnell",
        )
