"""Command line.

    python -m privgate.cli redact --file samples/complaint_1.txt
    python -m privgate.cli chat --task draft_reply --file samples/complaint_1.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .errors import PrivGateError
from .gateway import Gateway
from .llm import build_client, list_tasks


def _read(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    return args.text if args.text else sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="India-aware PII redaction gateway for LLM APIs.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("redact", "Only redact (no API key needed)."), ("chat", "Redact, call the LLM, restore.")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--file", help="Path to a text file.")
        p.add_argument("--text", help="Text to process (otherwise stdin).")
        if name == "chat":
            p.add_argument("--task", default="draft_reply", choices=list_tasks())
    args = parser.parse_args(argv)

    cfg = load_config()
    try:
        text = _read(args)
        if args.command == "redact":
            out = Gateway(cfg).redact_only(text)
            print("REDACTED TEXT\n-------------\n" + out.redacted_text)
            print("\nFOUND:", ", ".join(f"{k} x{v}" for k, v in out.counts.items()) or "nothing")
            return 0
        result = Gateway(cfg, build_client(cfg)).run(args.task, text)
    except (PrivGateError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("SENT TO THE LLM (redacted)\n--------------------------\n" + result.redacted_input)
    print("\nLLM ANSWER (as received)\n------------------------\n" + result.reply_redacted)
    print("\nFINAL ANSWER (values restored)\n------------------------------\n" + result.reply)
    print("\nREDACTED:", ", ".join(f"{k} x{v}" for k, v in result.counts.items()) or "nothing")
    for w in result.warnings:
        print("WARNING:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
