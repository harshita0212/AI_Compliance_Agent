"""
Citation Generator layer.

Takes the raw RuleHits from rule matching and attaches the exact legal
reference and a plain-English fix to each one, producing the Violation
objects the user sees.

Guardrail: it never fabricates a citation. Every Violation maps back to a
real, versioned rule in the corpus, looked up by rule_id. If a hit somehow
references an unknown rule, it is dropped rather than given a made-up citation.
"""
from __future__ import annotations

from app.core import corpus
from app.models.schemas import RuleHit, Violation


def generate(hits: list[RuleHit]) -> list[Violation]:
    violations: list[Violation] = []
    for hit in hits:
        rule = corpus.get_rule(hit.rule_id)
        if rule is None:
            # No real rule behind this hit -> do not invent a citation.
            continue
        violations.append(
            Violation(
                severity=hit.severity,
                triggering_text=hit.triggering_text,
                rule_source=hit.rule_source,
                citation=rule["citation"],
                explanation=rule["explanation"],
                suggested_fix=rule["suggested_fix"],
            )
        )
    return violations
