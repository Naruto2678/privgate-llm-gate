"""Optional name detection with spaCy (statistical NER).

Install it with:   pip install spacy && python -m spacy download en_core_web_sm
then set  use_spacy_ner: true  in config.yaml. If spaCy is missing, PrivGate keeps working
with the rule-based detectors and tells you so.
"""

from __future__ import annotations

import logging
from functools import lru_cache

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load():
    try:
        import spacy

        return spacy.load("en_core_web_sm")
    except Exception as exc:  # ImportError or missing model
        log.info("spaCy name detection unavailable (%s). Using rule-based detectors only.", exc)
        return None


def spacy_available() -> bool:
    return _load() is not None


def person_spans(text: str) -> list[tuple[int, int]]:
    nlp = _load()
    if nlp is None:
        return []
    return [(e.start_char, e.end_char) for e in nlp(text).ents if e.label_ == "PERSON"]
