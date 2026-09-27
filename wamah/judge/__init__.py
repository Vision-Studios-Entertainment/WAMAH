"""Grading entrypoint: rules fast path -> LLM judge -> UNJUDGED fallback."""

from __future__ import annotations

from typing import Any

from wamah.judge.rules import rules_grade
from wamah.schema import Grade, Item, Outcome, RunResult


def _unjudged(item: Item, note: str) -> Grade:
    return Grade(
        item_id=item.id, outcome=Outcome.UNJUDGED, rationale=note, judge="none",
        item_meta={
            "tier": item.tier, "category": item.category.value,
            "family": item.family.value, "harness": item.harness,
            "control": item.control, "depth": item.depth, "probes": item.probes,
        },
    )


def grade_item(item: Item, result: RunResult, config: Any, mode: str = "auto") -> Grade:
    if mode == "rules":
        return rules_grade(item, result) or _unjudged(item, "ambiguous - rules-only mode")
    if mode == "llm":
        try:
            from wamah.judge.llm_judge import grade_llm
            return grade_llm(item, result, config)
        except Exception as exc:
            g = rules_grade(item, result)
            if g:
                g.rationale = f"[llm failed: {exc}] {g.rationale}"
                return g
            return _unjudged(item, f"llm judge failed: {exc}")
    # auto
    g = rules_grade(item, result)
    if g is not None:
        return g
    if config.has_judge():
        try:
            from wamah.judge.llm_judge import grade_llm
            return grade_llm(item, result, config)
        except Exception as exc:
            return _unjudged(item, f"llm judge failed: {exc}")
    return _unjudged(item, "ambiguous and no judge configured (set WAMAH_JUDGE_MODEL)")


__all__ = ["grade_item", "rules_grade"]
