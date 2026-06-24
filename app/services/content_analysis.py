"""
Content Analysis layer.

Extracts claims, comparisons, and urgency phrases from campaign text and
returns them as a structured ContentAnalysis artifact that flows through the
pipeline. This is a lightweight keyword pass used for context and the
"no claims extracted" note; the heavier contextual reasoning now lives in the
Gemini detection layer (gemini_matching.py).
"""
from __future__ import annotations

import re

from app.models.schemas import ContentAnalysis

_SUPERLATIVES = r"\b(best|no\.?\s?1|number one|cheapest|safest|fastest|world'?s|india'?s)\b"
_URGENCY = r"\b(now|hurry|last chance|limited|before stock|act fast|today only|ends soon)\b"
_GUARANTEES = r"(100%|\bguaranteed\b|\brisk[- ]?free\b|\balways\b|\bnever fails\b)"


async def analyze(content: str) -> ContentAnalysis:
    text = content.lower()
    return ContentAnalysis(
        claims=re.findall(_SUPERLATIVES, text)
        + [m if isinstance(m, str) else m[0] for m in re.findall(_GUARANTEES, text)],
        comparisons=re.findall(_SUPERLATIVES, text),
        urgency_phrases=re.findall(_URGENCY, text),
    )
