"""Runs the real OpenAI SDK against a faked HTTP layer (no network, no key)."""

import json

import httpx
import pytest

from privgate.errors import LLMConfigError, LLMError
from privgate.llm import OpenAICompatClient, list_tasks, load_system_prompt, load_task


def completion(content="Hello", finish="stop"):
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }  # fmt: skip


def make(payload, seen=None, status=200, **kwargs):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append((str(request.url), json.loads(request.content)))
        return httpx.Response(status, json=payload)

    return OpenAICompatClient(
        api_key="sk-test", model="some-model", max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs,
    )  # fmt: skip


def test_complete_returns_text_and_sends_messages():
    seen = []
    assert make(completion("  Hi there  "), seen).complete(system="S", user="U") == "Hi there"
    url, body = seen[0]
    assert body["model"] == "some-model" and body["temperature"] == 0.2
    assert body["messages"] == [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]


def test_base_url_and_temperature_options():
    seen = []
    client = make(completion(), seen, base_url="https://example.test/v1/", temperature=None)
    client.complete(system="s", user="u")
    assert seen[0][0].startswith("https://example.test/v1/") and "temperature" not in seen[0][1]


def test_errors_are_wrapped():
    with pytest.raises(LLMError, match="LLM request failed"):
        make({"error": {"message": "bad key", "type": "invalid_request_error"}}, status=401).complete(system="s", user="u")
    with pytest.raises(LLMError, match="empty"):
        make(completion(content="")).complete(system="s", user="u")


def test_missing_key():
    with pytest.raises(LLMConfigError):
        OpenAICompatClient(api_key=None, model="m")


def test_prompt_files_load():
    assert "placeholders" in load_system_prompt()
    assert {"draft_reply", "summarize", "extract_details"} <= set(list_tasks())
    assert load_task("draft_reply").startswith("TASK:")
    with pytest.raises(ValueError):
        load_task("../system_prompt")


# ---------------- Gemini (native) ----------------
def gemini_payload(text="Hello from Gemini"):
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}]}


def make_gemini(payload, seen=None, status=200, **kwargs):
    from privgate.llm import GeminiClient

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append((request, json.loads(request.content) if request.content else {}))
        return httpx.Response(status, json=payload)

    return GeminiClient(api_key="AQ.fake-key", model="gemini-2.5-flash",
                        http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)  # fmt: skip


def test_gemini_complete_sends_key_model_system_prompt_and_user_text():
    seen = []
    assert make_gemini(gemini_payload("  Hi  "), seen).complete(system="SYS", user="USER") == "Hi"
    request, body = seen[0]
    assert "models/gemini-2.5-flash:generateContent" in str(request.url)
    assert request.headers["x-goog-api-key"] == "AQ.fake-key"
    assert body["systemInstruction"]["parts"][0]["text"] == "SYS"
    assert body["contents"][0]["parts"][0]["text"] == "USER"
    assert body["generationConfig"]["temperature"] == 0.2


def test_gemini_errors_are_wrapped():
    with pytest.raises(LLMError, match="Gemini request failed"):
        make_gemini({"error": {"code": 401, "message": "bad key", "status": "UNAUTHENTICATED"}}, status=401).complete(
            system="s", user="u")
    with pytest.raises(LLMError, match="empty"):
        make_gemini({"candidates": []}).complete(system="s", user="u")


def test_gemini_missing_key():
    from privgate.llm import GeminiClient

    with pytest.raises(LLMConfigError):
        GeminiClient(api_key=None, model="m")


def test_build_client_chooses_provider(monkeypatch):
    from privgate.config import AppConfig
    from privgate.llm import GeminiClient, OpenAICompatClient, build_client

    monkeypatch.setenv("GEMINI_API_KEY", "AQ.x")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    cfg = AppConfig()
    cfg.llm.provider = "gemini"
    assert isinstance(build_client(cfg), GeminiClient)
    cfg.llm.provider = "openai"
    assert isinstance(build_client(cfg), OpenAICompatClient)
    cfg.llm.provider = "other"
    with pytest.raises(LLMConfigError, match="Unknown provider"):
        build_client(cfg)


def test_gemini_key_lookup_order(monkeypatch):
    from privgate import config

    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    assert config.get_api_key("gemini") == "openai-key"  # fallback so one pasted key still works
    monkeypatch.setenv("GEMINI_API_KEY", "  gem-key  ")
    assert config.get_api_key("gemini") == "gem-key"
    assert config.get_api_key("openai") == "openai-key"
