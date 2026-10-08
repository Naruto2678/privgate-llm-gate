import json

from evaluation import make_dataset
from evaluation.metrics import Counts, prf, score_sample, summarize
from evaluation.run_eval import load_rows, run_config
from privgate.config import PrivacyConfig
from privgate.detectors import Entity


def test_dataset_is_reproducible_and_spans_are_correct():
    a, b = make_dataset.build(40, seed=1), make_dataset.build(40, seed=1)
    assert a == b
    for row in a:
        for g in row["entities"]:
            assert row["text"][g["start"] : g["end"]].strip() == row["text"][g["start"] : g["end"]]
        for d in row["decoys"]:
            assert row["text"][d["start"] : d["end"]]


def test_committed_dataset_matches_generator():
    committed = load_rows()
    assert committed == json.loads(json.dumps(make_dataset.build(len(committed), seed=42)))


def test_metrics_basic():
    gold = [{"type": "PHONE", "start": 0, "end": 10}, {"type": "EMAIL", "start": 20, "end": 30}]
    decoys = [{"kind": "DECOY_ORDER", "start": 40, "end": 52}]
    pred = [Entity("PHONE", 0, 10, "x", "regex"), Entity("AADHAAR", 40, 52, "y", "regex")]
    c = score_sample(pred, gold, decoys)
    assert (c.tp, c.predicted, c.gold, c.covered, c.decoys_hit) == (1, 2, 2, 1, 1)
    assert prf(1, 2, 2) == (0.5, 0.5, 0.5)
    assert summarize(c)["decoy_false_alarm_rate"] == 1.0
    total = Counts()
    total.add(c)
    total.add(c)
    assert total.tp == 2


def test_each_idea_improves_the_scores():
    """Regression guard for the headline claim of the project."""
    rows = load_rows()
    plain = summarize(run_config(rows, PrivacyConfig(use_checksums=False, use_context_rules=False)))
    checks = summarize(run_config(rows, PrivacyConfig(use_checksums=True, use_context_rules=False)))
    full = summarize(run_config(rows, PrivacyConfig(use_checksums=True, use_context_rules=True)))
    assert plain["decoy_false_alarm_rate"] > 0.5 and checks["decoy_false_alarm_rate"] < 0.05
    assert plain["precision"] < checks["precision"] < full["precision"] + 1e-9
    assert plain["f1"] < checks["f1"] < full["f1"]
    assert full["precision"] > 0.95 and full["recall"] > 0.9
