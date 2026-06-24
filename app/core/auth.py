"""
Authentication & role-based access control.

DEMO implementation: a small in-memory user map keyed by API key. In
production this is replaced by the company identity provider (SSO / SAML,
e.g. Okta or Azure AD) and the keys live in a secrets store - never
hardcoded. The structure (a user with a name and a role, resolved from a
request credential) stays the same, so the swap touches only this file.

Roles:
  - marketer            : may submit campaigns and read the log
  - compliance_officer  : may also review (override / reject) flagged campaigns
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException

# DEMO ONLY. Replace with SSO + secrets store in production.
_USERS: dict[str, dict] = {
    "marketer-key": {"name": "Marketer", "role": "marketer"},
    "officer-key": {"name": "Compliance Officer", "role": "compliance_officer"},
}


def get_current_user(x_api_key: str | None = Header(default=None)) -> dict:
    user = _USERS.get(x_api_key or "")
    if user is None:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return user


def require_compliance_officer(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "compliance_officer":
        raise HTTPException(
            status_code=403,
            detail="This action requires the compliance_officer role.",
        )
    return user
