"""
Approval Inbox - human-in-the-loop review of FLAGGED campaigns.

Shows flagged verdicts that have not yet been reviewed, beside the AI's
reasoning. A reviewer can Override & approve, Reject, or Send back. Each
action is recorded as a NEW review record alongside the original verdict
(never overwriting it). Reviewed items leave the queue.
"""
from __future__ import annotations

import streamlit as st

import api_client as api

st.set_page_config(page_title="Approval Inbox", page_icon="inbox", layout="wide")
st.title("Approval inbox")
st.caption("Flagged campaigns awaiting human review")

reviewer = st.text_input("Reviewer name", value="Compliance Officer")

try:
    all_entries = api.list_audit(200)
except Exception as e:  # noqa: BLE001
    st.error(f"Cannot load the audit log: {e}")
    st.stop()

# Pending = FLAGGED and not yet reviewed.
pending = [e for e in all_entries if e["verdict"] == "FLAGGED" and not e.get("reviews")]

if not pending:
    st.info("No flagged campaigns awaiting review. Run a borderline campaign to populate this.")
    st.stop()

st.write(f"**{len(pending)}** campaign(s) awaiting review")

for e in pending:
    ref = e["audit_reference"]
    with st.container(border=True):
        left, right = st.columns(2)
        with left:
            st.markdown("**Flagged content**")
            st.write(e.get("content") or "-")
            st.caption(f"{e['channel']} · {e['audience_segment']} · ref {ref}")
        with right:
            st.markdown("**AI reasoning**")
            if e.get("notes"):
                st.write(e["notes"])
            for vio in e.get("violations", []):
                st.markdown(f"- **{vio['severity']}** · {vio['citation']} - {vio['explanation']}")
            if not e.get("violations") and not e.get("notes"):
                st.write("No specific violations recorded.")

        justification = st.text_area(
            "Justification (required to override or reject)",
            key=f"just_{ref}",
            placeholder="Explain the decision for the audit trail…",
        )
        b1, b2, b3, _ = st.columns([1, 1, 1, 3])

        def _do(action: str):
            try:
                api.review(ref, reviewer or "Reviewer", action, justification)
                st.success("Recorded. Refreshing queue…")
                st.rerun()
            except Exception as ex:  # noqa: BLE001
                st.error(f"Could not record review: {ex}")

        if b1.button("Override & approve", key=f"ovr_{ref}"):
            if not justification.strip():
                st.warning("A justification is required to override.")
            else:
                _do("override_approve")
        if b2.button("Reject", key=f"rej_{ref}"):
            if not justification.strip():
                st.warning("A justification is required to reject.")
            else:
                _do("reject")
        if b3.button("Send back", key=f"snd_{ref}"):
            _do("send_back")
