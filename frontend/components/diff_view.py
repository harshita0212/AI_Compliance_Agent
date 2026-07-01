"""
Interactive Diff View Component.
Renders a side-by-side split container comparing violating phrases against suggested fixes.
"""
from __future__ import annotations

import re
import streamlit as st
import api_client as api


def render_diff_view(violations: list[dict], current_text: str, channel: str, audience_segment: str) -> None:
    """
    Renders a side-by-side split container showing violating phrases and suggested fixes.
    Includes a button to apply the suggestions back to the text area.
    
    Args:
        violations: List of violation dicts returned by the backend.
        current_text: The current campaign copy text from the text area.
        channel: The channel for remediation.
        audience_segment: The audience segment for remediation.
    """
    if not violations:
        return

    st.markdown("### 🔍 Compliance Remediation & Suggestions")
    
    # Custom CSS for the diff boxes
    st.markdown(
        """
        <style>
        .diff-container {
            display: flex;
            gap: 16px;
            margin-bottom: 12px;
            width: 100%;
        }
        .diff-box {
            flex: 1;
            padding: 16px 20px;
            border-radius: 10px;
            font-size: 14px;
            line-height: 1.5;
            font-family: 'Inter', sans-serif;
            border: 1px solid transparent;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15);
        }
        .diff-violating {
            background-color: rgba(239, 68, 68, 0.22) !important;
            border-color: rgba(239, 68, 68, 0.6) !important;
            color: #FFA3A3 !important;
        }
        .diff-suggested {
            background-color: rgba(16, 185, 129, 0.22) !important;
            border-color: rgba(16, 185, 129, 0.6) !important;
            color: #A3FFC2 !important;
        }
        .diff-label {
            font-weight: 700;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
            color: rgba(255, 255, 255, 0.7);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    valid_fixes = 0

    for i, vio in enumerate(violations):
        trigger = vio.get("triggering_text", "")
        fix = vio.get("suggested_fix", "")
        citation = vio.get("citation", "Violation")
        explanation = vio.get("explanation", "")
        
        if not trigger or not fix:
            continue

        valid_fixes += 1
        
        st.markdown(f"**Violation {i+1}:** {citation} — *{explanation}*")
        
        # HTML Diff side-by-side
        diff_html = f"""
        <div class="diff-container">
            <div class="diff-box diff-violating">
                <div class="diff-label">⚠️ Violating Phrase</div>
                <div>{trigger}</div>
            </div>
            <div class="diff-box diff-suggested">
                <div class="diff-label">✅ Suggested Fix</div>
                <div>{fix}</div>
            </div>
        </div>
        """
        st.markdown(diff_html, unsafe_allow_html=True)
        st.caption("")

    if valid_fixes > 0:
        # Action button to apply suggestions
        if st.session_state.get("gemini_enabled", False):
            if st.button("✨ Apply Suggestions", type="primary", use_container_width=True, key="apply_all_suggestions"):
                with st.spinner("Generating AI compliance rewrite..."):
                    try:
                        res = api.remediate_campaign(current_text, channel, audience_segment)
                        st.session_state["pending_draft"] = res["suggested_rewrite"]
                        
                        if "backend_response" in st.session_state:
                            st.session_state["backend_response"] = None
                        else:
                            st.session_state["verdict"] = None
                            
                        st.success("Suggestions successfully applied! Re-analyze the campaign to confirm compliance.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to generate remediation: {e}")
        else:
            st.warning("⚠️ AI Auto-Remediation Offline. Please configure GEMINI_API_KEY in .env to enable compliance rewriting.")
