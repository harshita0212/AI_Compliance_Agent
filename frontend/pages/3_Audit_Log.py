"""
Audit Log - the immutable record of every verdict.

Reads live from the backend, with filtering, search, CSV export, and the
reviewer history shown alongside each verdict (the human actions logged in
step 4). This is the "show a regulator" view: a filterable, exportable trail.
"""
from __future__ import annotations

import csv
import io

import streamlit as st

import api_client as api

st.set_page_config(page_title="Audit Log", page_icon="list", layout="wide")
api.sign_in_widget()
st.title("Audit log")
st.caption("Every verdict, newest first - append-only")

try:
    entries = api.list_audit(500)
except Exception as e:  # noqa: BLE001
    st.error(f"Cannot load the audit log: {e}")
    st.stop()

if not entries:
    st.info("No verdicts logged yet. Run a check to populate the log.")
    st.stop()

# --- Filters ---
f1, f2, f3 = st.columns([1.2, 1.2, 2])
with f1:
    verdicts = st.multiselect("Verdict", ["APPROVED", "FLAGGED", "REJECTED"], default=[])
with f2:
    channels = st.multiselect("Channel", sorted({e["channel"] for e in entries}), default=[])
with f3:
    query = st.text_input("Search content or reference", placeholder="e.g. Havells, or AUD-…")

def _match(e: dict) -> bool:
    if verdicts and e["verdict"] not in verdicts:
        return False
    if channels and e["channel"] not in channels:
        return False
    if query:
        q = query.lower()
        if q not in (e.get("content") or "").lower() and q not in e["audit_reference"].lower():
            return False
    return True

filtered = [e for e in entries if _match(e)]
st.write(f"Showing **{len(filtered)}** of {len(entries)} verdicts")

# --- Table ---
table = [
    {
        "ref": e["audit_reference"],
        "verdict": e["verdict"],
        "channel": e["channel"],
        "segment": e["audience_segment"],
        "consent": e["consent_rate"],
        "violations": len(e.get("violations", [])),
        "reviews": len(e.get("reviews", [])),
        "corpus": e["rule_corpus_version"],
        "time": e["timestamp"],
    }
    for e in filtered
]
st.dataframe(table, use_container_width=True, hide_index=True)

# --- CSV export ---
def _build_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["audit_reference", "timestamp", "verdict", "confidence", "channel",
                "audience_segment", "consent_rate", "violations", "rule_corpus_version",
                "content", "reviews"])
    for e in rows:
        review_summary = "; ".join(
            f"{r['action']} by {r['reviewer']} ({r.get('justification','')})"
            for r in e.get("reviews", [])
        )
        w.writerow([
            e["audit_reference"], e["timestamp"], e["verdict"], e.get("confidence"),
            e["channel"], e["audience_segment"], e["consent_rate"],
            len(e.get("violations", [])), e["rule_corpus_version"],
            (e.get("content") or "").replace("\n", " "), review_summary,
        ])
    return buf.getvalue()

st.download_button(
    "Download filtered audit report (CSV)",
    data=_build_csv(filtered),
    file_name="compliance_audit_report.csv",
    mime="text/csv",
    disabled=not filtered,
)

# --- Entry detail ---
st.divider()
st.subheader("Entry detail")
if filtered:
    ref = st.selectbox("Select a reference", [e["audit_reference"] for e in filtered])
    detail = next((e for e in filtered if e["audit_reference"] == ref), None)
    if detail:
        st.markdown(f"**Verdict:** {detail['verdict']} · **corpus** {detail['rule_corpus_version']}")
        st.markdown(f"**Content:** {detail.get('content') or '-'}")
        if detail.get("violations"):
            st.markdown("**Violations**")
            for vio in detail["violations"]:
                st.markdown(f"- **{vio['severity']}** · {vio['citation']} - {vio['explanation']}")
        if detail.get("reviews"):
            st.markdown("**Human review history** (logged alongside the original verdict)")
            for r in detail["reviews"]:
                st.markdown(
                    f"- `{r['action']}` by **{r['reviewer']}** at {r['reviewed_at']}"
                    + (f" - {r['justification']}" if r.get("justification") else "")
                )
