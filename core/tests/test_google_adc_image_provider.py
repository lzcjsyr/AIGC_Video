import sys
import types as module_types


def test_config_accepts_google_adc_without_google_api_key(monkeypatch):
    from core.config import Config

    monkeypatch.setattr(Config, "GOOGLE_CLOUD_API_KEY", "", raising=False)

    assert "google_adc" in Config.SUPPORTED_IMAGE_SERVERS
    Config.validate_model_provider_pair(
        "image",
        "google_adc",
        "gemini-3.1-flash-image",
    )


def test_google_adc_provider_uses_google_generator_with_adc(monkeypatch):
    from core.infra.ai import image_providers

    captured = {}

    def fake_google(prompt, size, model, use_adc=False):
        captured.update(prompt=prompt, size=size, model=model, use_adc=use_adc)
        return {"type": "bytes", "data": b"png"}

    monkeypatch.setattr(image_providers, "text_to_image_google", fake_google)

    result = image_providers.GoogleImageProvider(use_adc=True).generate(
        prompt="prompt",
        size="1024x1024",
        model="gemini-3.1-flash-image",
    )

    assert result == {"type": "bytes", "data": b"png"}
    assert captured == {
        "prompt": "prompt",
        "size": "1024x1024",
        "model": "gemini-3.1-flash-image",
        "use_adc": True,
    }


def test_text_to_image_google_adc_uses_project_and_location(monkeypatch):
    from core.infra.ai import llm_client

    captured = {}

    class FakePart:
        @staticmethod
        def from_text(text):
            return {"text": text}

    class FakeContent:
        def __init__(self, role, parts):
            self.role = role
            self.parts = parts

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeImageConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeSafetySetting:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeThinkingConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["request"] = kwargs
            inline = module_types.SimpleNamespace(data=b"image-bytes")
            part = module_types.SimpleNamespace(inline_data=inline)
            content = module_types.SimpleNamespace(parts=[part])
            candidate = module_types.SimpleNamespace(content=content)
            return module_types.SimpleNamespace(candidates=[candidate])

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.models = FakeModels()

    fake_types = module_types.SimpleNamespace(
        Content=FakeContent,
        Part=FakePart,
        GenerateContentConfig=FakeGenerateContentConfig,
        ImageConfig=FakeImageConfig,
        SafetySetting=FakeSafetySetting,
        ThinkingConfig=FakeThinkingConfig,
    )
    fake_genai = module_types.SimpleNamespace(Client=FakeClient, types=fake_types)
    fake_google = module_types.SimpleNamespace(genai=fake_genai)

    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setattr(llm_client.config, "GOOGLE_CLOUD_API_KEY", "", raising=False)
    monkeypatch.setattr(llm_client.config, "GOOGLE_CLOUD_PROJECT", "test-project", raising=False)
    monkeypatch.setattr(llm_client.config, "GOOGLE_CLOUD_LOCATION", "global", raising=False)

    result = llm_client.text_to_image_google(
        "prompt",
        size="1024x1024",
        model="gemini-3.1-flash-image",
        use_adc=True,
    )

    assert result == {"type": "bytes", "data": b"image-bytes"}
    assert captured["client"] == {
        "vertexai": True,
        "project": "test-project",
        "location": "global",
    }
