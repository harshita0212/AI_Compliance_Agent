"""
Orchestrator — the pipeline conductor.

Sequences the layers exactly as the architecture diagram shows:

  input -> content analysis -> consent validation -> rule matching
        -> citation generator -> verdict engine -> (audit log) -> verdict

Centralises the fail-safe behaviour: any degraded condition returns a FLAGGED
verdict, never a silent pass and never a 500.
"""
from __future__ import annotations

import uuid

from app.core import corpus
from app.core.exceptions import (
    ConsentStoreUnavailableError,
    LLMUnavailableError,
    RuleCorpusUnavailableError,
)
from app.config import get_settings
from app.models.schemas import CampaignRequest, ComplianceVerdict, RuleHit, Verdict
from app.services import (
    citation_generator,
    consent_validation,
    content_analysis,
    gemini_matching,
    rule_matching,
    verdict_engine,
)

settings = get_settings()


def _merge_hits(keyword: list[RuleHit], gemini: list[RuleHit]) -> list[RuleHit]:
    """
    Combine both detectors into one hit per rule.

    A rule should count once even if several phrases triggered it (e.g. "100%"
    and "risk-free" both firing the same ASCI clause). Collapsing by rule_id
    keeps the violation list clean AND stops the verdict engine from counting
    one rule's severity twice. The triggering phrases are preserved, joined
    together, so no detail is lost.
    """
    by_rule: dict[str, RuleHit] = {}
    phrases: dict[str, list[str]] = {}
    for hit in keyword + gemini:
        if hit.rule_id not in by_rule:
            by_rule[hit.rule_id] = hit
            phrases[hit.rule_id] = []
        text = hit.triggering_text.strip()
        if text and text.lower() not in [p.lower() for p in phrases[hit.rule_id]]:
            phrases[hit.rule_id].append(text)

    merged: list[RuleHit] = []
    for rule_id, hit in by_rule.items():
        merged.append(hit.model_copy(update={"triggering_text": ", ".join(phrases[rule_id])}))
    return merged


def _audit_id() -> str:
    return f"AUD-{uuid.uuid4().hex[:12]}"


def _fail_safe(audit_ref: str, reason: str) -> ComplianceVerdict:
    """Degraded-mode verdict: always FLAGGED, never APPROVED."""
    return ComplianceVerdict(
        verdict=Verdict.FLAGGED,
        confidence=0.0,
        violations=[],
        consent_summary=None,
        audit_reference=audit_ref,
        rule_corpus_version=corpus.version(),
        notes=f"Auto-flagged for human review (degraded mode): {reason}",
    )


async def run_compliance_check(req: CampaignRequest) -> ComplianceVerdict:
    audit_ref = _audit_id()

    # 1. Content analysis — claims become a structured artifact.
    try:
        analysis = await content_analysis.analyze(req.content)
    except LLMUnavailableError as e:
        return _fail_safe(audit_ref, f"content analysis unavailable: {e}")

    # 2. Consent — never assume; failure flags.
    try:
        consent = await consent_validation.validate_consent(
            req.audience_segment, req.channel.value
        )
    except ConsentStoreUnavailableError as e:
        return _fail_safe(audit_ref, f"consent store unavailable: {e}")

    # 3. Rule matching — keyword detection.
    try:
        hits = await rule_matching.match(req.content, analysis)
    except RuleCorpusUnavailableError as e:
        return _fail_safe(audit_ref, f"rule corpus unavailable: {e}")

    # 3b. Gemini detection — runs alongside keyword matching, results merged.
    #     If Gemini is unavailable, fall back to keyword-only and record it
    #     (keyword detection is still valid, so we don't blanket-flag).
    degraded_note = None
    gemini_hits: list[RuleHit] = []
    if settings.gemini_enabled:
        try:
            gemini_hits = await gemini_matching.detect(req.content)
        except LLMUnavailableError as e:
            degraded_note = f"AI reasoning unavailable this run; keyword checks only ({e})."

    # Always collapse to one hit per rule (combines keyword + Gemini, and
    # also de-duplicates multiple keyword phrases that hit the same rule).
    hits = _merge_hits(hits, gemini_hits)

    # 4. Citation generator — attach the law + fix to each hit.
    violations = citation_generator.generate(hits)

    # 5. Verdict.
    note = degraded_note or ("No claims extracted from content." if analysis.is_empty else None)
    return verdict_engine.decide(
        violations=violations,
        consent=consent,
        audit_reference=audit_ref,
        rule_corpus_version=corpus.version(),
        notes=note,
    )
