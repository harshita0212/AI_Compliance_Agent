"""
Consent Validation layer.

Checks the target audience against the consent store. Never assumes consent:
if the store is unavailable, the orchestrator flags the campaign.

The mock store stands in for SQLite now and Salesforce later — same interface.
"""
from __future__ import annotations

from app.models.schemas import ConsentSummary

# Mock consent store: segment -> (total_users, consented_users)
# In production this is a SQLite/Salesforce lookup.
_MOCK_STORE: dict[str, tuple[int, int]] = {
    "all_customers":      (10000, 9800),
    "premium_segment":    (2000, 2000),
    "low_consent_segment": (5000, 3100),   # 38% missing consent -> should fail
    "newsletter_optin":   (8000, 8000),
}


async def validate_consent(audience_segment: str, channel: str) -> ConsentSummary:
    if audience_segment not in _MOCK_STORE:
        # Unknown segment = no verifiable consent = treat as zero.
        return ConsentSummary(
            audience_size=0, consented=0, consent_rate=0.0, must_suppress=0
        )

    total, consented = _MOCK_STORE[audience_segment]
    rate = consented / total if total else 0.0
    return ConsentSummary(
        audience_size=total,
        consented=consented,
        consent_rate=round(rate, 4),
        must_suppress=total - consented,
    )
