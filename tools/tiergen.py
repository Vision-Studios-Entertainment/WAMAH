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


def _check_file(path: Path, x: int, expected: int, problems: list[str]) -> int:
    """Stream-validate one category file: count, unique ids, tier/depth.
    Only ids are retained, so S4 (194,481 rows) stays flat in memory."""
    if not path.exists():
        problems.append(f"{path} missing")
        return -1
    n = 0
    ids: set[str] = set()
    dup = False
    bad = False
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            n += 1
            row = Item.model_validate_json(line)
            if row.id in ids:
                dup = True
            ids.add(row.id)
            if row.tier.upper() != f"S{x}" or row.depth != x:
                bad = True
    if n != expected:
        problems.append(f"{path.stem}: expected {expected} rows, got {n}")
    if dup:
        problems.append(f"{path.stem}: duplicate item IDs")
    if bad:
        problems.append(f"{path.stem}: bad tier/depth on at least one row")
    return n


def check_tier(x: int, out_dir: Path, category: Category | None) -> int:
    """Validate what was written. Returns 0 on success, 1 otherwise."""
    expected = items_per_category(x)
    cats = [category] if category else list(CATEGORIES)
    problems: list[str] = []
    for cat in cats:
        path = out_dir / f"{cat.value.lower()}.jsonl"
        n = _check_file(path, x, expected, problems)
        if n >= 0:
            print(f"{cat.value}: {n} items -> {path}")
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
    parser.add_argument("--limit", type=int, default=0, metavar="N",
                        help="write only the first N items per category (partial "
                             "generation for previews/CI)")
    args = parser.parse_args(argv)

    cat = _category(args.category)
    out_dir = Path(args.out) / f"S{x}"
    limit = args.limit if args.limit and args.limit > 0 else None
    started = time.perf_counter()
    written = write_tier(x, out_dir, cat, limit=limit)
    elapsed = time.perf_counter() - started
    print(f"wrote {len(written)} file(s) for tier S{x} in {elapsed:.1f}s")
    if limit:
        print(f"partial generation (--limit {limit}): skipping full invariant check")
        return 0
    if args.skip_check:
        return 0
    return check_tier(x, out_dir, cat)


def main(x: int) -> None:
    raise SystemExit(run(x))


if __name__ == "__main__":
    main(2)
