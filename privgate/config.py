"""Load config.yaml (settings) and .env (secrets) into typed objects."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
ALL_TYPES = [
    "AADHAAR", "PAN", "PHONE", "EMAIL", "UPI_ID", "IFSC", "CREDIT_CARD", "BANK_ACCOUNT", "PIN_CODE", "PERSON",
]  # fmt: skip


class LLMConfig(BaseModel):
    provider: str = "openai"  # "openai" (any OpenAI-compatible API) or "gemini" (Google native API)
    model: str = "gpt-4o-mini"
    base_url: str | None = None
    temperature: float | None = 0.2
    timeout_seconds: float = 60.0
    max_retries: int = 3


class PrivacyConfig(BaseModel):
    detect: list[str] = Field(default_factory=lambda: list(ALL_TYPES))
    use_checksums: bool = True
    use_context_rules: bool = True
    use_spacy_ner: bool = False
    restore_in_reply: bool = True
    fail_closed: bool = True
    audit_log_path: str | None = None


class Limits(BaseModel):
    max_input_chars: int = 20_000


class AppConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    limits: Limits = Field(default_factory=Limits)


def load_config(path: str | Path | None = None) -> AppConfig:
    """Read config.yaml, then apply LLM_PROVIDER / LLM_MODEL (or OPENAI_MODEL) / OPENAI_BASE_URL overrides from the environment."""
    load_dotenv(ROOT / ".env")
    path = Path(path or os.getenv("PRIVGATE_CONFIG") or ROOT / "config.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    cfg = AppConfig.model_validate(data or {})
    if os.getenv("LLM_PROVIDER"):
        cfg.llm.provider = os.environ["LLM_PROVIDER"].strip().lower()
    model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL")
    if model:
        cfg.llm.model = model
    if os.getenv("OPENAI_BASE_URL"):
        cfg.llm.base_url = os.environ["OPENAI_BASE_URL"]
    return cfg


def get_api_key(provider: str = "openai") -> str | None:
    """Read the key from the environment / .env. Gemini users may use GEMINI_API_KEY."""
    load_dotenv(ROOT / ".env")
    names = ["GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"] if provider == "gemini" else ["OPENAI_API_KEY"]
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return None
