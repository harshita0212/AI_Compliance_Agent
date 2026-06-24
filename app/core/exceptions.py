"""
Domain exceptions. The global handler in main.py catches these and
fails SAFE — degraded conditions become a FLAGGED verdict, never a 500
and never a silent APPROVED. (Suggested change #5)
"""


class ComplianceError(Exception):
    """Base class for all pipeline errors."""


class LLMUnavailableError(ComplianceError):
    """Gemini quota hit, timeout, or malformed response."""


class ConsentStoreUnavailableError(ComplianceError):
    """Consent DB unreachable. Never assume consent — flag instead."""


class RuleCorpusUnavailableError(ComplianceError):
    """One or more rule sources could not be loaded."""
