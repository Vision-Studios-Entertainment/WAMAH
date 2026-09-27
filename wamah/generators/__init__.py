"""Tier generation: S1 loads hand-authored seeds, S2+ renders from tuples."""

from __future__ import annotations

import json
from pathlib import Path

from wamah.compose import (
    CATEGORIES,
    SEED_DIR,
    enumerate_tuples,
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


def generate_items(x: int, category: Category | None = None) -> list[Item]:
    from wamah.compose import MAX_GENERATED_TIER
    if x > MAX_GENERATED_TIER:
        raise ValueError(f"tier S{x} generation is capped at S{MAX_GENERATED_TIER} for now")
    tier = tier_name(x)
    cats = [category] if category else list(CATEGORIES)
    if x == 1:
        seeds = load_seed_items()
        if category:
            seeds = [i for i in seeds if i.category == category]
        return seeds
    verify_tier_counts(x)
    out: list[Item] = []
    renderer = None
    for cat in cats:
        renderer = _RENDERERS[cat]
        for probes in enumerate_tuples(x):
            out.append(renderer(tier, probes))
    return out


def write_tier(x: int, out_dir: Path, category: Category | None = None) -> dict[str, Path]:
    """Write one JSONL file per category. Returns {category: path}."""
    from wamah.compose import MAX_GENERATED_TIER
    if x > MAX_GENERATED_TIER:
        raise ValueError(
            f"tier S{x} is specified in the WAMAH-S[X] spec but not enabled yet: "
            f"generation is currently capped at S{MAX_GENERATED_TIER} "
            f"(S4 = 777,924 items, S5 = 16,336,404 items - deferred)"
        )
    tier = tier_name(x)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    cats = [category] if category else list(CATEGORIES)
    for cat in cats:
        items = generate_items(x, cat)
        path = out_dir / f"{cat.value.lower()}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for item in items:
                fh.write(item.model_dump_json() + "\n")
        written[cat.value] = path
    return written


def load_tier(tier: str, data_root: Path | None = None) -> list[Item]:
    """Load every item of a tier (seeds or generated)."""
    x = parse_tier(tier)
    if x == 1:
        return generate_items(1)
    root = (data_root or (SEED_DIR.parent)) / "generated" / tier.upper()
    items: list[Item] = []
    for cat in CATEGORIES:
        path = root / f"{cat.value.lower()}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"tier {tier} not generated yet: {path}")
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    items.append(Item.model_validate_json(line))
    return items
