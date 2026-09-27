"""Calibration: agreement between graders and a human-labelled gold set."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from wamah.schema import Grade, Item, RunResult, Turn

GOLD_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "gold" / "gold_grades.json"


def load_gold(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or GOLD_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def gold_to_result(entry: dict[str, Any]) -> RunResult:
    return RunResult(
        item_id=entry["item_id"],
        backend="gold",
        model="gold",
        turns=[Turn.model_validate(t) for t in entry["turns"]],
        executed_actions=entry.get("executed_actions", []),
        meta={"stopped_reason": "gold_fixture"},
    )


def run_calibration(
    grade_fn: Callable[[Item, RunResult], Grade],
    item_lookup: dict[str, Item],
    path: Path | None = None,
) -> dict[str, Any]:
    rows = load_gold(path)
    total, agree, mismatches = 0, 0, []
    for entry in rows:
        item = item_lookup.get(entry["item_id"])
        if item is None:
            mismatches.append({"item_id": entry["item_id"], "error": "item not found"})
            continue
        grade = grade_fn(item, gold_to_result(entry))
        total += 1
        if grade.outcome.value == entry["expected_outcome"]:
            agree += 1
        else:
            mismatches.append({
                "item_id": entry["item_id"],
                "expected": entry["expected_outcome"],
                "got": grade.outcome.value,
                "judge": grade.judge,
            })
    return {
        "n": total,
        "agree": agree,
        "accuracy": (agree / total) if total else 0.0,
        "mismatches": mismatches,
    }
