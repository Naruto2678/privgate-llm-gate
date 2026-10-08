"""FastAPI service. Run with:  uvicorn privgate.main:app --reload"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException

from . import __version__
from .config import AppConfig, load_config
from .errors import InputTooLongError, LLMConfigError, LLMError, PrivacyLeakError
from .gateway import Gateway
from .llm import ChatClient, build_client, list_tasks
from .schemas import ChatRequest, ChatResponse, RedactRequest, RedactResponse

app = FastAPI(
    title="PrivGate - PII redaction gateway for LLMs",
    version=__version__,
    description="Detects Indian personal data, redacts it before the LLM call, and restores it in the answer.",
)


@lru_cache
def get_config() -> AppConfig:
    return load_config()


def get_llm(cfg: AppConfig = Depends(get_config)) -> ChatClient:
    try:
        return build_client(cfg)
    except LLMConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/v1/tasks")
def tasks() -> list[str]:
    return list_tasks()


@app.post("/v1/redact", response_model=RedactResponse)
def redact_endpoint(req: RedactRequest, cfg: AppConfig = Depends(get_config)) -> RedactResponse:
    try:
        return Gateway(cfg).redact_only(req.text, req.include_values)
    except InputTooLongError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc


@app.post("/v1/chat", response_model=ChatResponse)
def chat_endpoint(
    req: ChatRequest, cfg: AppConfig = Depends(get_config), llm: ChatClient = Depends(get_llm)
) -> ChatResponse:
    try:
        return Gateway(cfg, llm).run(req.task, req.text, req.include_values)
    except InputTooLongError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:  # unknown task
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrivacyLeakError as exc:
        raise HTTPException(status_code=500, detail=f"Request blocked (fail-closed): {exc}") from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
