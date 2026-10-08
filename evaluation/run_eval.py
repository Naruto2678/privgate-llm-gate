"""Measure PII detection quality and show what each idea adds. No API key needed.

    python -m evaluation.run_eval
"""

from __future__ import annotations

import json
from pathlib import Path

from privgate.config import PrivacyConfig
from privgate.detectors import find_entities
from privgate.ner import person_spans, spacy_available

from .metrics import Counts, score_sample, summarize

DATA = Path(__file__).resolve().parent / "data" / "eval_set.jsonl"
RESULTS = Path(__file__).resolve().parent / "results"


def load_rows() -> list[dict]:
    return [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_config(rows: list[dict], cfg: PrivacyConfig) -> Counts:
    total = Counts()
    ner = person_spans if cfg.use_spacy_ner else None
    for row in rows:
        total.add(score_sample(find_entities(row["text"], cfg, ner), row["entities"], row["decoys"]))
    return total


def main() -> int:
    rows = load_rows()
    configs = [
        ("1. plain regex", PrivacyConfig(use_checksums=False, use_context_rules=False)),
        ("2. + checksums (Verhoeff, Luhn, PAN type)", PrivacyConfig(use_checksums=True, use_context_rules=False)),
        ("3. + context rules (A/C, PIN, names)", PrivacyConfig(use_checksums=True, use_context_rules=True)),
    ]
    if spacy_available():
        configs.append(("4. + spaCy name detection", PrivacyConfig(use_checksums=True, use_context_rules=True, use_spacy_ner=True)))
    else:
        print("(spaCy not installed - skipping config 4. See README to enable it.)\n")

    gold_total = sum(len(r["entities"]) for r in rows)
    decoy_total = sum(len(r["decoys"]) for r in rows)
    lines = [
        f"Dataset: {len(rows)} synthetic samples, {gold_total} personal values, {decoy_total} look-alike decoys.\n",
        "| configuration | precision | recall | F1 | privacy recall | decoy false-alarm rate |",
        "|---|---|---|---|---|---|",
    ]
    last: Counts | None = None
    for name, cfg in configs:
        counts = run_config(rows, cfg)
        m = summarize(counts)
        lines.append(f"| {name} | {m['precision']} | {m['recall']} | {m['f1']} | {m['privacy_recall']} | {m['decoy_false_alarm_rate']} |")
        last = counts

    lines += ["", "Per type (last configuration):", "", "| type | gold | predicted | exact matches |", "|---|---|---|---|"]
    assert last is not None
    for t in sorted(last.by_type):
        d = last.by_type[t]
        lines.append(f"| {t} | {d.get('gold', 0)} | {d.get('predicted', 0)} | {d.get('tp', 0)} |")
    lines += [
        "",
        "precision/recall/F1 need an exact span + type match. privacy recall counts a personal value as",
        "covered if ANY detection overlaps it (what matters for privacy). The data is synthetic and written",
        "by the same author as the rules, so treat the numbers as optimistic.",
    ]
    report = "\n".join(lines)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "latest.md").write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
