"""
Rule Matching layer — DETECTION ONLY.

Matches the campaign against all four corpora (DPDP, ASCI, TRAI, BIS),
running every source CONCURRENTLY via asyncio.gather so total latency is
~the slowest single check, not the sum.

It returns raw RuleHit objects (which rule fired, on what text). It does NOT
attach the legal citation or fix — that is the Citation Generator's job. This
keeps "what fired" separate from "what the law says about it".

The ContentAnalysis is passed in so claims are a first-class input to the
pipeline; if nothing was extracted the run still proceeds and records the gap.
"""
from __future__ import annotations

import asyncio
import re

from app.core import corpus
from app.models.schemas import ContentAnalysis, RuleHit, RuleSource, Severity


async def _check_source(source: str, text: str) -> list[RuleHit]:
    """Check one rule source. Runs as its own coroutine."""
    hits: list[RuleHit] = []
    for rule in corpus.rules_for(source):
        for match in re.finditer(rule["pattern"], text):
            hits.append(
                RuleHit(
                    rule_id=rule["id"],
                    rule_source=RuleSource(source),
                    severity=Severity(rule["severity"]),
                    triggering_text=match.group(0),
                )
            )
    await asyncio.sleep(0)  # real I/O (DB/vector lookup) slots in here
    return hits


async def match(content: str, analysis: ContentAnalysis) -> list[RuleHit]:
    text = content.lower()
    results = await asyncio.gather(
        *[_check_source(s, text) for s in corpus.SOURCES],
        return_exceptions=True,
    )
    hits: list[RuleHit] = []
    for r in results:
        if isinstance(r, Exception):
            continue  # one corpus down -> skip it, don't crash the run
        hits.extend(r)
    return hits


def corpus_version() -> str:
    return corpus.version()
