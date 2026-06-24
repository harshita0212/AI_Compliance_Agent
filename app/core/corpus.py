"""
Single source of truth for the rule corpus.

Loads corpus.json once and indexes every rule by its id so two layers can
share it without re-reading the file:
  - rule_matching  -> uses pattern + severity (DETECTION)
  - citation_generator -> uses citation + explanation + fix (CITATION)

This split is deliberate: detecting that a rule fired and explaining the law
behind it are different jobs, and keeping them apart means the citation logic
can get smarter later without touching the matching logic.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

settings = get_settings()

SOURCES = ["DPDP", "ASCI", "TRAI", "BIS"]


@lru_cache
def _load() -> dict:
    path = Path(settings.RULES_DIR) / "corpus.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def _index() -> dict[str, dict]:
    """rule_id -> rule dict (with its source attached)."""
    idx: dict[str, dict] = {}
    sources = _load().get("sources", {})
    for source, rules in sources.items():
        for rule in rules:
            idx[rule["id"]] = {**rule, "source": source}
    return idx


def version() -> str:
    return _load().get("version", settings.RULE_CORPUS_VERSION)


def rules_for(source: str) -> list[dict]:
    return _load().get("sources", {}).get(source, [])


def get_rule(rule_id: str) -> dict | None:
    return _index().get(rule_id)


def all_rules() -> list[dict]:
    """Every rule across all sources, each with its source attached."""
    return list(_index().values())
