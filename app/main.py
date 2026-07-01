"""
FastAPI entry point.

Exposes the compliance engine as an API with role-based access control and a
GLOBAL exception handler so an unexpected error never returns a bare 500 - it
returns a FLAGGED verdict, keeping the system legally fail-safe.

The app is intentionally thin: all logic lives in app/services + app/core,
so the Streamlit demo can later be swapped for React with no engine rewrite.
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core import corpus
from app.core.auth import get_current_user, require_compliance_officer
from app.core.orchestrator import run_compliance_check
from app.models.schemas import CampaignRequest, ComplianceVerdict, ReviewAction, ReviewRequest, Verdict, RemediationResponse
from app.services import audit_log, evaluation, file_extraction, gemini_matching

settings = get_settings()

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)


@app.on_event("startup")
async def _startup() -> None:
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
async def check_campaign(req: CampaignRequest, user: dict = Depends(get_current_user)) -> ComplianceVerdict:
    verdict = await run_compliance_check(req)
    await asyncio.to_thread(audit_log.write, req, verdict)
    return verdict


@app.post("/remediate", response_model=RemediationResponse)
async def remediate_campaign(req: CampaignRequest, user: dict = Depends(get_current_user)) -> RemediationResponse:
    if not settings.gemini_enabled:
        raise HTTPException(
            status_code=400,
            detail="AI Auto-Remediation requires a Gemini API key. Please configure GEMINI_API_KEY in the environment.",
        )
    
    # 1. Run compliance check to identify violations
    verdict = await run_compliance_check(req)
    
    # 2. Filter out consent violations as they cannot be fixed via copy rewrite
    copy_violations = [v for v in verdict.violations if "consent" not in v.citation.lower()]
    
    if not copy_violations:
        # Check if there was a consent issue
        consent_failed = any("consent" in v.citation.lower() for v in verdict.violations)
        if consent_failed:
            explanation = "The copywriting itself is compliant, but the targeted audience segment consent rate is too low. Copywriting changes cannot fix consent shortfalls."
        else:
            explanation = "No compliance violations found in the copywriting. The campaign copy is already compliant."
            
        return RemediationResponse(
            suggested_rewrite=req.content,
            explanation=explanation,
        )
        
    # 3. Call Gemini to rewrite the content
    try:
        rewrite_text = await gemini_matching.rewrite(req.content, verdict.violations)
        return RemediationResponse(
            suggested_rewrite=rewrite_text,
            explanation="Successfully generated a compliant copywriting rewrite to address detected violations.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate remediation suggestion: {e}",
        )



@app.get("/audit")
async def list_audit(limit: int = 100, user: dict = Depends(get_current_user)) -> list[dict]:
    return await asyncio.to_thread(audit_log.list_entries, limit)


@app.post("/extract")
async def extract_file(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> dict:
    """
    Extract text from an uploaded PDF or image so it can be checked.
    Local-first (pypdf / OCR); falls back to Gemini vision. Does not run the
    compliance check or write the audit log - the user reviews the text first.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty file.")
    return await asyncio.to_thread(
        file_extraction.extract_text, data, file.filename or "", file.content_type
    )


@app.get("/eval")
async def run_evaluation(user: dict = Depends(get_current_user)) -> dict:
    """Run the labelled test set through the pipeline and return accuracy metrics."""
    return await evaluation.evaluate()


@app.get("/audit/{audit_reference}")
async def get_audit(audit_reference: str, user: dict = Depends(get_current_user)) -> dict:
    entry = await asyncio.to_thread(audit_log.get_entry, audit_reference)
    if entry is None:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    return entry


@app.post("/audit/{audit_reference}/review")
async def review_audit(
    audit_reference: str,
    review: ReviewRequest,
    user: dict = Depends(require_compliance_officer),
) -> dict:
    """
    Record a human review action. Restricted to compliance officers. The
    reviewer's identity is taken from their authenticated login, not from the
    request body, so it cannot be spoofed.
    """
    entry = await asyncio.to_thread(audit_log.get_entry, audit_reference)
    if entry is None:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    if review.action in (ReviewAction.OVERRIDE_APPROVE, ReviewAction.REJECT) and not review.justification.strip():
        raise HTTPException(status_code=422, detail="A justification is required to override or reject.")

    return await asyncio.to_thread(
        audit_log.add_review,
        audit_reference,
        user["name"],            # identity from auth, not the request body
        review.action.value,
        review.justification,
    )


@app.exception_handler(Exception)
async def global_fail_safe_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all. Anything that slips through becomes a FLAGGED verdict, not a 500.
    (FastAPI handles HTTPException/401/403/422 with its own handlers first, so
    auth errors still return their proper status codes.)
    """
    verdict = ComplianceVerdict(
        verdict=Verdict.FLAGGED,
        confidence=0.0,
        audit_reference=f"AUD-ERR-{uuid.uuid4().hex[:8]}",
        rule_corpus_version=corpus.version(),
        notes=f"Unhandled error, auto-flagged for human review: {type(exc).__name__}",
    )
    return JSONResponse(status_code=200, content=verdict.model_dump(mode="json"))
