import pytest
from fastapi.testclient import TestClient

from privgate.config import AppConfig
from privgate.main import app, get_config, get_llm
from tests.conftest import FakeChat

BODY = {"text": "Hi, I am Priya Nair. Call me on 9876543210.", "task": "draft_reply"}


@pytest.fixture(autouse=True)
def _clean():
    yield
    app.dependency_overrides.clear()


def client(llm=None, cfg=None):
    app.dependency_overrides[get_config] = lambda: cfg or AppConfig()
    if llm is not None:
        app.dependency_overrides[get_llm] = lambda: llm
    return TestClient(app)


def test_health_and_tasks():
    c = client()
    assert c.get("/health").json()["status"] == "ok"
    assert {"draft_reply", "summarize", "extract_details"} <= set(c.get("/v1/tasks").json())


def test_redact_endpoint_hides_values():
    r = client().post("/v1/redact", json={"text": "Call 9876543210"})
    data = r.json()
    assert r.status_code == 200 and data["redacted_text"] == "Call [PHONE_1]"
    assert data["entities"][0]["value"] is None


def test_chat_endpoint_roundtrip():
    llm = FakeChat("Dear [PERSON_1], we will call [PHONE_1].")
    r = client(llm).post("/v1/chat", json=BODY)
    assert r.status_code == 200
    assert r.json()["reply"] == "Dear Priya Nair, we will call 9876543210."
    assert "Priya" not in llm.sent[0][1]


def test_missing_api_key_is_503(monkeypatch):
    monkeypatch.setattr("privgate.llm.get_api_key", lambda *args, **kwargs: None)
    r = client().post("/v1/chat", json=BODY)
    assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]


def test_unknown_task_422_and_empty_text_422_and_too_long_413():
    c = client(FakeChat())
    assert c.post("/v1/chat", json={**BODY, "task": "nope"}).status_code == 422
    assert c.post("/v1/chat", json={"text": "", "task": "summarize"}).status_code == 422
    small = AppConfig()
    small.limits.max_input_chars = 10
    assert client(FakeChat(), small).post("/v1/chat", json=BODY).status_code == 413


def test_llm_failure_is_502():
    from privgate.errors import LLMError

    class Boom(FakeChat):
        def complete(self, **kwargs):
            raise LLMError("upstream exploded")

    r = client(Boom()).post("/v1/chat", json=BODY)
    assert r.status_code == 502 and "upstream exploded" in r.json()["detail"]
