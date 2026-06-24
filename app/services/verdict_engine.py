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

    # Confidence: 1.0 minus the weighted load of violations, floored at 0.
    load = sum(_SEVERITY_WEIGHT[v.severity] for v in violations)
    confidence = max(0.0, round(1.0 - min(load, 1.0), 2))

    if has_critical or consent_failed:
        verdict = Verdict.REJECTED
    elif violations or confidence < settings.CONFIDENCE_THRESHOLD:
        verdict = Verdict.FLAGGED
    else:
        verdict = Verdict.APPROVED

    return ComplianceVerdict(
        verdict=verdict,
        confidence=confidence,
        violations=violations,
        consent_summary=consent,
        audit_reference=audit_reference,
        rule_corpus_version=rule_corpus_version,
        notes=notes,
    )
