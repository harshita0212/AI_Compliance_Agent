"""
FastAPI entry point.

Exposes the compliance engine as an API and installs a GLOBAL exception
handler so an unexpected error never returns a bare 500 — it returns a
FLAGGED verdict, keeping the system legally fail-safe. (Suggested change #5)

The app is intentionally thin: all logic lives in app/services + app/core,
so the Streamlit demo can later be swapped for React with no engine rewrite.
(Suggested change #1)
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core import corpus
from app.core.orchestrator import run_compliance_check
from app.models.schemas import CampaignRequest, ComplianceVerdict, ReviewAction, ReviewRequest, Verdict
from app.services import audit_log

settings = get_settings()

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)


@app.on_event("startup")
async def _startup() -> None:
    # Create the audit-log table if it does not exist yet.
    audit_log.init_db()


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "rule_corpus_version": corpus.version(),
        "gemini_enabled": settings.gemini_enabled,
        "model": settings.GEMINI_MODEL if settings.gemini_enabled else None,
    }


@app.post("/check", response_model=ComplianceVerdict)
async def check_campaign(req: CampaignRequest) -> ComplianceVerdict:
    # Pydantic has already validated channel/content at this point.
    verdict = await run_compliance_check(req)
    # Persist every verdict to the immutable audit log (off the event loop).
    await asyncio.to_thread(audit_log.write, req, verdict)
    return verdict


@app.get("/audit")
async def list_audit(limit: int = 100) -> list[dict]:
    """All verdicts, newest first — backs the Audit Log Viewer."""
    return await asyncio.to_thread(audit_log.list_entries, limit)


@app.get("/audit/{audit_reference}")
async def get_audit(audit_reference: str) -> dict:
    entry = await asyncio.to_thread(audit_log.get_entry, audit_reference)
    if entry is None:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    return entry


@app.post("/audit/{audit_reference}/review")
async def review_audit(audit_reference: str, review: ReviewRequest) -> dict:
    """
    Record a human review action against a verdict. Appended as a new review
    record - the original verdict is never overwritten.
    """
    entry = await asyncio.to_thread(audit_log.get_entry, audit_reference)
    if entry is None:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    # Guardrail: an override or rejection must be justified (per the spec).
    if review.action in (ReviewAction.OVERRIDE_APPROVE, ReviewAction.REJECT) and not review.justification.strip():
        raise HTTPException(status_code=422, detail="A justification is required to override or reject.")

    return await asyncio.to_thread(
        audit_log.add_review,
        audit_reference,
        review.reviewer,
        review.action.value,
        review.justification,
    )


@app.exception_handler(Exception)
async def global_fail_safe_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all. Anything that slips through becomes a FLAGGED verdict, not a 500.
    A human reviews it; nothing silently passes.
    """
    verdict = ComplianceVerdict(
        verdict=Verdict.FLAGGED,
        confidence=0.0,
        audit_reference=f"AUD-ERR-{uuid.uuid4().hex[:8]}",
        rule_corpus_version=corpus.version(),
        notes=f"Unhandled error, auto-flagged for human review: {type(exc).__name__}",
    )
    return JSONResponse(status_code=200, content=verdict.model_dump(mode="json"))
