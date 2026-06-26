"""
PII redaction.

Before any campaign text is sent to the external AI (Gemini), we strip out
personal data so it never leaves our system. The compliance check only needs
the wording and the claims - not anyone's real email or phone number - so
replacing PII with placeholders keeps the analysis intact while protecting
personal data. This is the tool practising the data-privacy principle it
enforces (DPDP Act data minimisation).

Scope: this protects data sent to the THIRD-PARTY model. It detects structured
PII (email, phone, Aadhaar, PAN). It does not attempt to detect names, which
have no reliable pattern; that is a known limitation noted in the README.
"""
from __future__ import annotations

import re

# Order matters: more specific / longer patterns first so a later pattern
# does not eat part of an earlier one (e.g. Aadhaar's 12 digits before phone).
_PATTERNS: list[tuple[str, str]] = [
    ("EMAIL", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ("PAN", r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    ("AADHAAR", r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    # Indian mobile / general 10-digit, optional +91 and a single separator.
    ("PHONE", r"(?:\+?91[\-\s]?)?\b\d{5}[\-\s]?\d{5}\b"),
]


def redact(text: str) -> tuple[str, list[str]]:
    """
    Replace PII with [TYPE] placeholders.

    Returns the redacted text and a sorted list of the PII types that were
    found (e.g. ["EMAIL", "PHONE"]), so the system can note on the verdict that
    redaction happened.
    """
    found: set[str] = set()
    redacted = text
    for label, pattern in _PATTERNS:
        def _sub(_m: re.Match, _label=label) -> str:
            found.add(_label)
            return f"[{_label}]"
        redacted = re.sub(pattern, _sub, redacted)
    return redacted, sorted(found)
