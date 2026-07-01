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
CHANNELS = ["email", "sms", "whatsapp", "social_media"]

# DEMO users (stand-in for SSO). name -> (api_key, role)
DEMO_USERS = {
    "marketer": ("marketer-key", "marketer"),
    "compliance_officer": ("officer-key", "compliance_officer"),
}


def sign_in_widget() -> tuple[str, str]:
    """
    Renders user status and log out button in the sidebar.
    Returns (username, role) based on the session state.
    """
    name = st.session_state.get("user_name", "Guest")
    role = st.session_state.get("user_role", "marketer")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👤 Session Profile")
    st.sidebar.markdown(f"**User:** `{name}`")
    st.sidebar.markdown(f"**Role:** `{role.replace('_', ' ').title()}`")
    
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    if st.sidebar.button("🚪 Log Out", key="sidebar_logout_btn", use_container_width=True):
        st.session_state.clear()
        st.session_state["authenticated"] = False
        st.rerun()
        
    return name, role


def _headers() -> dict:
    role = st.session_state.get("user_role", "marketer")
    key = "officer-key" if role == "compliance_officer" else "marketer-key"
    return {"X-API-Key": key}



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
