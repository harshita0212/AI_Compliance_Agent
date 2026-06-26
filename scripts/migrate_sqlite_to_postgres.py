"""
One-time migration: copy the audit log from the old SQLite file into Postgres.

Usage (from the project root, with the venv active and DATABASE_URL set in .env):

    python scripts/migrate_sqlite_to_postgres.py
    python scripts/migrate_sqlite_to_postgres.py --sqlite audit_log.db

Safe to run more than once: it skips rows that already exist in Postgres, so
re-running will not create duplicates. It never deletes or edits the SQLite
file - your old data stays where it is.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Make the project root importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402

settings = get_settings()


def _sqlite_rows(path: str, table: str) -> list[dict]:
    if not Path(path).exists():
        return []
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        # Table may not exist in older files; guard it.
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if table not in names:
            return []
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", default=settings.AUDIT_DB_PATH, help="Path to the old SQLite file")
    args = parser.parse_args()

    if not settings.DATABASE_URL.strip():
        print("DATABASE_URL is not set. Set it in .env to your Postgres DSN first.")
        return 1

    import psycopg

    audit_rows = _sqlite_rows(args.sqlite, "audit_log")
    review_rows = _sqlite_rows(args.sqlite, "reviews")
    print(f"Found {len(audit_rows)} verdict(s) and {len(review_rows)} review(s) in {args.sqlite}")

    if not audit_rows and not review_rows:
        print("Nothing to migrate.")
        return 0

    migrated_v = migrated_r = 0
    with psycopg.connect(settings.DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Verdicts. Skip any audit_reference already present.
            cur.execute("SELECT audit_reference FROM audit_log")
            existing = {r[0] for r in cur.fetchall()}
            for row in audit_rows:
                if row["audit_reference"] in existing:
                    continue
                cur.execute(
                    """
                    INSERT INTO audit_log (
                        audit_reference, timestamp, channel, audience_segment,
                        audience_size, consent_rate, verdict, confidence,
                        rule_corpus_version, content, violations_json, notes
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        row.get("audit_reference"), row.get("timestamp"), row.get("channel"),
                        row.get("audience_segment"), row.get("audience_size"), row.get("consent_rate"),
                        row.get("verdict"), row.get("confidence"), row.get("rule_corpus_version"),
                        row.get("content"), row.get("violations_json"), row.get("notes"),
                    ),
                )
                migrated_v += 1

            # Reviews. De-dupe on (audit_reference, reviewer, action, reviewed_at).
            cur.execute("SELECT audit_reference, reviewer, action, reviewed_at FROM reviews")
            existing_reviews = {tuple(r) for r in cur.fetchall()}
            for row in review_rows:
                key = (row.get("audit_reference"), row.get("reviewer"), row.get("action"), row.get("reviewed_at"))
                if key in existing_reviews:
                    continue
                cur.execute(
                    """
                    INSERT INTO reviews (audit_reference, reviewer, action, justification, reviewed_at)
                    VALUES (%s,%s,%s,%s,%s)
                    """,
                    (
                        row.get("audit_reference"), row.get("reviewer"), row.get("action"),
                        row.get("justification"), row.get("reviewed_at"),
                    ),
                )
                migrated_r += 1
        conn.commit()

    print(f"Migrated {migrated_v} new verdict(s) and {migrated_r} new review(s) into Postgres.")
    print("Done. (Re-running is safe - already-migrated rows are skipped.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
