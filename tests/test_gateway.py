import json

import pytest

from privgate.config import AppConfig
from privgate.errors import InputTooLongError, PrivacyLeakError
from privgate.gateway import Gateway
from privgate.redactor import Redaction
from tests.conftest import FakeChat, make_aadhaar

TEXT = "Hi, I am Priya Nair. My order 482913075521 is late. Call +91 98765 43210 or priya@gmail.com."


def reply_with_placeholders(user: str) -> str:
    return "Dear [PERSON_1], we will call you on [PHONE_1] about your order."


def test_llm_never_sees_original_values_and_reply_is_restored(cfg):
    llm = FakeChat(reply_with_placeholders)
    result = Gateway(cfg, llm).run("draft_reply", TEXT)
    system, user = llm.sent[0]
    for secret in ("Priya", "Nair", "98765", "priya@gmail.com"):
        assert secret not in user and secret not in system
    assert "482913075521" in user  # the order ID is not personal data
    assert "[PERSON_1]" in user and "[PHONE_1]" in user
    assert result.reply == "Dear Priya Nair, we will call you on +91 98765 43210 about your order."
    assert result.reply_redacted.startswith("Dear [PERSON_1]")
    assert result.warnings == []
    assert result.counts == {"PERSON": 1, "PHONE": 1, "EMAIL": 1}


def test_task_instruction_and_system_prompt_come_from_files(cfg):
    llm = FakeChat()
    Gateway(cfg, llm).run("summarize", TEXT)
    system, user = llm.sent[0]
    assert "placeholders" in system and "TASK: Summarize" in user


def test_unknown_placeholder_and_invented_pii_produce_warnings(cfg):
    llm = FakeChat("Call [PERSON_7] on 9123456780 or write to boss@corp.com")
    result = Gateway(cfg, llm).run("draft_reply", TEXT)
    messages = " ".join(result.warnings)
    assert "[PERSON_7]" in messages and "PHONE-like" in messages and "EMAIL-like" in messages


def test_restore_can_be_disabled(cfg):
    cfg.privacy.restore_in_reply = False
    result = Gateway(cfg, FakeChat(reply_with_placeholders)).run("draft_reply", TEXT)
    assert result.reply == result.reply_redacted


def test_fail_closed_blocks_the_call_if_a_value_would_leak(cfg, monkeypatch):
    llm = FakeChat()
    leaky = Redaction(redacted_text="call 9876543210", entities=[], vault={"[PHONE_1]": "9876543210"})
    monkeypatch.setattr("privgate.gateway.redact", lambda text, entities: leaky)
    with pytest.raises(PrivacyLeakError):
        Gateway(cfg, llm).run("draft_reply", "call 9876543210")
    assert llm.sent == []  # nothing was sent


def test_fail_closed_can_be_turned_off(cfg, monkeypatch):
    cfg.privacy.fail_closed = False
    leaky = Redaction(redacted_text="call 9876543210", entities=[], vault={"[PHONE_1]": "9876543210"})
    monkeypatch.setattr("privgate.gateway.redact", lambda text, entities: leaky)
    assert Gateway(cfg, FakeChat()).run("draft_reply", "x").reply == "Thanks."


def test_input_limit(cfg):
    cfg.limits.max_input_chars = 20
    with pytest.raises(InputTooLongError):
        Gateway(cfg, FakeChat()).run("draft_reply", "x" * 21)


def test_unknown_or_malicious_task_name(cfg):
    for bad in ("nope", "../system_prompt", "..\\x"):
        with pytest.raises(ValueError, match="Unknown task"):
            Gateway(cfg, FakeChat()).run(bad, TEXT)


def test_audit_log_has_counts_only(cfg, tmp_path):
    cfg.privacy.audit_log_path = str(tmp_path / "audit.jsonl")
    Gateway(cfg, FakeChat(reply_with_placeholders)).run("draft_reply", TEXT)
    raw = (tmp_path / "audit.jsonl").read_text()
    record = json.loads(raw.splitlines()[0])
    assert record["entities_redacted"] == {"PERSON": 1, "PHONE": 1, "EMAIL": 1} and record["task"] == "draft_reply"
    for secret in ("Priya", "98765", "gmail", "482913075521", "late"):
        assert secret not in raw


def test_redact_only_needs_no_llm_and_hides_values_by_default(cfg):
    out = Gateway(cfg).redact_only(f"Aadhaar {make_aadhaar()}")
    assert out.counts == {"AADHAAR": 1} and out.entities[0].value is None
    assert "*" in out.entities[0].masked_value
    shown = Gateway(cfg).redact_only(f"Aadhaar {make_aadhaar()}", include_values=True)
    assert shown.entities[0].value == make_aadhaar()


def test_run_without_llm_raises(cfg):
    with pytest.raises(RuntimeError):
        Gateway(cfg).run("draft_reply", TEXT)


def test_defaults_roundtrip():
    assert AppConfig().privacy.use_checksums is True
