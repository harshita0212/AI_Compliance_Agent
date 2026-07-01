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
from app.models.schemas import RuleHit, RuleSource, Severity, Violation

settings = get_settings()

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai  # imported lazily so no key = no import cost
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _build_prompt(content: str) -> str:
    # Some rules are marked keyword-only (gemini: false) because the model tends
    # to over-apply them; those are matched by regex only and kept out of here.
    lines = [
        f"- {r['id']} ({r['source']}, {r['citation']}): {r['explanation']}"
        for r in corpus.all_rules()
        if r.get("gemini", True)
    ]
    rules_block = "\n".join(lines)
    return (
        "You are a marketing-compliance reviewer for India. Below is a list of "
        "compliance rules, each with an ID. Decide which rules the campaign "
        "VIOLATES. Judge meaning and context, not just keywords (e.g. an "
        "unsubstantiated superlative counts even if phrased without the word "
        "'best'; a negated phrase like 'we are not the cheapest' does NOT).\n"
        "Be precise: only flag a rule when the campaign text clearly and "
        "specifically matches it. Do not infer a violation from a generic "
        "sign-up or data-collection phrase, and do not flag several overlapping "
        "rules for the same wording - pick the single most specific rule that "
        "applies.\n\n"
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
        print(f"[GEMINI FAILED] {type(e).__name__}: {e}")
        raise LLMUnavailableError(str(e)) from e

    hits: list[RuleHit] = []
    for item in _parse(raw):
        rule = corpus.get_rule(item.get("rule_id", ""))
        if rule is None:
            continue  # model named a rule that doesn't exist -> ignore, never fabricate
        if not rule.get("gemini", True):
            continue  # keyword-only rule -> the model may not apply it
        hits.append(
            RuleHit(
                rule_id=rule["id"],
                rule_source=RuleSource(rule["source"]),
                severity=Severity(rule["severity"]),
                triggering_text=item.get("triggering_text", "")[:200] or "(contextual match)",
            )
        )
    return hits


def _build_rewrite_prompt(content: str, violations: list[Violation]) -> str:
    # Filter out consent shortfalls from prompt violations
    copy_violations = [v for v in violations if "consent" not in v.citation.lower()]
    
    violations_text = ""
    for idx, vio in enumerate(copy_violations, 1):
        violations_text += (
            f"Violation {idx}:\n"
            f"- Triggering text/phrase: '{vio.triggering_text}'\n"
            f"- Legal source / Citation: {vio.rule_source.value} ({vio.citation})\n"
            f"- Why it violates: {vio.explanation}\n"
            f"- Required remediation: {vio.suggested_fix}\n\n"
        )
        
    return (
        "You are an expert compliance officer and professional copywriter for Indian marketing campaigns.\n"
        "Your task is to rewrite the campaign copywriting draft to make it fully compliant with all regulations "
        "(such as DPDP Act 2023, ASCI, TRAI/TCCCPR, and BIS/BEE) by resolving the compliance violations listed below.\n\n"
        "Here is the original campaign draft:\n"
        "\"\"\"\n"
        f"{content}\n"
        "\"\"\"\n\n"
        "Here are the active compliance violations and the required suggested actions:\n"
        f"{violations_text}"
        "INSTRUCTIONS:\n"
        "1. Rewrite the original text so that all copywriting violations are resolved.\n"
        "2. Keep the rewritten draft as close as possible to the original draft's marketing intent, value proposition, and general structure/length.\n"
        "3. If a disclosure label (e.g., 'Advertisement', '#Ad') is missing for social media channels, insert it at the very beginning of the copy.\n"
        "4. Tone down or remove any absolute guarantees (e.g., replace '100% safe' with appropriate qualified phrasing like 'designed with safety first') and unsubstantiated superlatives (e.g., 'best' -> 'leading').\n"
        "5. Respond with ONLY the rewritten compliant copywriting text. Do NOT include any explanations, introduction, markdown fences, quotes, or conversational preambles. Output ONLY the raw final copy."
    )


async def rewrite(content: str, violations: list[Violation]) -> str:
    # Only rewrite if there are copy violations
    copy_violations = [v for v in violations if "consent" not in v.citation.lower()]
    if not copy_violations:
        return content

    prompt = _build_rewrite_prompt(content, violations)
    try:
        raw = await asyncio.to_thread(_call_gemini, prompt)
        # Strip any formatting/markdown fences the model might return
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:text|markdown)?|```$", "", cleaned, flags=re.MULTILINE).strip()
        # Strip outer quotes if any
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()
        return cleaned
    except Exception as e:
        print(f"[GEMINI REWRITE FAILED] {type(e).__name__}: {e}")
        raise LLMUnavailableError(str(e)) from e

