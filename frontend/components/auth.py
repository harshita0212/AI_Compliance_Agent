"""
Authentication Screens & Credential Verification.
Provides the login / registration forms and hash validation logic.
"""
from __future__ import annotations

import streamlit as st
import hashlib
import json
import os
from pathlib import Path

# Paths to data storage
DATA_DIR = Path(__file__).parent.parent / "data"
USERS_FILE = DATA_DIR / "users.json"


def hash_password(password: str, salt: str) -> str:
    """Computes SHA-256 hash of the password combined with salt."""
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def load_users() -> dict:
    """Loads current registered users from JSON database. Seeds defaults if file is missing."""
    if not USERS_FILE.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Seed default demo users
        users = {}
        # Marketer: username "marketer", password "password123"
        marketer_salt = "1234567890abcdef"
        users["marketer"] = {
            "email": "marketer@compliance.ai",
            "password_hash": hash_password("password123", marketer_salt),
            "salt": marketer_salt,
            "role": "marketer"
        }
        # Officer: username "officer", password "password123"
        officer_salt = "abcdef1234567890"
        users["officer"] = {
            "email": "officer@compliance.ai",
            "password_hash": hash_password("password123", officer_salt),
            "salt": officer_salt,
            "role": "compliance_officer"
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4)
        return users
    
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_users(users: dict) -> None:
    """Saves updated user dictionary back to the JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)


def render_auth_gate() -> None:
    """
    Renders the custom Login / Signup tabs inside a premium layout container.
    Blocks page content execution if the user session is unauthenticated.
    """
    users = load_users()
    
    # Styled centered branding header
    st.markdown(
        """
        <div style="text-align: center; margin-top: 5vh; margin-bottom: 2vh;">
            <h1 style="font-family: 'Outfit', sans-serif; font-size: 2.6rem; font-weight: 800; background: linear-gradient(135deg, #6366F1 0%, #EC4899 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -0.02em;">
                🛡️ AI Compliance Agent
            </h1>
            <p style="font-family: 'Inter', sans-serif; color: #94A3B8; font-size: 1.1rem; margin-top: 0.2rem; font-weight: 400;">
                Enterprise Security Gateway & Automated Legal Workspace
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    # Centering columns
    _, col, _ = st.columns([1, 1.8, 1])
    
    with col:
        st.markdown('<div class="login-card-container">', unsafe_allow_html=True)
        tab_login, tab_signup = st.tabs(["🔒 Sign In", "📝 Create Account"])
        
        with tab_login:
            st.markdown("<br>", unsafe_allow_html=True)
            username = st.text_input("Username", key="login_username", placeholder="Enter username (e.g., marketer, officer)")
            password = st.text_input("Password", type="password", key="login_password", placeholder="Enter password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Sign In", type="primary", use_container_width=True, key="login_btn"):
                username_clean = username.strip().lower()
                if not username_clean or not password:
                    st.error("Please enter both username and password.")
                elif username_clean not in users:
                    st.error("Username not found.")
                else:
                    user_data = users[username_clean]
                    pwd_hash = hash_password(password, user_data["salt"])
                    if pwd_hash == user_data["password_hash"]:
                        st.session_state["authenticated"] = True
                        st.session_state["user_name"] = username_clean
                        st.session_state["user_role"] = user_data["role"]
                        st.success("Successfully authenticated! Launching terminal workspace...")
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
                        
        with tab_signup:
            st.markdown("<br>", unsafe_allow_html=True)
            new_email = st.text_input("Email Address", key="signup_email", placeholder="Enter email (e.g., user@company.com)")
            new_username = st.text_input("Username", key="signup_username", placeholder="Enter desired username")
            new_password = st.text_input("Password", type="password", key="signup_password", placeholder="Choose password (min 6 characters)")
            confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm_password", placeholder="Re-enter password")
            
            new_role_display = st.selectbox(
                "Assign Account Role", 
                options=["Marketer", "Compliance Officer"], 
                key="signup_role",
                help="Determines your access level and verification signature privileges."
            )
            new_role = "compliance_officer" if new_role_display == "Compliance Officer" else "marketer"
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Create Account", type="primary", use_container_width=True, key="signup_btn"):
                email_clean = new_email.strip()
                username_clean = new_username.strip().lower()
                
                # Perform registrations and credentials verification checks
                if not email_clean or not username_clean or not new_password or not confirm_password:
                    st.error("All registration fields are required.")
                elif "@" not in email_clean:
                    st.error("Invalid email address format.")
                elif not username_clean.isalnum() or len(username_clean) < 3:
                    st.error("Username must be alphanumeric and at least 3 characters.")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif username_clean in users:
                    st.error("Username already exists. Please choose a different one.")
                else:
                    # Save registration records securely using salt
                    salt = os.urandom(16).hex()
                    users[username_clean] = {
                        "email": email_clean,
                        "password_hash": hash_password(new_password, salt),
                        "salt": salt,
                        "role": new_role
                    }
                    save_users(users)
                    st.success(f"Account for '{new_username}' created successfully! You can now sign in.")
                    
        st.markdown('</div>', unsafe_allow_html=True)
