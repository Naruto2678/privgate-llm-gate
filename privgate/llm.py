"""OpenAI-compatible chat client plus prompt-file loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .config import ROOT, AppConfig, get_api_key
from .errors import LLMConfigError, LLMError

PROMPTS_DIR = ROOT / "prompts"


class ChatClient(Protocol):
    model: str

    def complete(self, *, system: str, user: str) -> str: ...


class OpenAICompatClient:
    """Works with OpenAI and any OpenAI-compatible provider (Gemini, Ollama...) via base_url."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str | None = None,
        temperature: float | None = 0.2,
        timeout: float = 60.0,
        max_retries: int = 3,
        http_client: Any = None,  # injectable for offline tests
    ) -> None:
        if not api_key:
            raise LLMConfigError("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")
        from openai import OpenAI

        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout, "max_retries": max_retries}
        if base_url:
            kwargs["base_url"] = base_url
        if http_client is not None:
            kwargs["http_client"] = http_client
        self._client = OpenAI(**kwargs)
        self.model = model
        self.temperature = temperature

    def complete(self, *, system: str, user: str) -> str:
        from openai import OpenAIError

        params: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if self.temperature is not None:
            params["temperature"] = self.temperature
        try:
            completion = self._client.chat.completions.create(**params)
        except OpenAIError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        content = completion.choices[0].message.content
        if not content:
            raise LLMError("The model returned an empty answer.")
        return content.strip()


class GeminiClient:
    """Google's native Gemini API (google-genai SDK). Use this for the new "AQ." style AI Studio keys."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        temperature: float | None = 0.2,
        timeout: float = 60.0,
        http_client: Any = None,  # injectable for offline tests
    ) -> None:
        if not api_key:
            raise LLMConfigError("No Gemini key found. Set GEMINI_API_KEY in .env (see .env.example).")
        from google import genai
        from google.genai import types

        options: dict[str, Any] = {"timeout": int(timeout * 1000)}  # the SDK expects milliseconds
        if http_client is not None:
            options["httpx_client"] = http_client
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(**options))
        self.model = model
        self.temperature = temperature

    def complete(self, *, system: str, user: str) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),  # we use no tools
        )
        try:
            response = self._client.models.generate_content(model=self.model, contents=user, config=config)
            text = response.text
        except Exception as exc:  # the SDK raises several error types (API errors, network errors...)
            raise LLMError(f"Gemini request failed: {exc}") from exc
        if not text:
            raise LLMError("Gemini returned an empty answer (it may have been blocked by a safety filter).")
        return text.strip()


def build_client(cfg: AppConfig) -> ChatClient:
    provider = cfg.llm.provider
    if provider == "gemini":
        return GeminiClient(
            api_key=get_api_key("gemini"),
            model=cfg.llm.model,
            temperature=cfg.llm.temperature,
            timeout=cfg.llm.timeout_seconds,
        )
    if provider != "openai":
        raise LLMConfigError(f"Unknown provider '{provider}'. Use 'openai' or 'gemini' in config.yaml.")
    return OpenAICompatClient(
        api_key=get_api_key("openai"),
        model=cfg.llm.model,
        base_url=cfg.llm.base_url,
        temperature=cfg.llm.temperature,
        timeout=cfg.llm.timeout_seconds,
        max_retries=cfg.llm.max_retries,
    )


def load_system_prompt(prompts_dir: Path = PROMPTS_DIR) -> str:
    return (prompts_dir / "system_prompt.txt").read_text(encoding="utf-8").strip()


def list_tasks(prompts_dir: Path = PROMPTS_DIR) -> list[str]:
    return sorted(p.stem for p in (prompts_dir / "tasks").glob("*.txt"))


def load_task(task: str, prompts_dir: Path = PROMPTS_DIR) -> str:
    path = prompts_dir / "tasks" / f"{task}.txt"
    if not path.exists() or task not in list_tasks(prompts_dir):  # also blocks path tricks like ../
        raise ValueError(f"Unknown task '{task}'. Available: {', '.join(list_tasks(prompts_dir))}")
    return path.read_text(encoding="utf-8").strip()
