"""Tier generation: S1 loads hand-authored seeds, S2+ renders from tuples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from wamah.compose import (
    CATEGORIES,
    SEED_DIR,
    enumerate_tuples,
    endgame_harness_id,
    harness_id_for,
    item_id,
    parse_tier,
    tier_name,
    verify_tier_counts,
)
from wamah.generators.d import render_d
from wamah.generators.p import render_p
from wamah.generators.q import render_q
from wamah.generators.sc import render_sc
from wamah.schema import Category, Item

_RENDERERS = {
    Category.Q: render_q,
    Category.SC: render_sc,
    Category.P: render_p,
    Category.D: render_d,
}

_SEED_FILES = {
    Category.Q: "q.json",
    Category.SC: "sc.json",
    Category.P: "p.json",
    Category.D: "d.json",
}


def load_seed_items() -> list[Item]:
    """Load the 84 hand-authored S1 items (21 per category)."""
    items: list[Item] = []
    for cat, fname in _SEED_FILES.items():
        path = SEED_DIR / "S1" / fname
        if not path.exists():
            raise FileNotFoundError(f"missing S1 seed file: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        for row in raw:
            items.append(Item.model_validate(row))
    return items


def iter_items(x: int, category: Category | None = None, limit: int | None = None) -> Iterator[Item]:
    """Stream items of tier S[x] without materializing them all in memory.

    S4 (777,924 items) makes the old list-based path untenable; this yields
    one item at a time. `limit` caps the yield (per category) for tests/previews.
    The tier cap is checked eagerly, not on first next().
    """
    from wamah.compose import MAX_GENERATED_TIER
    if x > MAX_GENERATED_TIER:
        raise ValueError(
            f"tier S{x} is specified in the WAMAH-S[X] spec but not enabled yet: "
            f"generation is currently capped at S{MAX_GENERATED_TIER} "
            f"(S4 = 777,924 items materialized; S5 = 16,336,404 items, ~21 GB - deferred)"
        )
    return _iter_items(x, category, limit)


def _iter_items(x: int, category: Category | None, limit: int | None) -> Iterator[Item]:
    tier = tier_name(x)
    cats = [category] if category else list(CATEGORIES)
    if x == 1:
        seeds = load_seed_items()
        if category:
            seeds = [i for i in seeds if i.category == category]
        for item in seeds:
            yield item
        return
    verify_tier_counts(x)
    for cat in cats:
        renderer = _RENDERERS[cat]
        n = 0
        for probes in enumerate_tuples(x):
            yield renderer(tier, probes)
            n += 1
            if limit is not None and n >= limit:
                break


def generate_items(x: int, category: Category | None = None) -> list[Item]:
    return list(iter_items(x, category))


def write_tier(x: int, out_dir: Path, category: Category | None = None,
               limit: int | None = None) -> dict[str, Path]:
    """Stream one JSONL file per category to disk (flat memory). Returns {category: path}."""
    from wamah.compose import MAX_GENERATED_TIER
    if x > MAX_GENERATED_TIER:
        raise ValueError(
            f"tier S{x} is specified in the WAMAH-S[X] spec but not enabled yet: "
            f"generation is currently capped at S{MAX_GENERATED_TIER} "
            f"(S4 = 777,924 items materialized; S5 = 16,336,404 items, ~21 GB - deferred)"
        )
    tier = tier_name(x)  # tier label for the renderer
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    cats = [category] if category else list(CATEGORIES)
    for cat in cats:
        path = out_dir / f"{cat.value.lower()}.jsonl"
        n = 0
        with path.open("w", encoding="utf-8") as fh:
            for item in iter_items(x, cat, limit=limit):
                fh.write(item.model_dump_json() + "\n")
                n += 1
        written[cat.value] = path
    return written


def load_tier(tier: str, data_root: Path | None = None) -> list[Item]:
    """Load every item of a tier (seeds or generated). Avoid for S4: use iter_tier."""
    return list(iter_tier(tier, data_root))


def iter_tier(tier: str, data_root: Path | None = None,
              category: Category | None = None) -> Iterator[Item]:
    """Stream every item of a tier without holding the whole tier in memory.

    S4 (777,924 items, ~1.5 GB as pydantic objects) cannot go through load_tier;
    runs and reports consume this iterator instead.
    """
    x = parse_tier(tier)
    if x == 1:
        seeds = generate_items(1)
        for item in seeds:
            if category is None or item.category == category:
                yield item
        return
    root = (data_root or (SEED_DIR.parent)) / "generated" / tier.upper()
    cats = [category] if category else list(CATEGORIES)
    for cat in cats:
        path = root / f"{cat.value.lower()}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"tier {tier} not generated yet: {path}")
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield Item.model_validate_json(line)
