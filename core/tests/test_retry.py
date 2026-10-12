import sys
import types as module_types

import pytest

from core.shared import APIError, http_status, is_retryable, retry_on_failure


class StatusError(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


@pytest.fixture
def waits(monkeypatch):
    recorded = []
    monkeypatch.setattr("core.shared.time.sleep", recorded.append)
    monkeypatch.setattr("core.shared.random.uniform", lambda a, b: 1.0)
    return recorded


def flaky(errors, result="ok"):
    """A function that raises the given errors in order, then returns result."""
    calls = []

    def call():
        calls.append(1)
        if len(calls) <= len(errors):
            raise errors[len(calls) - 1]
        return result

    return call, calls


def test_rate_limit_is_retried_five_times_with_growing_waits(waits):
    call, calls = flaky([StatusError(429)] * 5)
    assert retry_on_failure(max_retries=5, delay=5.0)(call)() == "ok"
    assert len(calls) == 6
    assert waits == [5.0, 10.0, 20.0, 40.0, 60.0]


def test_rate_limit_gives_up_after_the_last_retry(waits):
    call, calls = flaky([StatusError(429)] * 6)
    with pytest.raises(StatusError):
        retry_on_failure(max_retries=5, delay=5.0)(call)()
    assert len(calls) == 6


@pytest.mark.parametrize("error", [StatusError(404), StatusError(401), StatusError(400),
                                   APIError("KEY未配置", retryable=False)])
def test_permanent_errors_fail_at_once(waits, error):
    call, calls = flaky([error])
    with pytest.raises(type(error)):
        retry_on_failure(max_retries=5, delay=5.0)(call)()
    assert len(calls) == 1 and waits == []


def test_status_is_found_through_wrapping_errors():
    try:
        try:
            raise StatusError(404)
        except StatusError as inner:
            raise APIError("wrapped") from inner
    except APIError as outer:
        assert http_status(outer) == 404
        assert not is_retryable(outer)
    assert is_retryable(StatusError(503)) and is_retryable(ConnectionError("reset"))


def test_google_genai_errors_carry_their_status():
    errors = pytest.importorskip("google.genai.errors")
    not_found = errors.ClientError(404, {"error": {"code": 404, "message": "not found", "status": "NOT_FOUND"}})
    limited = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    assert not is_retryable(not_found) and is_retryable(limited)


def install_fake_genai(monkeypatch, outcomes):
    """Fake google.genai whose generate_content raises or returns each outcome in turn."""
    captured = {"calls": 0}

    class Anything:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        @staticmethod
        def from_text(text):
            return {"text": text}

    class Models:
        def generate_content(self, **kwargs):
            outcome = outcomes[min(captured["calls"], len(outcomes) - 1)]
            captured["calls"] += 1
            if isinstance(outcome, BaseException):
                raise outcome
            inline = module_types.SimpleNamespace(data=outcome)
            part = module_types.SimpleNamespace(inline_data=inline)
            content = module_types.SimpleNamespace(parts=[part])
            return module_types.SimpleNamespace(candidates=[module_types.SimpleNamespace(content=content)])

    class Client:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.models = Models()

    fake_types = module_types.SimpleNamespace(Content=Anything, Part=Anything, GenerateContentConfig=Anything,
                                              ImageConfig=Anything, SafetySetting=Anything, ThinkingConfig=Anything)
    fake_genai = module_types.SimpleNamespace(Client=Client, types=fake_types)
    monkeypatch.setitem(sys.modules, "google", module_types.SimpleNamespace(genai=fake_genai))
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    return captured


@pytest.fixture
def adc_project(monkeypatch):
    from core.infra.ai import llm_client

    monkeypatch.setattr(llm_client.config, "GOOGLE_CLOUD_PROJECT", "test-project", raising=False)
    monkeypatch.setattr(llm_client.config, "GOOGLE_CLOUD_LOCATION", "global", raising=False)
    return llm_client


def test_google_adc_cover_survives_rate_limits(waits, monkeypatch, adc_project):
    captured = install_fake_genai(monkeypatch, [StatusError(429)] * 5 + [b"png"])
    result = adc_project.text_to_image_google("prompt", size="2500x2500", use_adc=True)
    assert result == {"type": "bytes", "data": b"png"}
    assert captured["calls"] == 6 and len(waits) == 5


def test_google_adc_missing_model_is_reported_once_and_clearly(waits, monkeypatch, adc_project):
    captured = install_fake_genai(monkeypatch, [StatusError(404)])
    with pytest.raises(APIError) as raised:
        adc_project.text_to_image_google("prompt", model="gemini-retired-image", use_adc=True)
    assert captured["calls"] == 1 and waits == []
    message = str(raised.value)
    assert "gemini-retired-image" in message and "test-project" in message and "404" in message


def test_google_adc_without_project_fails_without_retrying(waits, monkeypatch, adc_project):
    install_fake_genai(monkeypatch, [b"png"])
    monkeypatch.setattr(adc_project, "_resolve_google_adc_project", lambda: None)
    with pytest.raises(APIError, match="ADC"):
        adc_project.text_to_image_google("prompt", use_adc=True)
    assert waits == []


def test_adc_project_falls_back_to_the_login_quota_project(monkeypatch):
    """Without the gcloud command on PATH (the desktop app), google.auth reports no project."""
    from core.infra.ai import llm_client

    credentials = module_types.SimpleNamespace(quota_project_id="quota-project")
    fake_auth = module_types.SimpleNamespace(default=lambda scopes: (credentials, None))
    monkeypatch.setitem(sys.modules, "google", module_types.SimpleNamespace(auth=fake_auth))
    monkeypatch.setitem(sys.modules, "google.auth", fake_auth)
    monkeypatch.setattr(llm_client.config, "GOOGLE_CLOUD_PROJECT", "", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_PROJECT_ID", raising=False)
    assert llm_client._resolve_google_adc_project() == "quota-project"


def test_default_cover_model_is_generally_available():
    from pathlib import Path
    import yaml

    example = yaml.safe_load((Path(__file__).resolve().parents[2] / "config.example.yaml").read_text(encoding="utf-8"))
    assert not example["step6"]["cover_image_model"].endswith("-preview")
