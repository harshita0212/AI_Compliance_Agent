"""
Audit Log - the immutable legal paper trail.

Two append-only tables:
  - audit_log: one row per verdict (never mutated)
  - reviews:   one row per human review action, referencing a verdict

A reviewer's decision is recorded as a NEW review row, never by editing the
original verdict. Both the AI's verdict and every human action on it stay
visible forever - that is what makes the trail defensible.

Storage backend is chosen at runtime:
  - Postgres, if DATABASE_URL is set (production / multi-user).
  - SQLite, otherwise (zero-setup local prototype).
The function signatures are identical for both, so nothing else changes.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from app.config import get_settings
from app.models.schemas import CampaignRequest, ComplianceVerdict

settings = get_settings()

_IS_PG = bool(settings.DATABASE_URL.strip())
_PH = "%s" if _IS_PG else "?"  # parameter placeholder differs by driver

# Auto-increment syntax differs between the two engines.
_ID_COL = "id BIGSERIAL PRIMARY KEY" if _IS_PG else "id INTEGER PRIMARY KEY AUTOINCREMENT"

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
    notes               TEXT
);
"""

_REVIEWS_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS reviews (
    {_ID_COL},
    audit_reference  TEXT NOT NULL,
    reviewer         TEXT NOT NULL,
    action           TEXT NOT NULL,
    justification    TEXT,
    reviewed_at      TEXT NOT NULL
);
"""


def _connect():
    """Return a connection with dict-style rows, for whichever backend is active."""
    if _IS_PG:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(settings.DATABASE_URL, row_factory=dict_row)
    conn = sqlite3.connect(settings.AUDIT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_SCHEMA)
        conn.execute(_REVIEWS_SCHEMA)
        if _IS_PG:
            conn.commit()


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
    placeholders = ",".join([_PH] * 12)
    with _connect() as conn:
        conn.execute(
            f"""
            INSERT INTO audit_log (
                audit_reference, timestamp, channel, audience_segment,
                audience_size, consent_rate, verdict, confidence,
                rule_corpus_version, content, violations_json, notes
            ) VALUES ({placeholders})
            """,
            row,
        )
        if _IS_PG:
            conn.commit()


def add_review(audit_reference: str, reviewer: str, action: str, justification: str) -> dict:
    """Append a human review action. Never edits the original verdict row."""
    reviewed_at = datetime.now(timezone.utc).isoformat()
    placeholders = ",".join([_PH] * 5)
    with _connect() as conn:
        conn.execute(
            f"""
            INSERT INTO reviews (audit_reference, reviewer, action, justification, reviewed_at)
            VALUES ({placeholders})
            """,
            (audit_reference, reviewer, action, justification, reviewed_at),
        )
        if _IS_PG:
            conn.commit()
    return {
        "audit_reference": audit_reference,
        "reviewer": reviewer,
        "action": action,
        "justification": justification,
        "reviewed_at": reviewed_at,
    }


def _reviews_for(conn, refs: list[str]) -> dict[str, list[dict]]:
    if not refs:
        return {}
    placeholders = ",".join([_PH] * len(refs))
    rows = conn.execute(
        f"SELECT * FROM reviews WHERE audit_reference IN ({placeholders}) ORDER BY reviewed_at ASC",
        refs,
    ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        d = dict(r)
        grouped.setdefault(d["audit_reference"], []).append(d)
    return grouped


def list_entries(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT {_PH}", (limit,)
        ).fetchall()
        entries = [_row_to_dict(r) for r in rows]
        reviews = _reviews_for(conn, [e["audit_reference"] for e in entries])
    for e in entries:
        e["reviews"] = reviews.get(e["audit_reference"], [])
    return entries


def get_entry(audit_reference: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            f"SELECT * FROM audit_log WHERE audit_reference = {_PH}", (audit_reference,)
        ).fetchone()
        if row is None:
            return None
        entry = _row_to_dict(row)
        entry["reviews"] = _reviews_for(conn, [audit_reference]).get(audit_reference, [])
    return entry


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["violations"] = json.loads(d.pop("violations_json") or "[]")
    return d
