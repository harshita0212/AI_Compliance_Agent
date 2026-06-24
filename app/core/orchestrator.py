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
from app.models.schemas import CampaignRequest, ComplianceVerdict, Verdict
from app.services import (
    citation_generator,
    consent_validation,
    content_analysis,
    rule_matching,
    verdict_engine,
)


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

    # 3. Rule matching — detection only, claims fed in.
    try:
        hits = await rule_matching.match(req.content, analysis)
    except RuleCorpusUnavailableError as e:
        return _fail_safe(audit_ref, f"rule corpus unavailable: {e}")

    # 4. Citation generator — attach the law + fix to each hit.
    violations = citation_generator.generate(hits)

    # 5. Verdict.
    note = "No claims extracted from content." if analysis.is_empty else None
    return verdict_engine.decide(
        violations=violations,
        consent=consent,
        audit_reference=audit_ref,
        rule_corpus_version=corpus.version(),
        notes=note,
    )
