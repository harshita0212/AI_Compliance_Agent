"""
Theme and Styling Injection.
Provides a global custom CSS styling injector to give the Streamlit application
an enterprise-grade, dark-mode glassmorphism visual layout with micro-animations.
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st


def inject_premium_css() -> None:
    """
    Injects global CSS overrides from frontend/assets/style.css into the Streamlit session.
    """
    css_path = Path(__file__).parent.parent / "assets" / "style.css"
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        st.markdown(f"<style>\n{css_content}\n</style>", unsafe_allow_html=True)
    except Exception as e:
        # Fallback in case of path loading failures
        st.warning(f"Fallback styling loaded. CSS file not found: {e}")
