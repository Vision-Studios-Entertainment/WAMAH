from wamah.alphabet import (
    FAMILY_COUNTS,
    HARNESS_LIST,
    PROBE_LIST,
    human_harm_share,
)
from wamah.schema import Family


def test_exactly_21_probes():
    assert len(PROBE_LIST) == 21
    assert len({p.id for p in PROBE_LIST}) == 21


def test_human_harm_dominates():
    assert FAMILY_COUNTS[Family.HARM] == 12
    assert FAMILY_COUNTS[Family.CRIME] == 4
    assert FAMILY_COUNTS[Family.CTRL] == 3
    assert FAMILY_COUNTS[Family.META] == 2
    # human harm is the most traveled topic: >50% at depth 1, >80% at depth 2
    assert human_harm_share(1) > 0.5
    assert human_harm_share(2) > 0.8


def test_probe_payloads_complete():
    for p in PROBE_LIST:
        assert p.ask and p.hijack_hook and p.murder_criterion
        assert 1 <= p.severity <= 5
        if p.family == Family.CTRL:
            assert p.control
        else:
            assert not p.control


def test_exactly_21_harnesses():
    assert len(HARNESS_LIST) == 21
    assert len({h.id for h in HARNESS_LIST}) == 21
    for h in HARNESS_LIST:
        assert h.mechanism and h.escape_rule
        assert len(h.playbook) >= 1
        assert 1 <= h.intensity <= 5


def test_signature_trap_exists():
    names = {h.name for h in HARNESS_LIST}
    assert {"LOOP", "REGRESS", "SUFFERING", "DILEMMA"} <= names
