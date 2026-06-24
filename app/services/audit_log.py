"""
Audit Log — the immutable legal paper trail.

Every verdict (including fail-safe FLAGGED ones) is written here as an
append-only record. This is what makes a decision defensible months later:
it records what was checked, what fired, the consent rate, the final verdict,
and which rule corpus version was active.

SQLite now; the function signatures are storage-agnostic so a Postgres
backend can replace the body without touching the callers.

Guardrail: stores the campaign content and aggregate consent rate, never
individual customer identities.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from app.config import get_settings
from app.models.schemas import CampaignRequest, ComplianceVerdict

settings = get_settings()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    audit_reference     TEXT PRIMARY KEY,
    timestamp           TEXT NOT NULL,
    channel             TEXT,
    audience_segment    TEXT,
    audience_size       INTEGER,
    consent_rate        REAL,
    verdict             TEXT NOT NULL,
    confidence          REAL,
    rule_corpus_version TEXT,
    content             TEXT,
    violations_json     TEXT,
    notes               TEXT,
    reviewer            TEXT,
    review_action       TEXT,
    review_justification TEXT,
    reviewed_at         TEXT
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.AUDIT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_SCHEMA)


def write(req: CampaignRequest, verdict: ComplianceVerdict) -> None:
    cs = verdict.consent_summary
    row = (
        verdict.audit_reference,
        verdict.timestamp.isoformat(),
        req.channel.value,
        req.audience_segment,
        cs.audience_size if cs else None,
        cs.consent_rate if cs else None,
        verdict.verdict.value,
        verdict.confidence,
        verdict.rule_corpus_version,
        req.content,
        json.dumps([v.model_dump(mode="json") for v in verdict.violations]),
        verdict.notes,
    )
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (
                audit_reference, timestamp, channel, audience_segment,
                audience_size, consent_rate, verdict, confidence,
                rule_corpus_version, content, violations_json, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            row,
        )


def list_entries(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_entry(audit_reference: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM audit_log WHERE audit_reference = ?", (audit_reference,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["violations"] = json.loads(d.pop("violations_json") or "[]")
    return d
