"""
Review Queue Page.
Provides a Human-in-the-Loop interface for compliance officers to review,
override, or reject FLAGGED campaigns.
"""
from __future__ import annotations

import sys
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
    page_title="Review Queue — AI Compliance",
    page_icon="📥",
    layout="wide",
)

from components.style import inject_premium_css
inject_premium_css()

# Page-specific styling overrides
st.markdown(
    """
    <style>
    .title {
        font-family: 'Outfit', sans-serif;
        font-size: 2.2rem;
        font-weight: 700;
        color: #F59E0B;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        font-size: 1rem;
        color: rgba(255, 255, 255, 0.7);
        margin-bottom: 2rem;
    }
    .card-meta {
        font-size: 0.85rem;
        color: #A0AEC0;
        margin-bottom: 8px;
    }
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        margin-right: 8px;
    }
    .badge-email { background-color: rgba(99, 102, 241, 0.2); color: #818CF8; border: 1px solid rgba(99, 102, 241, 0.4); }
    .badge-sms { background-color: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge-whatsapp { background-color: rgba(217, 70, 239, 0.2); color: #E879F9; border: 1px solid rgba(217, 70, 239, 0.4); }
    </style>
    """,
    unsafe_allow_html=True,
)

# Authentication and Role Widget in Sidebar
name, role = api.sign_in_widget()


# Header
st.markdown('<div class="title">Review Queue (Human-in-the-Loop)</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Review and override flagged campaigns requiring manual compliance audit trail authorization.</div>', unsafe_allow_html=True)

# User Role Warning / Success
is_officer = (role == "compliance_officer")
if is_officer:
    st.success(f"🔓 Authenticated as **{name}** (Compliance Officer). You have authorization to approve overrides and confirm rejections.")
else:
    st.warning("🔒 Signed in as **Marketer**. You are in read-only mode. Swap roles in the sidebar to perform compliance overrides.")

# Fetch audit logs
try:
    all_entries = api.list_audit(300)
except Exception as e:
    st.error(f"Failed to fetch audit log entries from backend: {e}")
    st.stop()

# Filter for FLAGGED campaigns that have not yet been reviewed (empty reviews list)
pending_campaigns = [
    e for e in all_entries 
    if e["verdict"] == "FLAGGED" and not e.get("reviews")
]

# Display queue status
if not pending_campaigns:
    st.info("🎉 The queue is clean. There are currently no FLAGGED campaigns awaiting review.")
    st.stop()

st.markdown(f"### 📂 Pending Inbox ({len(pending_campaigns)} campaign(s) awaiting action)")

for idx, campaign in enumerate(pending_campaigns):
    ref_id = campaign["audit_reference"]
    timestamp = campaign["timestamp"]
    content_text = campaign.get("content", "")
    channel = campaign.get("channel", "email")
    segment = campaign.get("audience_segment", "N/A")
    violations = campaign.get("violations", [])
    
    # Assign channel badge style
    badge_style = "badge-email"
    if channel.lower() == "sms":
        badge_style = "badge-sms"
    elif channel.lower() == "whatsapp":
        badge_style = "badge-whatsapp"
        
    card_title = f"Campaign Ref: {ref_id} | Created at {timestamp[:19].replace('T', ' ')}"
    
    # Display each pending campaign in an expander card
    with st.expander(card_title, expanded=(idx == 0)):
        col_info, col_viols = st.columns([1, 1], gap="medium")
        
        with col_info:
            st.markdown(f'<span class="badge {badge_style}">{channel}</span> **Segment:** `{segment}`', unsafe_allow_html=True)
            st.markdown("<div style='margin-top: 10px; font-weight: 600;'>Draft Copy:</div>", unsafe_allow_html=True)
            st.markdown(
                f"""
                <div style="
                    background-color: rgba(255, 255, 255, 0.05); 
                    padding: 12px; 
                    border-radius: 8px; 
                    border: 1px solid rgba(255, 255, 255, 0.1); 
                    font-family: 'Inter', sans-serif;
                    white-space: pre-wrap;
                ">{content_text}</div>
                """,
                unsafe_allow_html=True
            )
            
        with col_viols:
            st.markdown("🚨 **Rule Warnings & Citations:**")
            if campaign.get("notes"):
                st.caption(f"**Notes:** {campaign['notes']}")
                
            if violations:
                for vio in violations:
                    st.markdown(
                        f"""
                        <div style="margin-bottom: 8px; padding-left: 8px; border-left: 2px solid #EF4444;">
                            <div style="font-weight:600; font-size: 13px;">{vio['rule_source']} — {vio['citation']} ({vio['severity']})</div>
                            <div style="font-size: 12px; color: #CBD5E0;">Trigger: "{vio['triggering_text']}"</div>
                            <div style="font-size: 12px; color: #A0AEC0;">Reason: {vio['explanation']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                st.write("No specific code triggers captured. Auto-flagged via safety override or system exception.")
        
        st.markdown("---")
        
        # Action controls inside each card
        if not is_officer:
            st.caption("🔒 Actions locked. Sign in as a compliance officer to perform overrides.")
        else:
            justification = st.text_input(
                "✍️ Reviewer Justification Notes",
                key=f"notes_{ref_id}",
                placeholder="State the justification reason for this override or rejection action...",
            )
            
            btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])
            
            def handle_resolution(action_name: str, reference: str = ref_id, key_suffix: str = ref_id):
                input_notes = st.session_state.get(f"notes_{key_suffix}", "").strip()
                if not input_notes:
                    st.warning("⚠️ Reviewer Justification Notes are required to commit this action.")
                else:
                    with st.spinner("Submitting review resolution..."):
                        try:
                            api.review(reference, action_name, input_notes)
                            st.success(f"Resolution '{action_name}' logged successfully! Refreshing dashboard...")
                            st.rerun()
                        except Exception as err:
                            st.error(f"Resolution commit failed: {err}")

            with btn_col1:
                st.button(
                    "✅ Approve Override",
                    key=f"approve_{ref_id}",
                    use_container_width=True,
                    on_click=handle_resolution,
                    args=("override_approve",)
                )
                
            with btn_col2:
                st.button(
                    "❌ Confirm Rejection",
                    key=f"reject_{ref_id}",
                    use_container_width=True,
                    on_click=handle_resolution,
                    args=("reject",)
                )
