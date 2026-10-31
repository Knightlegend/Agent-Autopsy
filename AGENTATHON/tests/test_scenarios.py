"""Unit tests for ScenarioManager and deterministic fault scenarios (S1-S6)."""

import pytest
from src.runner.scenario_mgr import ScenarioManager


@pytest.fixture
def scenario_mgr() -> ScenarioManager:
    return ScenarioManager()


def test_scenario_s1_happy_path(scenario_mgr: ScenarioManager):
    """Verify S1: agent fixes the discount bug and passes tests."""
    eval_result, recorder = scenario_mgr.run_scenario("S1")
    assert eval_result.passed is True
    assert len(eval_result.failures) == 0

    # Verify trace integrity
    is_valid, err = recorder.verify_trace()
    assert is_valid is True
    assert err is None


def test_scenario_s2_incorrect_modification(scenario_mgr: ScenarioManager):
    """Verify S2: unexpected modification detected."""
    eval_result, recorder = scenario_mgr.run_scenario("S2")
    assert eval_result.passed is True
    assert any(a["assertion"] == "unexpected_file_modified" and a["passed"] for a in eval_result.assertions)


def test_scenario_s3_test_failure(scenario_mgr: ScenarioManager):
    """Verify S3: test failure detected without false completion."""
    eval_result, recorder = scenario_mgr.run_scenario("S3")
    assert eval_result.passed is True


def test_scenario_s4_regression(scenario_mgr: ScenarioManager):
    """Verify S4: regression introduced in average is caught."""
    eval_result, recorder = scenario_mgr.run_scenario("S4")
    assert eval_result.passed is True
    assert any(a["assertion"] == "regression_detected" and a["passed"] for a in eval_result.assertions)


def test_scenario_s5_infinite_loop(scenario_mgr: ScenarioManager):
    """Verify S5: infinite repetitive tool loop is intercepted and halted."""
    eval_result, recorder = scenario_mgr.run_scenario("S5")
    assert eval_result.passed is True
    assert any(a["assertion"] == "loop_detected" and a["passed"] for a in eval_result.assertions)


def test_scenario_s6_permission_violation(scenario_mgr: ScenarioManager):
    """Verify S6: path traversal attempt is blocked by security boundary."""
    eval_result, recorder = scenario_mgr.run_scenario("S6")
    assert eval_result.passed is True
    assert any(a["assertion"] == "path_traversal_blocked" and a["passed"] for a in eval_result.assertions)

