"""Item execution: builds the poisoned context and drives the harness."""

from __future__ import annotations

from typing import Any

from wamah.harness.injection import dataset_context, leading_context
from wamah.harness.multi_turn import drive
from wamah.schema import Category, Item, RunResult, Turn


def build_base_messages(item: Item) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    if item.system:
        msgs.append({"role": "system", "content": item.system})
    msgs.extend(leading_context(item))
    ds = dataset_context(item)
    if ds is not None:
        msgs.append(ds)
    return msgs


def run_item(backend: Any, item: Item, config: Any,
             prelude: list[dict[str, Any]] | None = None,
             campaign_meta: dict[str, Any] | None = None) -> RunResult:
    """Run one item. `prelude` injects campaign history before this item's
    own context (campaign mode); `campaign_meta` stamps provenance in meta."""
    if hasattr(backend, "begin_item"):
        backend.begin_item(item.id)
    base = build_base_messages(item)
    if prelude:
        base = [dict(m) for m in prelude] + base
    state = drive(backend, item, base, config)
    error = state.stopped_reason if state.stopped_reason.startswith("backend_error") else None
    turns = list(state.turns)
    if prelude:
        # record campaign context for auditability, but under context_* roles so
        # per-item grading (which reads user/assistant turns) is not contaminated
        # by earlier items' replies.
        turns = [Turn(role=f"context_{m.get('role', 'user')}",
                      content=str(m.get("content", ""))) for m in prelude] + turns
    meta = {"stopped_reason": state.stopped_reason, "category": item.category.value,
            "harness": item.harness, "last_signal": state.last_signal,
            "pressure": "hard" if getattr(config, "hard", False) else "soft",
            "phases": state.phases, "counters_used": state.counters_used,
            "broke_at": state.broke_at}
    if item.endgame_harness:
        meta["endgame_harness"] = item.endgame_harness
    if campaign_meta:
        meta.update(campaign_meta)
    return RunResult(
        item_id=item.id,
        backend=getattr(backend, "name", "unknown"),
        model=getattr(backend, "model", "unknown"),
        turns=turns,
        executed_actions=state.actions,
        harness_iterations=state.iterations,
        error=error,
        meta=meta,
    )
