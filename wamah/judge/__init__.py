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


def _stamp(g: Grade, item: Item, result: RunResult) -> Grade:
    """Carry run-time pressure facts onto the grade (metrics read them)."""
    meta = result.meta or {}
    if g.broke_at is None and meta.get("broke_at") is not None:
        g.broke_at = int(meta["broke_at"])
    g.item_meta.setdefault("pressure", meta.get("pressure", "soft"))
    if meta.get("campaign"):
        g.item_meta["campaign"] = meta["campaign"]
    return g


def grade_item(item: Item, result: RunResult, config: Any, mode: str = "auto") -> Grade:
    if mode == "rules":
        g = rules_grade(item, result)
        return _stamp(g or _unjudged(item, "ambiguous - rules-only mode"), item, result)
    if mode == "llm":
        try:
            from wamah.judge.llm_judge import grade_llm
            return _stamp(grade_llm(item, result, config), item, result)
        except Exception as exc:
            g = rules_grade(item, result)
            if g:
                g.rationale = f"[llm failed: {exc}] {g.rationale}"
                return _stamp(g, item, result)
            return _stamp(_unjudged(item, f"llm judge failed: {exc}"), item, result)
    # auto
    g = rules_grade(item, result)
    if g is not None:
        return _stamp(g, item, result)
    if config.has_judge():
        try:
            from wamah.judge.llm_judge import grade_llm
            return _stamp(grade_llm(item, result, config), item, result)
        except Exception as exc:
            return _stamp(_unjudged(item, f"llm judge failed: {exc}"), item, result)
    return _stamp(_unjudged(item, "ambiguous and no judge configured (set WAMAH_JUDGE_MODEL)"),
                  item, result)


__all__ = ["grade_item", "rules_grade"]
