"""
Law Amender Page.
Provides an interface for compliance officers to view, edit, and calibrate the rule corpus.
Commits changes directly to the corpus configuration, incrementing its version.
"""
from __future__ import annotations

import os
import sys
import json
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
    page_title="Law Amender — AI Compliance",
    page_icon="⚖️",
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
        color: #EC4899;
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
st.markdown('<div class="title">Rule Corpus Calibration Panel</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Edit compliance rules, alter patterns, calibrate severity classifications, and amend versioned law guidelines.</div>', unsafe_allow_html=True)

# Auth Check
is_officer = (role == "compliance_officer")
if is_officer:
    st.success(f"🔓 Authenticated as **{name}** (Compliance Officer / Admin). You are authorized to amend rule configurations.")
else:
    st.warning("🔒 Signed in as **Marketer**. You are in read-only mode. Swap roles in the sidebar to commit rule modifications.")

# Determine corpus file path
rules_dir = os.getenv("RULES_DIR", "app/data/rules")
corpus_file_path = Path(rules_dir) / "corpus.json"

# Load current corpus JSON
def load_corpus() -> dict:
    try:
        with open(corpus_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading rule corpus: {e}")
        st.stop()

corpus_data = load_corpus()
current_version = corpus_data.get("version", "1.0.0")

st.markdown(f"**Current Rule Corpus Version:** `{current_version}`")
st.divider()

# Selection Matrix columns
col_select, col_edit = st.columns([1, 2], gap="large")

with col_select:
    st.markdown("### ⚖️ Target Module Selection")
    
    # Framework selection radio button
    selected_framework = st.radio(
        "Select Regulatory Module",
        options=[
            "DPDP Act 2023",
            "ASCI Guidelines",
            "TRAI Rules",
            "BIS Standards"
        ],
        index=0,
        help="Choose which national or industry guideline standard ruleset to load."
    )
    
    # Map label to JSON key
    framework_mapping = {
        "DPDP Act 2023": "DPDP",
        "ASCI Guidelines": "ASCI",
        "TRAI Rules": "TRAI",
        "BIS Standards": "BIS"
    }
    corpus_key = framework_mapping[selected_framework]
    
    # Select specific Rule
    available_rules = corpus_data.get("sources", {}).get(corpus_key, [])
    if not available_rules:
        st.error(f"No rules found for module: {selected_framework}")
        st.stop()
        
    rule_ids = [r["id"] for r in available_rules]
    selected_rule_id = st.selectbox(
        "Select Rule to Calibrate",
        options=rule_ids,
        help="Select a specific rule sub-clause to edit."
    )
    
    # Get active rule data
    active_rule = next(r for r in available_rules if r["id"] == selected_rule_id)
    
    st.markdown("---")
    st.markdown("#### 🔍 Active Rule Snapshot")
    st.json(active_rule)

with col_edit:
    st.markdown(f"### ✏️ Edit Rule: {selected_rule_id}")
    
    # Form input fields for rule specifications
    edited_pattern = st.text_input(
        "Regex Matching Pattern",
        value=active_rule.get("pattern", ""),
        help="The regular expression pattern matched against campaign copy text.",
        disabled=not is_officer
    )
    
    edited_citation = st.text_input(
        "Legal Clause Citation Reference",
        value=active_rule.get("citation", ""),
        help="Official text/reference reference (e.g. DPDP Act 2023, Section 6).",
        disabled=not is_officer
    )
    
    edited_explanation = st.text_area(
        "Violation Explanation Description",
        value=active_rule.get("explanation", ""),
        height=100,
        help="Plain-English explanation shown to users when this rule triggers.",
        disabled=not is_officer
    )
    
    edited_fix = st.text_area(
        "Remediation Suggested Fix",
        value=active_rule.get("suggested_fix", ""),
        height=100,
        help="Clear instructions on how to resolve this violation.",
        disabled=not is_officer
    )
    
    # Severity Slider (Low -> Medium -> High -> Critical)
    severity_order = ["Low", "Medium", "High", "Critical"]
    current_severity = active_rule.get("severity", "Medium")
    # Ensure value exists in list or default to Medium
    if current_severity not in severity_order:
        current_severity = "Medium"
        
    edited_severity = st.select_slider(
        "Alter Severity Classification",
        options=severity_order,
        value=current_severity,
        help="Determines compliance severity rating.",
        disabled=not is_officer
    )
    
    st.markdown("---")
    
    # Version Increment & Save Button
    if is_officer:
        commit_btn = st.button("💾 Commit Rule Version Amendment", type="primary", use_container_width=True)
        
        if commit_btn:
            # 1. Update the rule in-memory
            for r in corpus_data["sources"][corpus_key]:
                if r["id"] == selected_rule_id:
                    r["pattern"] = edited_pattern
                    r["citation"] = edited_citation
                    r["explanation"] = edited_explanation
                    r["suggested_fix"] = edited_fix
                    r["severity"] = edited_severity
                    break
            
            # 2. Increment the version string (e.g. 2026.06.1 -> 2026.06.2)
            version_parts = current_version.split(".")
            if len(version_parts) >= 3 and version_parts[-1].isdigit():
                version_parts[-1] = str(int(version_parts[-1]) + 1)
                new_version = ".".join(version_parts)
            else:
                new_version = current_version + ".1"
                
            corpus_data["version"] = new_version
            
            # 3. Write JSON back to file
            try:
                with open(corpus_file_path, "w", encoding="utf-8") as f:
                    json.dump(corpus_data, f, indent=2, ensure_ascii=False)
                
                st.success(
                    f"🎉 Successfully amended ruleset! Corpus version updated to **{new_version}**.\n\n"
                    "The backend server will automatically hot-reload and clear its evaluation caches."
                )
                # Force reload page to see the new version
                st.rerun()
            except Exception as save_err:
                st.error(f"Failed to commit ruleset to file system: {save_err}")
    else:
        st.info("ℹ️ Editing controls are read-only. Compliance Officer credentials are required to save changes.")
