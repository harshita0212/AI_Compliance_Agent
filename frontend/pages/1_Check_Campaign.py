"""
Check Campaign — the main workflow page.

Submit content + channel + audience, get a verdict with cited violations,
consent summary, and a per-violation Apply Fix that edits the draft in place.
"""
from __future__ import annotations

import streamlit as st

import api_client as api

st.set_page_config(page_title="Check Campaign", page_icon="check", layout="wide")
st.title("Check campaign")

# --- session state ---
if "draft" not in st.session_state:
    st.session_state.draft = (
        "Havells fans - the BEST in India! 100% safe. Buy NOW before stock runs out!"
    )
if "verdict" not in st.session_state:
    st.session_state.verdict = None

_BANNER = {
    "APPROVED": st.success,
    "FLAGGED": st.warning,
    "REJECTED": st.error,
}
_SEV_LABEL = {"Critical": "🔴 Critical", "High": "🟠 High", "Medium": "🟡 Medium", "Low": "⚪ Low"}

# --- input form ---
col1, col2 = st.columns([3, 1])
with col1:
    content = st.text_area("Campaign content", key="draft", height=140)
with col2:
    channel = st.selectbox("Channel", api.CHANNELS)
    segment = st.selectbox("Audience segment", api.KNOWN_SEGMENTS, index=2)

if st.button("Run compliance check", type="primary"):
    if not content.strip():
        st.warning("Enter some campaign content first.")
    else:
        with st.spinner("Checking against DPDP, ASCI, TRAI, BIS…"):
            try:
                st.session_state.verdict = api.check_campaign(content, channel, segment)
            except Exception as e:  # noqa: BLE001
                st.error(f"Check failed: {e}")
                st.session_state.verdict = None

# --- verdict display ---
v = st.session_state.verdict
if v:
    st.divider()
    state = v["verdict"]
    _BANNER.get(state, st.info)(
        f"**{state}**  ·  confidence {v['confidence']:.0%}  ·  ref {v['audit_reference']}"
    )
    if v.get("notes"):
        st.caption(v["notes"])

    # Consent summary
    cs = v.get("consent_summary")
    if cs:
        c1, c2, c3 = st.columns(3)
        c1.metric("Consent rate", f"{cs['consent_rate']:.0%}")
        c2.metric("Audience size", f"{cs['audience_size']:,}")
        c3.metric("Must suppress", f"{cs['must_suppress']:,}")

    # Violations
    violations = v.get("violations", [])
    if violations:
        st.subheader(f"{len(violations)} violation(s)")
        for i, vio in enumerate(violations):
            with st.expander(f"{_SEV_LABEL.get(vio['severity'], vio['severity'])} · {vio['citation']}"):
                st.markdown(f"**Triggered by:** `{vio['triggering_text']}`")
                st.markdown(f"**Why:** {vio['explanation']}")
                st.markdown(f"**Suggested fix:** {vio['suggested_fix']}")
                # Apply Fix only when the flagged phrase actually appears in the draft.
                phrase = vio["triggering_text"]
                if phrase.lower() in st.session_state.draft.lower():
                    if st.button("Apply fix (remove flagged phrase)", key=f"fix_{i}"):
                        draft = st.session_state.draft
                        idx = draft.lower().find(phrase.lower())
                        st.session_state.draft = (draft[:idx] + draft[idx + len(phrase):]).strip()
                        st.session_state.verdict = None
                        st.rerun()
    else:
        st.success("No violations found.")
