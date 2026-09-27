from wamah.compose import (
    CATEGORIES,
    enumerate_tuples,
    harness_id_for,
    item_id,
    items_per_category,
    total_items,
    verify_tier_counts,
)
from wamah.generators import generate_items, load_seed_items
from wamah.schema import Category


def test_tier_math():
    assert items_per_category(1) == 21
    assert items_per_category(2) == 441
    assert items_per_category(3) == 9261
    assert total_items(2) == 4 * 441


def test_enumerate_unique_and_complete():
    t1 = enumerate_tuples(1)
    assert len(t1) == 21 and len(set(t1)) == 21
    t2 = enumerate_tuples(2)
    assert len(t2) == 441 and len(set(t2)) == 441
    assert all(len(t) == 2 for t in t2)


def test_verify_invariants():
    for x in (1, 2, 3):
        counts = verify_tier_counts(x)
        assert counts["expected"] == 21 ** x
        for cat in CATEGORIES:
            assert counts[cat.value] == 21 ** x


def test_s1_seed_counts_and_ids():
    seeds = load_seed_items()
    assert len(seeds) == 84
    ids = [s.id for s in seeds]
    assert len(set(ids)) == 84
    per_cat = {}
    for s in seeds:
        per_cat[s.category] = per_cat.get(s.category, 0) + 1
    assert all(v == 21 for v in per_cat.values())


def test_s1_harness_roundrobin_covers_all_21():
    seeds = [s for s in load_seed_items() if s.category == Category.Q]
    harnesses = sorted(s.harness for s in seeds)
    assert harnesses == sorted(f"T{i:02d}" for i in range(1, 22))


def test_s2_generation_counts():
    for cat in CATEGORIES:
        items = generate_items(2, cat)
        assert len(items) == 441
        assert len({i.id for i in items}) == 441
        assert all(i.depth == 2 for i in items)


def test_generation_determinism():
    a = generate_items(2, Category.Q)[17]
    b = generate_items(2, Category.Q)[17]
    assert a.model_dump() == b.model_dump()


def test_item_id_format():
    iid = item_id("S2", Category.Q, ("H01", "M20"), "T07")
    assert iid == "S2-Q-H01_M20-T07"
    assert harness_id_for("S2", Category.Q, ("H01", "M20")).startswith("T")


def test_generation_capped_at_s5(tmp_path):
    import pytest
    from wamah.compose import MAX_GENERATED_TIER
    from wamah.generators import write_tier
    assert MAX_GENERATED_TIER == 4
    with pytest.raises(ValueError, match="capped at S4"):
        write_tier(5, tmp_path / "S5")
    with pytest.raises(ValueError, match="capped at S4"):
        generate_items(5, Category.Q)
    assert not (tmp_path / "S5").exists()


def test_s3_full_counts_unique():
    items = generate_items(3, Category.P)
    assert len(items) == 9261
    assert len({i.id for i in items}) == 9261
