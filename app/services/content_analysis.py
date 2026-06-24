"""
Content Analysis layer.

Extracts claims, comparisons, and urgency phrases from campaign text and
returns them as a structured ContentAnalysis artifact that flows through the
rest of the pipeline (it is no longer discarded). Uses Gemini in production;
ships with a mock so the pipeline runs day one.
"""
from __future__ import annotations

import re

from app.config import get_settings
from app.core.exceptions import LLMUnavailableError
from app.models.schemas import ContentAnalysis

settings = get_settings()

_SUPERLATIVES = r"\b(best|no\.?\s?1|number one|cheapest|safest|fastest|world'?s|india'?s)\b"
_URGENCY = r"\b(now|hurry|last chance|limited|before stock|act fast|today only|ends soon)\b"
_GUARANTEES = r"(100%|\bguaranteed\b|\brisk[- ]?free\b|\balways\b|\bnever fails\b)"


async def analyze(content: str) -> ContentAnalysis:
    if settings.USE_MOCK_LLM:
        return _mock(content)
    return await _gemini(content)


def _mock(content: str) -> ContentAnalysis:
    text = content.lower()
    return ContentAnalysis(
        claims=re.findall(_SUPERLATIVES, text) + [m if isinstance(m, str) else m[0]
                                                   for m in re.findall(_GUARANTEES, text)],
        comparisons=re.findall(_SUPERLATIVES, text),
        urgency_phrases=re.findall(_URGENCY, text),
    )


async def _gemini(content: str) -> ContentAnalysis:
    """Production path. Any failure raises LLMUnavailableError -> FLAGGED upstream."""
    try:
        # TODO: real Gemini call returning JSON, then:
        #   return ContentAnalysis(**json.loads(resp.text))
        raise NotImplementedError("Wire up Gemini here.")
    except Exception as e:  # noqa: BLE001 — fail safe upstream
        raise LLMUnavailableError(str(e)) from e
