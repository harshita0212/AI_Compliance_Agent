"""
Thin HTTP client to the FastAPI backend.

The frontend never imports the engine directly — it only talks to the API.
That is what keeps Streamlit swappable for React later: the contract is HTTP,
not Python imports.
"""
from __future__ import annotations

import os

import requests

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
TIMEOUT = 30

# Mirrors the mock consent store keys in app/services/consent_validation.py.
# When real Salesforce data is wired in, this list comes from the backend.
KNOWN_SEGMENTS = [
    "all_customers",
    "premium_segment",
    "low_consent_segment",
    "newsletter_optin",
]

CHANNELS = ["email", "SMS", "WhatsApp"]


def health() -> dict:
    r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def check_campaign(content: str, channel: str, audience_segment: str) -> dict:
    r = requests.post(
        f"{BASE_URL}/check",
        json={"content": content, "channel": channel, "audience_segment": audience_segment},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def list_audit(limit: int = 100) -> list[dict]:
    r = requests.get(f"{BASE_URL}/audit", params={"limit": limit}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_audit(audit_reference: str) -> dict:
    r = requests.get(f"{BASE_URL}/audit/{audit_reference}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def review(audit_reference: str, reviewer: str, action: str, justification: str) -> dict:
    r = requests.post(
        f"{BASE_URL}/audit/{audit_reference}/review",
        json={"reviewer": reviewer, "action": action, "justification": justification},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()
