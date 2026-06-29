"""
Analytics & Audit Page.
Displays summary KPIs and an auditing matrix of historical transaction logs.
Allows auditing compliance trends, filtering by date and state, and downloading reports.
"""
from __future__ import annotations

import sys
import datetime
from pathlib import Path

# Add parent directories to sys.path to ensure local imports resolve
parent_dir = str(Path(__file__).parent.absolute())
frontend_dir = str(Path(__file__).parent.parent.absolute())
for p in [parent_dir, frontend_dir]:
    if p not in sys.path:
        sys.path.append(p)

import streamlit as st
import api_client as api

if not st.session_state.get('authenticated', False):
    st.set_page_config(
        page_title="Access Denied — AI Compliance",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.warning("Please sign in to access this operations console.")
    st.stop()

st.set_page_config(
    page_title="Analytics Audit — AI Compliance",
    page_icon="📊",
    layout="wide",
)

from components.style import inject_premium_css
inject_premium_css()

# Custom header styling
st.markdown(
    """
    <style>
    .title {
        font-family: 'Outfit', sans-serif;
        font-size: 2.2rem;
        font-weight: 700;
        color: #6366F1;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        font-size: 1rem;
        color: rgba(255, 255, 255, 0.7);
        margin-bottom: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Authentication and Role Widget in Sidebar
name, role = api.sign_in_widget()

# Header
st.markdown('<div class="title">Compliance Analytics & Audit</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Immutable transaction history logging, metric analytics, and regulatory audit trail reports.</div>', unsafe_allow_html=True)

# Fetch audit log logs
try:
    all_entries = api.list_audit(500)
except Exception as e:
    st.error(f"Cannot load compliance audit log from backend: {e}")
    st.stop()

if not all_entries:
    st.info("No compliance transactions recorded yet. Submit a campaign on the Home page to populate the log.")
    st.stop()

# Helper function to resolve final verdict state from reviews
def get_current_verdict_info(e: dict) -> tuple[str, str]:
    """Returns (verdict_state, user_in_charge)"""
    if not e.get("reviews"):
        return e["verdict"], "System (AI)"
        
    # Get latest review sorted by timestamp
    reviews_sorted = sorted(e["reviews"], key=lambda r: r["reviewed_at"])
    latest_review = reviews_sorted[-1]
    
    action = latest_review["action"]
    reviewer = latest_review["reviewer"]
    
    if action == "override_approve":
        return "APPROVED (Override)", reviewer
    elif action == "reject":
        return "REJECTED (Confirmed)", reviewer
    elif action == "send_back":
        return "FLAGGED (Re-eval)", reviewer
        
    return e["verdict"], reviewer

# ----------------- CALCULATE KPIs (Overall data) -----------------
total_screened = len(all_entries)

# Auto approval rate: campaigns originally APPROVED by AI
auto_approved_count = len([e for e in all_entries if e["verdict"] == "APPROVED"])
auto_approval_rate = (auto_approved_count / total_screened) if total_screened > 0 else 0.0

# Backlog size: FLAGGED and not yet reviewed
flagged_backlog = len([
    e for e in all_entries 
    if e["verdict"] == "FLAGGED" and not e.get("reviews")
])

# Renders Top Metrics Row
kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
kpi_col1.metric("Total Screened Campaigns", f"{total_screened:,}")
kpi_col2.metric("Auto-Approval Rate", f"{auto_approval_rate:.1%}")
kpi_col3.metric("Flagged Queue Backlog", f"{flagged_backlog}", delta="Pending", delta_color="inverse")

st.markdown("---")

# ----------------- SIDEBAR FILTERING PANEL -----------------
st.sidebar.markdown("### 🔍 Filters")

# Collect dates for default bounds
entry_dates = []
for entry in all_entries:
    try:
        # Strip timezone offset or use simple parsing
        ts = entry["timestamp"].split("T")[0]
        dt = datetime.date.fromisoformat(ts)
        entry_dates.append(dt)
    except Exception:
        pass

min_date = min(entry_dates) if entry_dates else datetime.date.today() - datetime.timedelta(days=30)
max_date = max(entry_dates) if entry_dates else datetime.date.today()

# Sidebar date range filter
date_range = st.sidebar.date_input(
    "Date Range Select",
    value=(min_date, max_date),
    min_value=min_date - datetime.timedelta(days=365),
    max_value=max_date + datetime.timedelta(days=30),
    help="Filter transactions by matching timestamps."
)

# Sidebar state multiselect (original and overridden tags)
verdict_choices = ["APPROVED", "FLAGGED", "REJECTED"]
selected_states = st.sidebar.multiselect(
    "Filter State Tags",
    options=verdict_choices,
    default=[],
    help="Matches against the verdict state of the transactions."
)

# ----------------- APPLY FILTERS -----------------
filtered_rows = []
for entry in all_entries:
    # Resolve the active state and user
    curr_state, user_in_charge = get_current_verdict_info(entry)
    
    # 1. State Filter
    if selected_states:
        match_found = False
        for s in selected_states:
            if s in curr_state:
                match_found = True
                break
        if not match_found:
            continue
            
    # 2. Date Filter
    try:
        ts = entry["timestamp"].split("T")[0]
        entry_date = datetime.date.fromisoformat(ts)
        
        if isinstance(date_range, (tuple, list)):
            if len(date_range) == 2:
                if not (date_range[0] <= entry_date <= date_range[1]):
                    continue
            elif len(date_range) == 1:
                if entry_date != date_range[0]:
                    continue
        else:
            if entry_date != date_range:
                continue
    except Exception:
        pass
        
    # Append to filtered
    consent_pct = f"{entry.get('consent_rate', 0.0) * 100:.0f}%" if entry.get("consent_rate") is not None else "100%"
    
    filtered_rows.append({
        "Timestamp": entry["timestamp"].replace("T", " ")[:19],
        "User": user_in_charge,
        "Content Draft": entry.get("content", ""),
        "Consent Rate (%)": consent_pct,
        "Verdict State": curr_state,
        "Rule Corpus Version": entry.get("rule_corpus_version", "N/A"),
        "Ref": entry["audit_reference"]
    })

st.markdown(f"### 📋 Audit Transaction Log Grid ({len(filtered_rows)} entry/entries found)")

# Render table
if filtered_rows:
    st.dataframe(
        filtered_rows,
        use_container_width=True,
        hide_index=True,
        column_order=["Timestamp", "User", "Content Draft", "Consent Rate (%)", "Verdict State", "Rule Corpus Version", "Ref"]
    )
else:
    st.info("No matching audit logs found for the selected date range and filter states.")
