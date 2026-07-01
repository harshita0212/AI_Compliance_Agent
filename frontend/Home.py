"""
Marketer's Workspace — Home Page.
Allows marketers to submit copy, upload files for text extraction, choose target channel and segments,
and view compliance audit scores and suggested remediation.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add parent directories to sys.path to ensure local imports resolve
parent_dir = str(Path(__file__).parent.absolute())
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import streamlit as st
import api_client as api
from components.gauges import render_confidence_gauge
from components.diff_view import render_diff_view

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.set_page_config(
        page_title="Sign In — AI Compliance",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    from components.style import inject_premium_css
    from components.auth import render_auth_gate
    inject_premium_css()
    render_auth_gate()
    st.stop()

st.set_page_config(
    page_title="Marketer's Workspace — AI Compliance",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from components.style import inject_premium_css
inject_premium_css()

# Page-specific header text styling
st.markdown(
    """
    <style>
    .header-title {
        font-family: 'Outfit', sans-serif;
        font-size: 2.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366F1 0%, #EC4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .header-subtitle {
        font-size: 1.1rem;
        color: rgba(255, 255, 255, 0.7);
        margin-bottom: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Authentication and Role Widget in the Sidebar
name, role = api.sign_in_widget()

# Header
st.markdown('<div class="header-title">Marketer\'s Submission Terminal</div>', unsafe_allow_html=True)
st.markdown('<div class="header-subtitle">Analyze copy and content against regulatory corpus (DPDP Act 2023, ASCI, TRAI, BIS)</div>', unsafe_allow_html=True)

# Main container session state init
if "draft" not in st.session_state:
    st.session_state.draft = (
        "Havells fans - the BEST in India! 100% safe. Buy NOW before stock runs out! "
        "By continuing you are automatically subscribed to third-party newsletter partners."
    )
if "verdict" not in st.session_state:
    st.session_state.verdict = None

# Input Columns
col_main, col_options = st.columns([2, 1], gap="large")

with col_main:
    with st.container(border=True):
        # Campaign Text Area Input
        if "pending_draft" in st.session_state:
            st.session_state["draft"] = st.session_state.pop("pending_draft")
        content = st.text_area(
            "📝 Campaign Copywriting Draft",
            key="draft",
            height=180,
            placeholder="Paste your promotional copy or campaign draft here...",
        )
        
        # File Uploader component
        with st.expander("📤 Extract Text from Document (PDF or Image)"):
            uploaded_file = st.file_uploader(
                "Upload file for compliance pre-scanning", 
                type=["pdf", "png", "jpg", "jpeg", "webp"],
                key="file_upload"
            )
            if uploaded_file is not None:
                if st.button("Extract Content", use_container_width=True):
                    with st.spinner("Processing file with OCR/Text parser..."):
                        try:
                            res = api.extract_file(uploaded_file.getvalue(), uploaded_file.name, uploaded_file.type)
                            if res and res.get("text"):
                                st.session_state["pending_draft"] = res["text"]
                                st.session_state.verdict = None
                                st.success(res.get("note", "Text successfully extracted!"))
                                st.rerun()
                            else:
                                st.warning(res.get("note", "No readable text found in document."))
                        except Exception as e:
                            st.error(f"Error reading file: {e}")

with col_options:
    st.markdown("### ⚙️ Channel & Targeting")
    
    # Select Channel (strictly constrained)
    selected_channel = st.selectbox(
        "Select Channel Target",
        options=["Email", "SMS", "WhatsApp","Social Media"],
        index=0,
        help="Target channel specifies which compliance rules will be triggered."
    )
    
    # Map back to lowercase/casing required by the backend
    channel_api_map = {
        "Email": "email",
        "SMS": "sms",
        "WhatsApp": "whatsapp",
        "Social Media": "social_media"
    }
    api_channel = channel_api_map[selected_channel]

    # Select Segment
    selected_segment = st.selectbox(
        "Audience Segment ID",
        options=api.KNOWN_SEGMENTS,
        index=2,
        help="Segments with low consent rates can trigger suppression warning flags."
    )

    st.markdown("---")
    # Execution Trigger Button
    analyze_button = st.button("🔍 Analyze Campaign", type="primary", use_container_width=True)

# API Call and Execution
if analyze_button:
    if not content.strip():
        st.warning("Please provide copywriting draft text to analyze.")
    else:
        with st.spinner("Analyzing compliance and scanning rule matrices..."):
            try:
                # HTTP POST call using api_client wrapper
                verdict_res = api.check_campaign(content, api_channel, selected_segment)
                st.session_state.verdict = verdict_res
            except Exception as e:
                # Fail-safe mode: Catch connection issues/exceptions, auto-flag, and alert user
                st.error(f"Backend API error encountered: {e}")
                st.warning("Degraded mode: Defaulting verdict to FLAGGED for human verification.")
                
                # Mock a FLAGGED verdict to maintain compliance safety
                st.session_state.verdict = {
                    "verdict": "FLAGGED",
                    "confidence": 0.0,
                    "violations": [],
                    "consent_summary": None,
                    "audit_reference": "ERR-FALLBACK",
                    "rule_corpus_version": "Fallback Mode",
                    "notes": f"System Connection Fallback: The API could not be reached. Reason: {type(e).__name__}"
                }

# Render verdict results
v = st.session_state.verdict
if v:
    st.divider()
    
    # Left: Verdict description & details
    # Right: Metric block and Gauge component
    res_col, score_col = st.columns([2, 1])
    
    with res_col:
        state = v["verdict"]
        ref = v["audit_reference"]
        corpus_ver = v["rule_corpus_version"]
        notes = v.get("notes", "")
        
        # Color coding container matching verdict state
        if state == "APPROVED":
            st.markdown(
                f"""<div class="verdict-card verdict-card-approved">
<div class="verdict-card-title">🟢 Campaign APPROVED</div>
<div style="font-size: 1.05rem; line-height: 1.5; color: #E2E8F0;">
No violations were detected in your draft. This campaign is cleared for scheduling.
</div>
<div class="verdict-card-meta">
<strong>Ref ID:</strong> {ref} &nbsp;&bull;&nbsp; <strong>Corpus Version:</strong> {corpus_ver}
</div>
</div>""",
                unsafe_allow_html=True
            )
            
        elif state == "FLAGGED":
            st.markdown(
                f"""<div class="verdict-card verdict-card-flagged">
<div class="verdict-card-title">🟡 Campaign FLAGGED</div>
<div style="font-size: 1.05rem; line-height: 1.5; color: #E2E8F0;">
Potential compliance issues detected. This campaign requires human review.
</div>
{f'<div style="margin-top: 12px; padding: 10px; border-radius: 6px; background-color: rgba(245, 158, 11, 0.08); font-size: 0.95rem; color: #FCD34D;"><strong>Audit Note:</strong> {notes}</div>' if notes else ''}
<div class="verdict-card-meta">
<strong>Ref ID:</strong> {ref} &nbsp;&bull;&nbsp; <strong>Corpus Version:</strong> {corpus_ver}
</div>
</div>""",
                unsafe_allow_html=True
            )
            
        elif state == "REJECTED":
            st.markdown(
                f"""<div class="verdict-card verdict-card-rejected">
<div class="verdict-card-title">🔴 Campaign REJECTED</div>
<div style="font-size: 1.05rem; line-height: 1.5; color: #E2E8F0;">
Critical compliance violations detected. The draft must be modified to satisfy legal frameworks.
</div>
{f'<div style="margin-top: 12px; padding: 10px; border-radius: 6px; background-color: rgba(239, 68, 68, 0.08); font-size: 0.95rem; color: #FCA5A5;"><strong>Reason:</strong> {notes}</div>' if notes else ''}
<div class="verdict-card-meta">
<strong>Ref ID:</strong> {ref} &nbsp;&bull;&nbsp; <strong>Corpus Version:</strong> {corpus_ver}
</div>
</div>""",
                unsafe_allow_html=True
            )
            
        # Consent summaries if returned
        cs = v.get("consent_summary")
        if cs:
            st.markdown("#### 👥 Consent Distribution")
            cs_col1, cs_col2, cs_col3 = st.columns(3)
            cs_col1.metric("Consent Rate", f"{cs['consent_rate']:.0%}")
            cs_col2.metric("Audience Size", f"{cs['audience_size']:,}")
            cs_col3.metric("Suppressed Count", f"{cs['must_suppress']:,}", delta="Excluding", delta_color="inverse")

    with score_col:
        # st.metric block for confidence
        st.metric(
            label="AI Confidence Score", 
            value=f"{v['confidence']:.0%}",
            help="Confidence rating computed by matching layers and database lookups."
        )
        
        # Premium circular gauge from components
        render_confidence_gauge(v["confidence"])

    # Violations & Diff view
    violations = v.get("violations", [])
    if violations:
        st.divider()
        st.markdown(f"### 📋 Violation Details ({len(violations)} match(es))")
        for i, vio in enumerate(violations):
            with st.expander(f"{vio['rule_source']} violation ({vio['severity']}) — {vio['citation']}"):
                st.markdown(f"**Violating Segment:** `{vio['triggering_text']}`")
                st.markdown(f"**Explanation:** {vio['explanation']}")
                st.markdown(f"**Remediation Fix:** {vio['suggested_fix']}")
                
        st.divider()
        # Interactive side-by-side diff view with apply suggestion patcher
        render_diff_view(violations, content)
