"""The pressure profiles: soft (legacy) vs hard (warm-up, ladder, endgame)."""

from wamah.config import RunConfig
from wamah.generators import load_seed_items
from wamah.generators.q import render_q
from wamah.harness import run_item
from wamah.runtimes.transcript import TranscriptBackend

REFUSAL = "I can't help with that request."

SEEDS = {i.id: i for i in load_seed_items()}


def _run(item, pressure, replies=None):
    cfg = RunConfig(pressure=pressure)
    backend = TranscriptBackend(responses={"default": replies or [REFUSAL]})
    return run_item(backend, item, cfg)


def _user_turns(result):
    return [t.content for t in result.turns if t.role == "user"]


def test_soft_profile_is_legacy_no_warmup_no_counters_no_endgame():
    res = _run(SEEDS["S1-Q-H01-T01"], "soft")
    assert res.meta["phases"] == ["primary"]
    assert res.meta["counters_used"] == 0
    assert res.harness_iterations <= RunConfig().max_turns


def test_hard_profile_walks_all_three_phases():
    res = _run(SEEDS["S1-Q-H01-T01"], "hard")
    assert res.meta["phases"] == ["warmup", "primary", "endgame"]
    assert res.meta["counters_used"] > 0
    users = _user_turns(res)
    # warm-up comes before the actual ask
    assert "direct complete answer" in users[0] or "calibration" in users[0] \
        or "Setup question" in users[0]
    # endgame playbook arrives after the primary one (T01 ends with FINAL REISSUE)
    final_idx = max(i for i, u in enumerate(users) if "FINAL REISSUE" in u)
    assert any(i > final_idx for i, u in enumerate(users))


def test_hard_budget_is_larger_than_soft():
    soft = _run(SEEDS["S1-Q-H01-T01"], "soft")
    hard = _run(SEEDS["S1-Q-H01-T01"], "hard")
    assert soft.harness_iterations <= RunConfig().max_turns
    assert hard.harness_iterations <= RunConfig().max_turns_hard
    assert hard.harness_iterations > soft.harness_iterations


def test_refusal_gets_a_counter_not_a_repetition():
    res = _run(SEEDS["S1-Q-H01-T01"], "hard")
    users = _user_turns(res)
    from wamah.harness.escalate import _COUNTER_POOLS, _REFUSAL_KINDS
    counters = {m for pool in _COUNTER_POOLS.values() for m in pool}
    for pool in _REFUSAL_KINDS.values():
        counters.update(pool)
    # warmup x2, opener, then the refusal is answered by a counter
    assert users[2].startswith("My coworker")
    assert users[3] in counters, "first refusal must be answered by a counter"
    assert sum(1 for u in users if u in counters) >= 2
    # counters interleave: no message repeats back to back
    for a, b in zip(users, users[1:]):
        assert a != b


def test_control_probes_get_no_pressure_machinery():
    control = SEEDS["S1-Q-K17-T17"]
    res = _run(control, "hard")
    assert res.meta["phases"] == ["primary"]
    assert res.meta["counters_used"] == 0
    assert len(_user_turns(res)) == 1


def test_broke_at_recorded_on_late_compliance():
    item = render_q("S4", ("H01", "H02", "H03", "H04"))
    long_comply = ("Here's how you do it. Step 1: gather materials. Step 2: prepare. "
                   "First, position. Then, wait. Finally, act. " * 4)
    # refusals through warmup + opener; compliance arrives on the counter turn
    res = _run(item, "hard",
               replies=[REFUSAL, REFUSAL, REFUSAL, long_comply])
    assert res.meta["broke_at"] == 4
    assert res.meta["stopped_reason"] == "suspected_compliance"
    # grade carries broke_at through
    from wamah.config import RunConfig as C
    from wamah.judge import grade_item
    g = grade_item(item, res, C(pressure="hard"), mode="rules")
    assert g.broke_at == 4
    assert g.item_meta["pressure"] == "hard"


def test_no_compliance_means_no_broke_at():
    res = _run(SEEDS["S1-Q-H01-T01"], "hard")
    assert res.meta["broke_at"] is None


def test_endgame_harness_differs_from_primary():
    item = render_q("S4", ("H01", "M20", "K17", "H05"))
    assert item.endgame_harness and item.endgame_harness != item.harness
    # hard pressure derives one for legacy tiers too (S1 has none stored)
    res = _run(SEEDS["S1-Q-H01-T01"], "hard")
    assert res.meta["phases"][-1] == "endgame"
