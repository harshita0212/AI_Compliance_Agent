"""
Run the compliance evaluation from the terminal:

    python scripts/run_eval.py

Runs the labelled test set through the live pipeline (including Gemini if a key
is configured) and prints accuracy plus a per-case breakdown. Does not touch the
audit log.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make the project root importable when run as `python scripts/run_eval.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.evaluation import evaluate  # noqa: E402


def _bar(label: str, value: str) -> str:
    return f"  {label:<34} {value}"


async def main() -> int:
    r = await evaluate()

    print("=" * 56)
    print("  COMPLIANCE AGENT - ACCURACY REPORT")
    print(f"  rule corpus {r['rule_corpus_version']}")
    print("=" * 56)
    print(_bar("Accuracy", f"{r['accuracy']:.0%}  ({r['correct']}/{r['total']})"))
    print(_bar("Unsafe misses (let risky through)", str(r["unsafe_misses"])))
    print(_bar("Over-blocks (flagged clean copy)", str(r["over_blocks"])))
    print("-" * 56)
    print(f"  {'CASE':<18}{'EXPECTED':<10}{'ACTUAL':<10}RESULT")
    print("-" * 56)
    for c in r["results"]:
        result = "ok" if c["correct"] else ("UNSAFE MISS" if c["unsafe_miss"] else "over-block")
        print(f"  {c['id']:<18}{c['expected']:<10}{c['actual']:<10}{result}")
    print("=" * 56)

    # Non-zero exit if any unsafe miss, so this can gate CI later.
    return 1 if r["unsafe_misses"] else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
