"""
Custom styling for Confidence score meters using SVG and CSS.
Provides an elegant, enterprise-grade visual representation of the AI's verdict confidence.
"""
from __future__ import annotations

import streamlit as st


def render_confidence_gauge(confidence: float) -> None:
    """
    Renders a premium circular SVG gauge representing the confidence score.
    
    Args:
        confidence: Float between 0.0 and 1.0 representing the confidence.
    """
    percentage = int(confidence * 100)
    
    # Calculate HSL color dynamically
    # 0% confidence -> Red (0 deg), 100% confidence -> Green (120 deg)
    hue = int(confidence * 120)
    color = f"hsl({hue}, 85%, 45%)"
    glow_color = f"hsla({hue}, 85%, 45%, 0.35)"
    
    # Calculate SVG stroke offset for the circle path
    # Radius = 50, Circumference = 2 * pi * r = 314.16
    circumference = 314.16
    dash_offset = circumference - (confidence * circumference)
    
    gauge_html = f"""
    <div style="
        display: flex; 
        flex-direction: column; 
        align-items: center; 
        justify-content: center; 
        background: rgba(255, 255, 255, 0.05); 
        backdrop-filter: blur(10px); 
        border-radius: 16px; 
        padding: 24px; 
        border: 1px solid rgba(255, 255, 255, 0.1); 
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        max-width: 250px;
        margin: 0 auto;
    ">
        <div style="position: relative; width: 140px; height: 140px;">
            <svg width="140" height="140" viewBox="0 0 120 120" style="transform: rotate(-90deg); filter: drop-shadow(0px 0px 8px {glow_color});">
                <!-- Background Circle -->
                <circle cx="60" cy="60" r="50" 
                        fill="transparent" 
                        stroke="rgba(255, 255, 255, 0.1)" 
                        stroke-width="10" />
                <!-- Foreground Arc -->
                <circle cx="60" cy="60" r="50" 
                        fill="transparent" 
                        stroke="{color}" 
                        stroke-width="10" 
                        stroke-dasharray="{circumference}" 
                        stroke-dashoffset="{dash_offset}" 
                        stroke-linecap="round" 
                        style="transition: stroke-dashoffset 1s ease-in-out;" />
            </svg>
            <div style="
                position: absolute; 
                top: 50%; 
                left: 50%; 
                transform: translate(-50%, -50%); 
                text-align: center;
            ">
                <span style="
                    font-size: 28px; 
                    font-weight: 700; 
                    font-family: 'Outfit', 'Inter', sans-serif; 
                    color: #FFFFFF;
                ">{percentage}%</span>
            </div>
        </div>
        <div style="
            margin-top: 16px; 
            font-size: 14px; 
            font-weight: 600; 
            letter-spacing: 0.05em; 
            text-transform: uppercase; 
            color: #A0AEC0;
            font-family: 'Inter', sans-serif;
        ">
            AI Confidence Score
        </div>
    </div>
    """
    st.markdown(gauge_html, unsafe_allow_html=True)
