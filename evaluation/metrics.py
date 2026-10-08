"""Scoring for PII detection. Pure functions, no API needed."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from privgate.detectors import Entity


@dataclass
class Counts:
    tp: int = 0
    predicted: int = 0
    gold: int = 0
    covered: int = 0  # gold spans overlapped by any prediction (type-agnostic)
    decoys: int = 0
    decoys_hit: int = 0  # decoys wrongly overlapped by a prediction
    by_type: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))

    def add(self, other: Counts) -> None:
        for name in ("tp", "predicted", "gold", "covered", "decoys", "decoys_hit"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        for t, d in other.by_type.items():
            for k, v in d.items():
                self.by_type[t][k] += v


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def score_sample(pred: list[Entity], gold: list[dict], decoys: list[dict]) -> Counts:
    c = Counts(predicted=len(pred), gold=len(gold), decoys=len(decoys))
    gold_keys = {(g["type"], g["start"], g["end"]) for g in gold}
    for p in pred:
        c.by_type[p.type]["predicted"] += 1
        if (p.type, p.start, p.end) in gold_keys:
            c.tp += 1
            c.by_type[p.type]["tp"] += 1
    for g in gold:
        c.by_type[g["type"]]["gold"] += 1
        if any(_overlap(g["start"], g["end"], p.start, p.end) for p in pred):
            c.covered += 1
    c.decoys_hit = sum(1 for d in decoys if any(_overlap(d["start"], d["end"], p.start, p.end) for p in pred))
    return c


def prf(tp: int, predicted: int, gold: int) -> tuple[float, float, float]:
    precision = tp / predicted if predicted else 1.0
    recall = tp / gold if gold else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return round(precision, 3), round(recall, 3), round(f1, 3)


def summarize(c: Counts) -> dict[str, float]:
    precision, recall, f1 = prf(c.tp, c.predicted, c.gold)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "privacy_recall": round(c.covered / c.gold, 3) if c.gold else 1.0,
        "decoy_false_alarm_rate": round(c.decoys_hit / c.decoys, 3) if c.decoys else 0.0,
    }
