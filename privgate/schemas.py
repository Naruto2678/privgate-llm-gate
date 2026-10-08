"""Data contracts for the API and the UI."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntityOut(BaseModel):
    type: str
    placeholder: str
    start: int
    end: int
    detector: str
    masked_value: str = Field(description="Display-safe masked version of the value.")
    value: str | None = Field(default=None, description="Only present when include_values is requested.")


class RedactRequest(BaseModel):
    text: str = Field(min_length=1)
    include_values: bool = False


class RedactResponse(BaseModel):
    redacted_text: str
    entities: list[EntityOut]
    counts: dict[str, int]


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, description="The message that may contain personal data.")
    task: str = Field(default="draft_reply", description="One of the files in prompts/tasks (without .txt).")
    include_values: bool = False

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Hi, I am Priya Nair. My order 482913075521 never arrived. Call me on +91 98765 43210.",
                "task": "draft_reply",
            }
        }
    }


class ChatResponse(BaseModel):
    task: str
    model: str
    redacted_input: str = Field(description="Exactly what was sent to the LLM.")
    reply_redacted: str = Field(description="The LLM's answer as received (still contains placeholders).")
    reply: str = Field(description="The answer with real values restored (if enabled).")
    entities: list[EntityOut]
    counts: dict[str, int]
    warnings: list[str]
