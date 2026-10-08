"""Replace detected values with placeholders and put them back later.

The "vault" (placeholder -> original value) lives only in memory for the duration of one request.
It is never written to disk or sent to the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .detectors import Entity
from .errors import PrivacyLeakError

_PLACEHOLDER = re.compile(r"\[\s*([A-Z_]+_\d+)\s*\]")
_NUMERIC_TYPES = {"AADHAAR", "PHONE", "CREDIT_CARD", "BANK_ACCOUNT", "PIN_CODE"}


@dataclass
class Redaction:
    redacted_text: str
    entities: list[tuple[Entity, str]]  # (entity, placeholder) in text order
    vault: dict[str, str] = field(default_factory=dict)  # placeholder -> original value


def _key(entity: Entity, name_to_full: dict[str, str]) -> tuple[str, str]:
    if entity.type in _NUMERIC_TYPES:
        return entity.type, re.sub(r"[\s-]", "", entity.value)
    value = entity.value.casefold()
    if entity.type == "PERSON":  # "Priya" and "Priya Nair" are the same person -> same placeholder
        value = name_to_full.get(value, value)
    return entity.type, value


def _name_links(entities: list[Entity]) -> dict[str, str]:
    """Map each single name part to the longest full name that contains it."""
    full_names = sorted((e.value.casefold() for e in entities if e.type == "PERSON"), key=len, reverse=True)
    links: dict[str, str] = {}
    for full in full_names:
        for token in re.findall(r"[a-z]+", full):
            links.setdefault(token, full)
    return links


def redact(text: str, entities: list[Entity]) -> Redaction:
    """Swap each entity for [TYPE_n]. The same value always gets the same placeholder."""
    counters: dict[str, int] = {}
    seen: dict[tuple[str, str], str] = {}
    vault: dict[str, str] = {}
    pairs: list[tuple[Entity, str]] = []
    out: list[str] = []
    cursor = 0
    links = _name_links(entities)
    for entity in sorted(entities, key=lambda e: e.start):
        key = _key(entity, links)
        if key not in seen:
            counters[entity.type] = counters.get(entity.type, 0) + 1
            placeholder = f"[{entity.type}_{counters[entity.type]}]"
            seen[key] = placeholder
            vault[placeholder] = entity.value
        placeholder = seen[key]
        out.append(text[cursor : entity.start])
        out.append(placeholder)
        cursor = entity.end
        pairs.append((entity, placeholder))
    out.append(text[cursor:])
    return Redaction("".join(out), pairs, vault)


def assert_clean(redacted_text: str, vault: dict[str, str]) -> None:
    """Fail-closed safety check: no original value may remain in the outgoing text."""
    for placeholder, original in vault.items():
        # whole-token match, so a phone number is not "found" inside a longer order number
        if original and re.search(rf"(?<![A-Za-z0-9]){re.escape(original)}(?![A-Za-z0-9])", redacted_text):
            raise PrivacyLeakError(f"An original {placeholder.strip('[]').rsplit('_', 1)[0]} value is still present.")


def restore(text: str, vault: dict[str, str]) -> tuple[str, list[str]]:
    """Put original values back. Returns (restored_text, unknown_placeholders)."""
    unknown: list[str] = []

    def swap(match: re.Match[str]) -> str:
        placeholder = f"[{match.group(1)}]"
        if placeholder in vault:
            return vault[placeholder]
        if placeholder not in unknown:
            unknown.append(placeholder)
        return match.group(0)

    return _PLACEHOLDER.sub(swap, text), unknown


def mask(value: str) -> str:
    """Display-safe version of a value, e.g. 'Rajesh Kumar' -> 'R***********r'."""
    if len(value) <= 4:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]
