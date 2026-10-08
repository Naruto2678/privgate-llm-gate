"""The gateway: detect -> redact -> verify clean -> call LLM -> restore -> audit."""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .config import AppConfig
from .detectors import find_entities
from .errors import InputTooLongError
from .llm import ChatClient, load_system_prompt, load_task
from .ner import person_spans
from .redactor import Redaction, assert_clean, mask, redact, restore
from .schemas import ChatResponse, EntityOut, RedactResponse

log = logging.getLogger(__name__)


class Gateway:
    def __init__(self, cfg: AppConfig, llm: ChatClient | None = None) -> None:
        self.cfg = cfg
        self.llm = llm

    # ---- step 1-3: no LLM involved ----
    def sanitize(self, text: str) -> Redaction:
        if len(text) > self.cfg.limits.max_input_chars:
            raise InputTooLongError(f"Input is longer than {self.cfg.limits.max_input_chars} characters.")
        ner = person_spans if self.cfg.privacy.use_spacy_ner else None
        result = redact(text, find_entities(text, self.cfg.privacy, ner))
        if self.cfg.privacy.fail_closed:
            assert_clean(result.redacted_text, result.vault)
        return result

    @staticmethod
    def _entities_out(red: Redaction, include_values: bool) -> list[EntityOut]:
        return [
            EntityOut(
                type=e.type, placeholder=ph, start=e.start, end=e.end, detector=e.detector,
                masked_value=mask(e.value), value=e.value if include_values else None,
            )
            for e, ph in red.entities
        ]  # fmt: skip

    def redact_only(self, text: str, include_values: bool = False) -> RedactResponse:
        red = self.sanitize(text)
        return RedactResponse(
            redacted_text=red.redacted_text,
            entities=self._entities_out(red, include_values),
            counts=dict(Counter(e.type for e, _ in red.entities)),
        )

    # ---- full flow ----
    def run(self, task: str, text: str, include_values: bool = False) -> ChatResponse:
        if self.llm is None:
            raise RuntimeError("No LLM client configured.")
        instruction = load_task(task)
        red = self.sanitize(text)
        user_message = f"{instruction}\n\n--- MESSAGE ---\n{red.redacted_text}"
        reply_redacted = self.llm.complete(system=load_system_prompt(), user=user_message)

        warnings: list[str] = []
        reply, unknown = restore(reply_redacted, red.vault) if self.cfg.privacy.restore_in_reply else (reply_redacted, [])
        warnings += [f"The model used a placeholder that does not exist: {p}" for p in unknown]

        # Did the model invent personal data of its own?
        known = set(red.vault.values())
        for e in find_entities(reply_redacted, self.cfg.privacy):
            if e.value not in known:
                warnings.append(f"The model's answer contains a {e.type}-like value that was not in your input.")

        counts = dict(Counter(e.type for e, _ in red.entities))
        self._audit(task, counts, len(warnings))
        return ChatResponse(
            task=task,
            model=self.llm.model,
            redacted_input=red.redacted_text,
            reply_redacted=reply_redacted,
            reply=reply,
            entities=self._entities_out(red, include_values),
            counts=counts,
            warnings=warnings,
        )

    def _audit(self, task: str, counts: dict[str, int], n_warnings: int) -> None:
        """Append one line of COUNTS ONLY (never text or values) so usage can be reviewed safely."""
        path = self.cfg.privacy.audit_log_path
        if not path:
            return
        record = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "task": task,
            "entities_redacted": counts,
            "warnings": n_warnings,
        }
        try:
            with Path(path).open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError as exc:  # logging must never break the request
            log.warning("Could not write audit log: %s", exc)
