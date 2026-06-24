"""
Approval Inbox — human-in-the-loop review of FLAGGED campaigns.

Reads flagged verdicts from the audit log and shows the flagged content
beside the AI's reasoning. The Override/Reject actions are stubbed here —
they get wired to a backend review endpoint in step 4, so a reviewer's
decision is logged ALONGSIDE the original verdict (never overwriting it).
"""
from __future__ import annotations

import streamlit as st

import api_client as api

st.set_page_config(page_title="Approval Inbox", page_icon="inbox", layout="wide")
st.title("Approval inbox")
st.caption("Flagged campaigns awaiting human review")

try:
    entries = [e for e in api.list_audit(200) if e["verdict"] == "FLAGGED"]
except Exception as e:  # noqa: BLE001
    st.error(f"Cannot load the audit log: {e}")
    st.stop()

if not entries:
    st.info("No flagged campaigns in the queue. Run a borderline campaign to populate this.")
    st.stop()

for e in entries:
    with st.container(border=True):
        left, right = st.columns(2)
        with left:
            st.markdown("**Flagged content**")
            st.write(e.get("content") or "—")
            st.caption(f"{e['channel']} · {e['audience_segment']} · ref {e['audit_reference']}")
        with right:
            st.markdown("**AI reasoning**")
            if e.get("notes"):
                st.write(e["notes"])
            for vio in e.get("violations", []):
                st.markdown(f"- **{vio['severity']}** · {vio['citation']} — {vio['explanation']}")
            if not e.get("violations") and not e.get("notes"):
                st.write("No specific violations recorded.")

        b1, b2, _ = st.columns([1, 1, 4])
        b1.button("Override & approve", key=f"ovr_{e['audit_reference']}", disabled=True)
        b2.button("Reject", key=f"rej_{e['audit_reference']}", disabled=True)

st.caption("Review actions are wired to the backend in step 4 (logged alongside the original verdict).")
