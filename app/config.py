"""
Central config. Reads from environment / .env so no secrets live in code.
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

# Load variables from a .env file in the project root, if present.
load_dotenv()


class Settings:
    # --- App ---
    APP_NAME: str = "AI Compliance Agent"
    APP_VERSION: str = "1.0"

    # --- Gemini ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    @property
    def gemini_enabled(self) -> bool:
        """Gemini runs whenever a key is configured."""
        return bool(self.GEMINI_API_KEY.strip())

    # --- Rule corpus ---
    RULE_CORPUS_VERSION: str = os.getenv("RULE_CORPUS_VERSION", "2026.06.1")
    RULES_DIR: str = os.getenv("RULES_DIR", "app/data/rules")

    # --- Verdict thresholds ---
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))
    MIN_CONSENT_RATE: float = float(os.getenv("MIN_CONSENT_RATE", "1.0"))  # all targeted users must consent

    # --- Mode ---
    USE_MOCK_LLM: bool = os.getenv("USE_MOCK_LLM", "true").lower() == "true"

    # --- Audit log ---
    # SQLite for the prototype; swap to a Postgres DSN later with one change.
    AUDIT_DB_PATH: str = os.getenv("AUDIT_DB_PATH", "audit_log.db")


@lru_cache
def get_settings() -> Settings:
    return Settings()
