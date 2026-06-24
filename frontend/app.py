"""
AI Compliance Agent — frontend home.

Run from the project root with:
    streamlit run frontend/app.py

Streamlit auto-builds the sidebar nav from the files in frontend/pages/.
"""
from __future__ import annotations

import streamlit as st

import api_client as api

st.set_page_config(page_title="AI Compliance Agent", page_icon="check", layout="wide")

st.title("AI Compliance Agent")
st.caption("Automated marketing-compliance review — DPDP, ASCI, TRAI, BIS")

st.write(
    "Submit a campaign and get a verdict in seconds, with the exact law behind "
    "every decision. Use the sidebar to navigate:"
)

st.markdown(
    "- **Check Campaign** — submit content and get an APPROVED / FLAGGED / REJECTED verdict\n"
    "- **Approval Inbox** — review flagged campaigns (human-in-the-loop)\n"
    "- **Audit Log** — the immutable record of every verdict\n"
    "- **Dashboard** — compliance metrics at a glance"
)

st.divider()

# Backend health indicator
try:
    h = api.health()
    st.success(
        f"Backend connected · rule corpus {h['rule_corpus_version']} · "
        f"{'mock LLM' if h['mock_llm'] else 'live Gemini'}"
    )
except Exception as e:  # noqa: BLE001
    st.error(
        f"Cannot reach the backend at {api.BASE_URL}. "
        "Start it with `python run.py` in another terminal."
    )
    st.caption(str(e))
