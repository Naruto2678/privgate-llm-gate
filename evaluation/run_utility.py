"""Does redaction break the LLM's answers? (needs an API key)

Runs the full gateway on the sample messages and checks the round trip:
no placeholder is invented by the model, and the real name/phone are restored in the final answer.

    python -m evaluation.run_utility
"""

from __future__ import annotations

from pathlib import Path

from privgate.config import load_config
from privgate.gateway import Gateway
from privgate.llm import build_client
from privgate.redactor import restore

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def main() -> int:
    cfg = load_config()
    cfg.privacy.audit_log_path = None
    gateway = Gateway(cfg, build_client(cfg))
    rows, ok_total = [], 0
    for path in sorted(SAMPLES.glob("complaint_*.txt")):
        text = path.read_text(encoding="utf-8")
        red = gateway.sanitize(text)
        for task in ("draft_reply", "summarize"):
            result = gateway.run(task, text)
            _, unknown = restore(result.reply_redacted, red.vault)
            ok = not result.warnings and not unknown
            ok_total += ok
            used = sum(1 for ph in red.vault if ph in result.reply_redacted)
            rows.append((path.stem, task, len(red.vault), used, "yes" if ok else "NO: " + "; ".join(result.warnings)))
    print("| sample | task | placeholders sent | used in answer | clean round trip |\n|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(str(c) for c in r) + " |")
    print(f"\nClean round trips: {ok_total}/{len(rows)}   (model: {cfg.llm.model})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
