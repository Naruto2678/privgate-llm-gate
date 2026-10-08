"""Find personal data in text.

Every detector is deterministic (regular expressions + checksums + context rules), so the
same input always gives the same result and nothing leaves your machine at this stage.

Three switches (see config.yaml) let you see what each idea adds:
* use_checksums     - an Aadhaar must pass Verhoeff, a card must pass Luhn, a PAN must have a valid
                      holder-type letter. This rejects look-alikes such as order or tracking numbers.
* use_context_rules - bank account numbers, PIN codes and names are only recognised next to words
                      like "account no.", "PIN" or "my name is" (a bare 9-18 digit number is ambiguous).
* use_spacy_ner     - optional statistical name detection (see ner.py).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from .config import PrivacyConfig
from .validators import luhn_valid, pan_valid, verhoeff_valid


@dataclass(frozen=True)
class Entity:
    type: str
    start: int
    end: int
    value: str
    detector: str  # "regex", "regex+checksum", "context", "spacy"


Candidate = tuple[int, int, str]  # start, end, detector name

# Lower number wins when two detections overlap (then the longer span wins).
# Context-labelled values ("account no. ...", "PIN ...") win over look-alike number patterns,
# because the words around them tell us what the number really is.
PRIORITY = {
    "BANK_ACCOUNT": 0, "PIN_CODE": 0, "AADHAAR": 1, "CREDIT_CARD": 2, "PAN": 3, "UPI_ID": 4,
    "EMAIL": 5, "IFSC": 6, "PHONE": 7, "PERSON": 10,
}  # fmt: skip

UPI_HANDLES = (
    "okaxis|oksbi|okhdfcbank|okicici|ybl|ibl|axl|paytm|apl|upi|sbi|icici|hdfcbank|axisbank|kotak|"
    "pnb|barodampay|postbank|fbl|yesbank|airtel|jio|freecharge|ikwik|waicici|ptyes|ptsbi|pthdfc|ptaxis"
)

# The extra guards stop a 12-digit slice of a longer, space-separated number (a 16-digit card) from matching.
_AADHAAR = re.compile(r"(?<![\d.])(?<!\d[ -])[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?![ -]?\d)")
_CARD = re.compile(r"(?<![\d.])(?:\d[ -]?){12,18}\d(?!\d)")
_PAN = re.compile(r"(?<![A-Za-z0-9])[A-Z]{5}\d{4}[A-Z](?![A-Za-z0-9])")
_IFSC = re.compile(r"(?<![A-Za-z0-9])[A-Z]{4}0[A-Z0-9]{6}(?![A-Za-z0-9])")
_EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?![\w-])")
_UPI = re.compile(rf"(?<![\w.+-])[A-Za-z0-9._-]{{2,64}}@(?:{UPI_HANDLES})(?![\w-])(?!\.[A-Za-z])")
_PHONE = re.compile(r"(?<![\w+])(?<!\d[ -])(?:(?:\+91|91|0)[ -]?)?[6-9]\d{4}[ -]?\d{5}(?![ -]?\d)")

_BANK_ACCOUNT = re.compile(
    r"(?i:\b(?:a/c|acct?|account)(?:\s*(?:no\.?|number|num\.?|#))?)\s*[:\-#]?\s*(?P<v>\d{9,18})(?!\d)"
)
_PIN_CODE = re.compile(r"(?i:\b(?:pin(?:\s*code)?|pincode|postal\s*code))\s*[:\-]?\s*(?P<v>[1-9]\d{5})(?!\d)")
_NAME = r"[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+){0,2}"  # same line only: never spans a line break
_PERSON_TITLE = re.compile(rf"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Shri|Smt|Sri|Mx)\.?[ \t]+(?P<v>{_NAME})")
_PERSON_INTRO = re.compile(
    rf"(?i:\b(?:my name is|customer name[ \t]*:|name[ \t]*:|i am|i'm))[ \t]+(?P<v>{_NAME})"
)


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _aadhaar(text: str, cfg: PrivacyConfig) -> Iterator[Candidate]:
    for m in _AADHAAR.finditer(text):
        if cfg.use_checksums and not verhoeff_valid(_digits(m.group())):
            continue
        yield m.start(), m.end(), "regex+checksum" if cfg.use_checksums else "regex"


def _card(text: str, cfg: PrivacyConfig) -> Iterator[Candidate]:
    for m in _CARD.finditer(text):
        digits = _digits(m.group())
        if not 13 <= len(digits) <= 19:
            continue
        if cfg.use_checksums and not luhn_valid(digits):
            continue
        yield m.start(), m.end(), "regex+checksum" if cfg.use_checksums else "regex"


def _pan(text: str, cfg: PrivacyConfig) -> Iterator[Candidate]:
    for m in _PAN.finditer(text):
        if cfg.use_checksums and not pan_valid(m.group()):
            continue
        yield m.start(), m.end(), "regex+checksum" if cfg.use_checksums else "regex"


def _simple(pattern: re.Pattern[str]) -> Callable[[str, PrivacyConfig], Iterator[Candidate]]:
    def run(text: str, cfg: PrivacyConfig) -> Iterator[Candidate]:
        for m in pattern.finditer(text):
            yield m.start(), m.end(), "regex"

    return run


def _contextual(*patterns: re.Pattern[str]) -> Callable[[str, PrivacyConfig], Iterator[Candidate]]:
    def run(text: str, cfg: PrivacyConfig) -> Iterator[Candidate]:
        if not cfg.use_context_rules:
            return
        for pattern in patterns:
            for m in pattern.finditer(text):
                yield m.start("v"), m.end("v"), "context"

    return run


DETECTORS: dict[str, Callable[[str, PrivacyConfig], Iterator[Candidate]]] = {
    "AADHAAR": _aadhaar,
    "CREDIT_CARD": _card,
    "PAN": _pan,
    "UPI_ID": _simple(_UPI),
    "EMAIL": _simple(_EMAIL),
    "IFSC": _simple(_IFSC),
    "PHONE": _simple(_PHONE),
    "BANK_ACCOUNT": _contextual(_BANK_ACCOUNT),
    "PIN_CODE": _contextual(_PIN_CODE),
    "PERSON": _contextual(_PERSON_TITLE, _PERSON_INTRO),
}


def find_entities(text: str, cfg: PrivacyConfig, ner: Callable[[str], list[tuple[int, int]]] | None = None) -> list[Entity]:
    """Return non-overlapping entities sorted by position."""
    wanted = set(cfg.detect)
    candidates: list[Entity] = []
    for etype, detector in DETECTORS.items():
        if etype not in wanted:
            continue
        for start, end, how in detector(text, cfg):
            candidates.append(Entity(etype, start, end, text[start:end], how))
    if cfg.use_spacy_ner and ner is not None and "PERSON" in wanted:
        for start, end in ner(text):
            candidates.append(Entity("PERSON", start, end, text[start:end], "spacy"))

    # Resolve overlaps: best priority first, then longest, then earliest.
    candidates.sort(key=lambda e: (PRIORITY[e.type], -(e.end - e.start), e.start))
    chosen: list[Entity] = []
    for cand in candidates:
        if all(cand.end <= c.start or cand.start >= c.end for c in chosen):
            chosen.append(cand)
    chosen = _link_name_mentions(text, chosen)
    return sorted(chosen, key=lambda e: e.start)


def _link_name_mentions(text: str, chosen: list[Entity]) -> list[Entity]:
    """If "Priya Nair" was found, also catch later mentions of just "Priya" or "Nair".

    Without this the signature line of an email would leak the first name.
    """
    full_names: set[str] = set()
    parts: set[str] = set()
    for e in chosen:
        if e.type == "PERSON":
            full_names.add(e.value)
            parts.update(t for t in re.findall(r"[A-Za-z]+", e.value) if len(t) >= 3)
    if not parts:
        return chosen
    extra: list[Entity] = []
    # full names first (longest first), then single name parts, so "Priya Nair" stays one entity
    for needle in [*sorted(full_names, key=len, reverse=True), *sorted(parts)]:
        for m in re.finditer(rf"(?<![A-Za-z]){re.escape(needle)}(?![A-Za-z])", text):
            if all(m.end() <= c.start or m.start() >= c.end for c in [*chosen, *extra]):
                extra.append(Entity("PERSON", m.start(), m.end(), m.group(), "name-link"))
    return [*chosen, *extra]
