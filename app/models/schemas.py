"""
Pydantic models — the contract for every request and response.

Strict validation here means a bad request (e.g. an invalid channel) is
rejected at the gateway BEFORE any expensive Gemini/DB work runs.
(Suggested change #6)
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------- Enums (strict, closed sets) ----------

class Channel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    SOCIAL_MEDIA = "social_media"


class Verdict(str, Enum):
    APPROVED = "APPROVED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class RuleSource(str, Enum):
    DPDP = "DPDP"
    ASCI = "ASCI"
    TRAI = "TRAI"
    BIS = "BIS"


class ReviewAction(str, Enum):
    OVERRIDE_APPROVE = "override_approve"
    REJECT = "reject"
    SEND_BACK = "send_back"


class ReviewRequest(BaseModel):
    action: ReviewAction
    justification: str = Field(default="", description="Required for overrides/rejections.")
    reviewer: str = Field(default="", description="Ignored; identity comes from auth.")


# ---------- Request ----------

class CampaignRequest(BaseModel):
    content: str = Field(..., min_length=1, description="The campaign copy/text.")
    channel: Channel = Field(..., description="email | SMS | WhatsApp")
    audience_segment: str = Field(..., min_length=1, description="Audience segment ID or name.")


# ---------- Sub-structures ----------

class ContentAnalysis(BaseModel):
    """Structured output of the content-analysis layer. Flows downstream."""
    claims: list[str] = Field(default_factory=list)
    comparisons: list[str] = Field(default_factory=list)
    urgency_phrases: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.claims or self.comparisons or self.urgency_phrases)


class RuleHit(BaseModel):
    """A raw detection from rule matching — BEFORE the citation is attached."""
    rule_id: str
    rule_source: RuleSource
    severity: Severity
    triggering_text: str


class Violation(BaseModel):
    severity: Severity
    triggering_text: str
    rule_source: RuleSource
    citation: str          # e.g. "DPDP Act 2023, Section 6"
    explanation: str
    suggested_fix: str


class ConsentSummary(BaseModel):
    audience_size: int
    consented: int
    consent_rate: float            # 0.0 - 1.0
    must_suppress: int             # users who must be excluded


# ---------- Response ----------

class ComplianceVerdict(BaseModel):
    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=1.0)
    violations: list[Violation] = Field(default_factory=list)
    consent_summary: Optional[ConsentSummary] = None
    audit_reference: str
    rule_corpus_version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None     # used for fail-safe / degraded-mode messages


class RemediationResponse(BaseModel):
    suggested_rewrite: str
    explanation: str

