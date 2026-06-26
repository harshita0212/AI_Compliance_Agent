"""
Thin HTTP client to the FastAPI backend.

Carries the signed-in user's API key on every request. sign_in_widget()
renders a sidebar role switch (demo stand-in for company SSO) and sets the key.
"""
from __future__ import annotations

import os

import requests
import streamlit as st

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
TIMEOUT = 30

KNOWN_SEGMENTS = ["all_customers", "premium_segment", "low_consent_segment", "newsletter_optin"]
CHANNELS = ["email", "SMS", "WhatsApp"]

# DEMO users (stand-in for SSO). name -> (api_key, role)
DEMO_USERS = {
    "Marketer": ("marketer-key", "marketer"),
    "Compliance Officer": ("officer-key", "compliance_officer"),
}

API_KEY: str | None = None


def sign_in_widget() -> tuple[str, str]:
    """Sidebar role switch. Sets the active API key. Returns (name, role)."""
    global API_KEY
    name = st.sidebar.radio("Signed in as", list(DEMO_USERS), key="_signed_in_as")
    key, role = DEMO_USERS[name]
    API_KEY = key
    st.session_state["user_name"] = name
    st.session_state["user_role"] = role
    return name, role


def _headers() -> dict:
    return {"X-API-Key": API_KEY} if API_KEY else {}


def health() -> dict:
    r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def check_campaign(content: str, channel: str, audience_segment: str) -> dict:
    r = requests.post(
        f"{BASE_URL}/check",
        json={"content": content, "channel": channel, "audience_segment": audience_segment},
        headers=_headers(), timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def list_audit(limit: int = 100) -> list[dict]:
    r = requests.get(f"{BASE_URL}/audit", params={"limit": limit}, headers=_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_audit(audit_reference: str) -> dict:
    r = requests.get(f"{BASE_URL}/audit/{audit_reference}", headers=_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def review(audit_reference: str, action: str, justification: str) -> dict:
    r = requests.post(
        f"{BASE_URL}/audit/{audit_reference}/review",
        json={"action": action, "justification": justification},
        headers=_headers(), timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def run_eval() -> dict:
    r = requests.get(f"{BASE_URL}/eval", headers=_headers(), timeout=120)
    r.raise_for_status()
    return r.json()


def extract_file(file_bytes: bytes, filename: str, content_type: str | None = None) -> dict:
    files = {"file": (filename, file_bytes, content_type or "application/octet-stream")}
    r = requests.post(f"{BASE_URL}/extract", files=files, headers=_headers(), timeout=120)
    r.raise_for_status()
    return r.json()
