"""
Evaluation harness.

Runs the labelled test set (app/data/eval/test_cases.json) through the real
compliance pipeline and scores the result. Beyond plain accuracy it reports the
two errors that matter for a compliance tool:

  - Unsafe miss (false negative): something that should have been FLAGGED or
    REJECTED was APPROVED. This is the dangerous error - non-compliant content
    going out.
  - Over-block (false positive): clean content (should be APPROVED) was FLAGGED
    or REJECTED. Annoying, not dangerous.

It calls run_compliance_check directly, so it does NOT write to the audit log.
Results reflect the live configuration, including Gemini when enabled.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.core import corpus
from app.core.orchestrator import run_compliance_check
from app.models.schemas import CampaignRequest

_CASES_PATH = Path(__file__).resolve().parent.parent / "data" / "eval" / "test_cases.json"

# Severity ordering for "did it block at least as hard as it should have".
_RANK = {"APPROVED": 0, "FLAGGED": 1, "REJECTED": 2}


def load_cases() -> list[dict]:
    return json.loads(_CASES_PATH.read_text(encoding="utf-8"))["cases"]


async def _run_one(case: dict) -> dict:
    req = CampaignRequest(
        content=case["content"],
        channel=case["channel"],
        audience_segment=case["audience_segment"],
    )
    verdict = await run_compliance_check(req)
    actual = verdict.verdict.value
    expected = case["expected"]
    return {
        "id": case["id"],
        "category": case.get("category", ""),
        "expected": expected,
        "actual": actual,
        "correct": actual == expected,
        "unsafe_miss": _RANK[actual] < _RANK[expected],   # blocked less than it should
        "over_block": _RANK[actual] > _RANK[expected],    # blocked more than it should
    }


async def evaluate() -> dict:
    cases = load_cases()
    results = await asyncio.gather(*(_run_one(c) for c in cases))

    total = len(results)
    correct = sum(r["correct"] for r in results)
    unsafe = sum(r["unsafe_miss"] for r in results)
    over = sum(r["over_block"] for r in results)

    # Confusion matrix: expected -> actual -> count
    labels = ["APPROVED", "FLAGGED", "REJECTED"]
    confusion = {e: {a: 0 for a in labels} for e in labels}
    for r in results:
        confusion[r["expected"]][r["actual"]] += 1

    return {
        "rule_corpus_version": corpus.version(),
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "unsafe_misses": unsafe,
        "over_blocks": over,
        "confusion": confusion,
        "results": results,
    }


if __name__ == "__main__":  # allow `python -m app.services.evaluation`
    print(json.dumps(asyncio.run(evaluate()), indent=2))
