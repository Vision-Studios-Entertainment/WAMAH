from wamah.config import RunConfig
from wamah.generators import load_seed_items
from wamah.judge import grade_item
from wamah.judge.calibration import run_calibration

SEEDS = {i.id: i for i in load_seed_items()}


def test_rules_calibration_accuracy():
    result = run_calibration(
        lambda item, res: grade_item(item, res, RunConfig(), mode="rules"),
        SEEDS,
    )
    assert result["n"] >= 12
    assert result["accuracy"] == 1.0, result["mismatches"]


def test_auto_calibration_without_judge():
    result = run_calibration(
        lambda item, res: grade_item(item, res, RunConfig(), mode="auto"),
        SEEDS,
    )
    assert result["accuracy"] == 1.0, result["mismatches"]
