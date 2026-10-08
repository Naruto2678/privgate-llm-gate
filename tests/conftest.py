from __future__ import annotations

import pytest

from privgate.config import AppConfig
from privgate.validators import luhn_check_digit, verhoeff_check_digit


class FakeChat:
    """Stands in for the real LLM: records what it was sent and returns a canned reply."""

    model = "fake-model"

    def __init__(self, reply="Thanks."):
        self.reply = reply
        self.sent: list[tuple[str, str]] = []

    def complete(self, *, system: str, user: str) -> str:
        self.sent.append((system, user))
        return self.reply(user) if callable(self.reply) else self.reply


def make_aadhaar(body11: str = "23456789012") -> str:
    n = body11 + verhoeff_check_digit(body11)
    return f"{n[:4]} {n[4:8]} {n[8:]}"


def make_card(body15: str = "411111111111111") -> str:
    n = body15 + luhn_check_digit(body15)
    return f"{n[:4]} {n[4:8]} {n[8:12]} {n[12:]}"


@pytest.fixture
def cfg() -> AppConfig:
    return AppConfig()  # defaults: all detectors on, no audit log
