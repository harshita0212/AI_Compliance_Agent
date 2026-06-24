"""
Gemini detection layer.

A second detector that runs ALONGSIDE the keyword matcher. It hands Gemini
the campaign text plus the rule corpus (as plain-English descriptions, not
regex) and asks which rules are violated, so it can catch context that
keyword matching misses (e.g. a superlative phrased without the trigger word).

It returns RuleHit objects in the same shape as the keyword matcher, so the
two sets can be merged. Citations are NOT taken from Gemini — they are looked
up from the corpus by rule_id, so the legal references stay controlled and the
model cannot fabricate a citation.

If Gemini is unavailable (no key, quota, network blocked), this raises
LLMUnavailableError and the orchestrator falls back to keyword-only results.
"""
from __future__ import annotations

import asyncio
import json
import re

from app.config import get_settings
from app.core import corpus
from app.core.exceptions import LLMUnavailableError
from app.models.schemas import RuleHit, RuleSource, Severity

settings = get_settings()

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai  # imported lazily so no key = no import cost
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _build_prompt(content: str) -> str:
    lines = [
        f"- {r['id']} ({r['source']}, {r['citation']}): {r['explanation']}"
        for r in corpus.all_rules()
    ]
    rules_block = "\n".join(lines)
    return (
        "You are a marketing-compliance reviewer for India. Below is a list of "
        "compliance rules, each with an ID. Decide which rules the campaign "
        "VIOLATES. Judge meaning and context, not just keywords (e.g. an "
        "unsubstantiated superlative counts even if phrased without the word "
        "'best'; a negated phrase like 'we are not the cheapest' does NOT).\n\n"
        f"RULES:\n{rules_block}\n\n"
        f"CAMPAIGN:\n\"\"\"\n{content}\n\"\"\"\n\n"
        "Return ONLY a JSON array, no prose, no markdown fences. Each item: "
        '{\"rule_id\": \"<id from the list>\", \"triggering_text\": \"<the exact '
        'phrase from the campaign>\"}. If nothing is violated, return [].'
    )


def _call_gemini(prompt: str) -> str:
    """Isolated so it can be mocked in tests. Returns the raw model text."""
    client = _get_client()
    resp = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )
    return resp.text or "[]"


def _parse(raw: str) -> list[dict]:
    text = raw.strip()
    # Strip accidental markdown fences.
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    # Grab the first JSON array if the model added stray text.
    m = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if m:
        text = m.group(0)
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


async def detect(content: str) -> list[RuleHit]:
    try:
        raw = await asyncio.to_thread(_call_gemini, _build_prompt(content))
    except Exception as e:  # noqa: BLE001 — any SDK/network/quota error degrades safely
        raise LLMUnavailableError(str(e)) from e

    hits: list[RuleHit] = []
    for item in _parse(raw):
        rule = corpus.get_rule(item.get("rule_id", ""))
        if rule is None:
            continue  # model named a rule that doesn't exist -> ignore, never fabricate
        hits.append(
            RuleHit(
                rule_id=rule["id"],
                rule_source=RuleSource(rule["source"]),
                severity=Severity(rule["severity"]),
                triggering_text=item.get("triggering_text", "")[:200] or "(contextual match)",
            )
        )
    return hits
