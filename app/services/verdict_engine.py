"""
Verdict Engine.

Aggregates consent + rule violations, applies severity weighting, and
selects APPROVED / FLAGGED / REJECTED. Fails safe: when uncertain, it
never auto-approves.

Rules:
  - Any Critical violation, OR consent rate below threshold -> REJECTED
  - Any violation below the confidence threshold / medium severity -> FLAGGED
  - No violations and full consent -> APPROVED
"""
from __future__ import annotations

from app.config import get_settings
from app.models.schemas import (
    ComplianceVerdict,
    ConsentSummary,
    RuleSource,
    Severity,
    Verdict,
    Violation,
)

settings = get_settings()

_SEVERITY_WEIGHT = {
    Severity.CRITICAL: 1.0,
    Severity.HIGH: 0.6,
    Severity.MEDIUM: 0.3,
    Severity.LOW: 0.1,
}


def decide(
    violations: list[Violation],
    consent: ConsentSummary,
    audit_reference: str,
    rule_corpus_version: str,
    notes: str | None = None,
) -> ComplianceVerdict:
    consent_failed = consent.consent_rate < settings.MIN_CONSENT_RATE

    # A consent shortfall is itself a DPDP violation — surface it in the list
    # with the legal citation, don't just silently reject.
    if consent_failed:
        pct = round((1 - consent.consent_rate) * 100, 1)
        violations = violations + [
            Violation(
                severity=Severity.CRITICAL,
                triggering_text=f"{pct}% of the audience has no verifiable consent",
                rule_source=RuleSource.DPDP,
                citation="DPDP Act 2023, Section 6 (Consent)",
                explanation=(
                    f"{consent.must_suppress} of {consent.audience_size} targeted "
                    "users have no consent record. Processing their data is unlawful."
                ),
                suggested_fix=(
                    "Suppress non-consenting users from the send list, or obtain "
                    "fresh consent before targeting them."
                ),
            )
        ]

    has_critical = any(v.severity == Severity.CRITICAL for v in violations)

    # Internal load metric — kept only to drive the FLAGGED threshold.
    violation_load = min(sum(_SEVERITY_WEIGHT[v.severity] for v in violations), 1.0)

    if has_critical or consent_failed:
        verdict = Verdict.REJECTED
    elif violations or (1.0 - violation_load) < settings.CONFIDENCE_THRESHOLD:
        verdict = Verdict.FLAGGED
    else:
        verdict = Verdict.APPROVED

    # Reported confidence = how sure the agent is in THIS verdict (always set).
    llm_degraded = bool(notes) and "unavailable" in notes.lower()
    if consent_failed or has_critical:
        confidence = 0.97          # deterministic consent math / hard rule
    elif violations:
        confidence = 0.90          # rules fired; verdict well-supported
    else:
        confidence = 0.95          # clean, full pipeline ran
    if llm_degraded:
        confidence = min(confidence, 0.60)   # AI layer fell back -> less sure
    confidence = round(confidence, 2)

    return ComplianceVerdict(
        verdict=verdict,
        confidence=confidence,
        violations=violations,
        consent_summary=consent,
        audit_reference=audit_reference,
        rule_corpus_version=rule_corpus_version,
        notes=notes,
    )
