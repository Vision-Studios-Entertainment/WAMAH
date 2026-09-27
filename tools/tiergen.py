"""Shared driver for the generated tiers (S2 and S3).

Both `tools/make_s2.py` and `tools/make_s3.py` delegate here: they render the
tier from the probe tuples, write one JSONL per category, then check the
defining invariants (21^X rows per category, unique IDs, schema round-trip).

Run either script directly:

    python tools/make_s2.py [--out data/generated] [--category Q]
    python tools/make_s3.py [--out data/generated] [--category Q]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wamah.compose import CATEGORIES, GENERATED_DIR, items_per_category, total_items
from wamah.generators import write_tier
from wamah.schema import Category, Item


def _category(value: str | None) -> Category | None:
    if not value:
        return None
    for cat in CATEGORIES:
        if cat.value.lower() == value.lower():
            return cat
    raise SystemExit(f"unknown category: {value} (choose from {[c.value for c in CATEGORIES]})")


def _read(path: Path) -> list[Item]:
    rows: list[Item] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(Item.model_validate_json(line))
    return rows


def check_tier(x: int, out_dir: Path, category: Category | None) -> int:
    """Validate what was written. Returns 0 on success, 1 otherwise."""
    expected = items_per_category(x)
    cats = [category] if category else list(CATEGORIES)
    problems: list[str] = []
    for cat in cats:
        path = out_dir / f"{cat.value.lower()}.jsonl"
        if not path.exists():
            problems.append(f"{path} missing")
            continue
        rows = _read(path)
        if len(rows) != expected:
            problems.append(f"{cat.value}: expected {expected} rows, got {len(rows)}")
        ids = [r.id for r in rows]
        if len(set(ids)) != len(ids):
            problems.append(f"{cat.value}: duplicate item IDs")
        for row in rows:
            if row.tier.upper() != f"S{x}" or row.depth != x:
                problems.append(f"{cat.value}: bad tier/depth on {row.id}")
                break
        print(f"{cat.value}: {len(rows)} items -> {path}")
    if problems:
        for msg in problems:
            print(f"FAIL {msg}", file=sys.stderr)
        return 1
    if category is None:
        assert expected * len(CATEGORIES) == total_items(x)
        print(f"invariants OK: {expected} per category, {total_items(x)} items total")
    else:
        print(f"invariants OK: {expected} items in {category.value}")
    return 0


def run(x: int, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=f"Generate WAMAH-S{x} ({items_per_category(x)} items per category, "
                    f"{total_items(x)} total) into <out>/S{x}/.")
    parser.add_argument("--out", default=str(GENERATED_DIR),
                        help="output root (default: data/generated)")
    parser.add_argument("--category", default=None, metavar="Q|Sc|P|D",
                        help="generate a single category only")
    parser.add_argument("--skip-check", action="store_true",
                        help="write only, skip the invariant checks")
    args = parser.parse_args(argv)

    cat = _category(args.category)
    out_dir = Path(args.out) / f"S{x}"
    started = time.perf_counter()
    written = write_tier(x, out_dir, cat)
    elapsed = time.perf_counter() - started
    print(f"wrote {len(written)} file(s) for tier S{x} in {elapsed:.1f}s")
    if args.skip_check:
        return 0
    return check_tier(x, out_dir, cat)


def main(x: int) -> None:
    raise SystemExit(run(x))


if __name__ == "__main__":
    main(2)
