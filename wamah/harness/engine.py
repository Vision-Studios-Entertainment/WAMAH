"""Item execution: builds the poisoned context and drives the harness."""

from __future__ import annotations

from typing import Any

from wamah.harness.injection import dataset_context, leading_context
from wamah.harness.multi_turn import drive
from wamah.schema import Category, Item, RunResult


def build_base_messages(item: Item) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    if item.system:
        msgs.append({"role": "system", "content": item.system})
    msgs.extend(leading_context(item))
    ds = dataset_context(item)
    if ds is not None:
        msgs.append(ds)
    return msgs


def run_item(backend: Any, item: Item, config: Any) -> RunResult:
    if hasattr(backend, "begin_item"):
        backend.begin_item(item.id)
    base = build_base_messages(item)
    state = drive(backend, item, base, config)
    error = state.stopped_reason if state.stopped_reason.startswith("backend_error") else None
    return RunResult(
        item_id=item.id,
        backend=getattr(backend, "name", "unknown"),
        model=getattr(backend, "model", "unknown"),
        turns=state.turns,
        executed_actions=state.actions,
        harness_iterations=state.iterations,
        error=error,
        meta={"stopped_reason": state.stopped_reason, "category": item.category.value,
              "harness": item.harness, "last_signal": state.last_signal},
    )
