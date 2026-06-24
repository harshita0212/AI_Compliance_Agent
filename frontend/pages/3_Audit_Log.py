"""
Audit Log — the immutable record of every verdict.

Reads live from the backend. Rich filtering and CSV/PDF export come in step 5.
"""
from __future__ import annotations

import streamlit as st

import api_client as api

st.set_page_config(page_title="Audit Log", page_icon="list", layout="wide")
st.title("Audit log")
st.caption("Every verdict, newest first — append-only")

try:
    entries = api.list_audit(200)
except Exception as e:  # noqa: BLE001
    st.error(f"Cannot load the audit log: {e}")
    st.stop()

if not entries:
    st.info("No verdicts logged yet. Run a check to populate the log.")
    st.stop()

# Compact table view
table = [
    {
        "ref": e["audit_reference"],
        "verdict": e["verdict"],
        "channel": e["channel"],
        "segment": e["audience_segment"],
        "consent": e["consent_rate"],
        "violations": len(e.get("violations", [])),
        "corpus": e["rule_corpus_version"],
        "time": e["timestamp"],
    }
    for e in entries
]
st.dataframe(table, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Entry detail")
ref = st.selectbox("Select a reference", [e["audit_reference"] for e in entries])
detail = next((e for e in entries if e["audit_reference"] == ref), None)
if detail:
    st.markdown(f"**Verdict:** {detail['verdict']} · **corpus** {detail['rule_corpus_version']}")
    st.markdown(f"**Content:** {detail.get('content') or '—'}")
    for vio in detail.get("violations", []):
        st.markdown(f"- **{vio['severity']}** · {vio['citation']} — {vio['explanation']}")

st.caption("Filtering, search, and export arrive in step 5.")
