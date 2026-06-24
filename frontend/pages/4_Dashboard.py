"""
Compliance Dashboard — metrics at a glance.

Shows basic counts computed from the audit log now. The richer analytics
(top violation types over time, channel breakdowns via DuckDB) arrive in step 6.
"""
from __future__ import annotations

from collections import Counter

import streamlit as st

import api_client as api

st.set_page_config(page_title="Dashboard", page_icon="chart", layout="wide")
st.title("Compliance dashboard")

try:
    entries = api.list_audit(500)
except Exception as e:  # noqa: BLE001
    st.error(f"Cannot load the audit log: {e}")
    st.stop()

if not entries:
    st.info("No data yet. Run some checks to populate the dashboard.")
    st.stop()

total = len(entries)
counts = Counter(e["verdict"] for e in entries)
approved = counts.get("APPROVED", 0)
approval_rate = approved / total if total else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Campaigns checked", total)
c2.metric("Approval rate", f"{approval_rate:.0%}")
c3.metric("Flagged", counts.get("FLAGGED", 0))
c4.metric("Rejected", counts.get("REJECTED", 0))

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Verdict breakdown")
    st.bar_chart({k: counts.get(k, 0) for k in ["APPROVED", "FLAGGED", "REJECTED"]})

with col2:
    st.subheader("Top violation types")
    cites = Counter(
        vio["citation"] for e in entries for vio in e.get("violations", [])
    )
    if cites:
        st.bar_chart(dict(cites.most_common(5)))
    else:
        st.write("No violations recorded yet.")

st.caption("Full analytics (trends over time, channel breakdowns via DuckDB) arrive in step 6.")
