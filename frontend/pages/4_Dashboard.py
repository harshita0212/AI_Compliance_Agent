"""
Compliance Dashboard - metrics at a glance, powered by DuckDB.

Audit-log records are loaded into an in-process DuckDB instance and analysed
with SQL: verdict mix, approval rate, top violation types, verdicts by channel,
and check volume over time. DuckDB is fast, in-process, and zero-setup - the
same query engine scales to far larger logs than a Python loop would.
"""
from __future__ import annotations

import duckdb
import streamlit as st

import api_client as api

st.set_page_config(page_title="Dashboard", page_icon="chart", layout="wide")
st.title("Compliance dashboard")
st.caption("Analytics over the audit log (DuckDB)")


def compute_analytics(entries: list[dict]) -> dict:
    """Run the analytical SQL over the audit log. Returns plain dicts."""
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE audit (ref VARCHAR, verdict VARCHAR, channel VARCHAR, "
        "segment VARCHAR, consent DOUBLE, confidence DOUBLE, violations INT, ts VARCHAR)"
    )
    con.execute("CREATE TABLE viols (ref VARCHAR, citation VARCHAR, severity VARCHAR)")

    for e in entries:
        con.execute(
            "INSERT INTO audit VALUES (?,?,?,?,?,?,?,?)",
            [e["audit_reference"], e["verdict"], e["channel"], e["audience_segment"],
             e.get("consent_rate"), e.get("confidence"),
             len(e.get("violations", [])), e["timestamp"]],
        )
        for v in e.get("violations", []):
            con.execute("INSERT INTO viols VALUES (?,?,?)",
                        [e["audit_reference"], v["citation"], v["severity"]])

    total = con.execute("SELECT count(*) FROM audit").fetchone()[0]
    by_verdict = dict(con.execute(
        "SELECT verdict, count(*) FROM audit GROUP BY verdict").fetchall())
    approved = by_verdict.get("APPROVED", 0)
    top_violations = dict(con.execute(
        "SELECT citation, count(*) c FROM viols GROUP BY citation ORDER BY c DESC LIMIT 5"
    ).fetchall())
    by_channel = con.execute(
        "SELECT channel, verdict, count(*) FROM audit GROUP BY channel, verdict "
        "ORDER BY channel"
    ).fetchall()
    over_time = dict(con.execute(
        "SELECT substr(ts,1,10) d, count(*) FROM audit GROUP BY d ORDER BY d"
    ).fetchall())
    con.close()

    return {
        "total": total,
        "by_verdict": by_verdict,
        "approval_rate": (approved / total) if total else 0.0,
        "top_violations": top_violations,
        "by_channel": by_channel,
        "over_time": over_time,
    }


try:
    entries = api.list_audit(1000)
except Exception as e:  # noqa: BLE001
    st.error(f"Cannot load the audit log: {e}")
    st.stop()

if not entries:
    st.info("No data yet. Run some checks to populate the dashboard.")
    st.stop()

a = compute_analytics(entries)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Campaigns checked", a["total"])
c2.metric("Approval rate", f"{a['approval_rate']:.0%}")
c3.metric("Flagged", a["by_verdict"].get("FLAGGED", 0))
c4.metric("Rejected", a["by_verdict"].get("REJECTED", 0))

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Verdict breakdown")
    st.bar_chart({k: a["by_verdict"].get(k, 0) for k in ["APPROVED", "FLAGGED", "REJECTED"]})
with col2:
    st.subheader("Top violation types")
    if a["top_violations"]:
        st.bar_chart(a["top_violations"])
    else:
        st.write("No violations recorded yet.")

col3, col4 = st.columns(2)
with col3:
    st.subheader("Verdicts by channel")
    # Pivot the (channel, verdict, count) rows into a per-channel table.
    pivot: dict[str, dict] = {}
    for channel, verdict, count in a["by_channel"]:
        pivot.setdefault(channel, {"channel": channel, "APPROVED": 0, "FLAGGED": 0, "REJECTED": 0})
        pivot[channel][verdict] = count
    st.dataframe(list(pivot.values()), use_container_width=True, hide_index=True)
with col4:
    st.subheader("Checks over time")
    st.bar_chart(a["over_time"])
