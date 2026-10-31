"""Unit tests for core Pydantic data contracts and cryptographic hash chaining."""

import pytest
from pydantic import ValidationError
from src.core.contracts import (
    AgentPolicy,
    AgentProfile,
    Diagnosis,
    EvaluationResult,
    ExecutionEvent,
    PolicyPatch,
    TestCase,
    verify_trace_integrity,
)


def test_agent_profile_validation():
    """Verify valid and invalid AgentProfile instantiation."""
    profile = AgentProfile(
        agent_id="test-agent-01",
        name="Test Coding Agent",
        model_provider="mock",
        model_name="mock-model",
        available_tools=["list_files", "read_file"],
        capabilities=["coding"],
        constraints=["sandboxed"],
    )
    assert profile.agent_id == "test-agent-01"
    assert profile.name == "Test Coding Agent"
    assert "list_files" in profile.available_tools

    # Rejection of empty strings
    with pytest.raises(ValidationError):
        AgentProfile(
            agent_id="",
            name="Valid Name",
            model_provider="mock",
            model_name="mock-model",
        )


def test_test_case_validation():
    """Verify TestCase validation and severity typing."""
    tc = TestCase(
        test_id="TC-01",
        scenario_id="S1",
        category="bug_fix",
        task="Fix discount bug",
        expected_behaviour="All tests pass",
        severity="medium",
    )
    assert tc.test_id == "TC-01"
    assert tc.severity == "medium"

    with pytest.raises(ValidationError):
        TestCase(
            test_id="TC-02",
            scenario_id="S1",
            category="bug_fix",
            task="Task",
            expected_behaviour="Pass",
            severity="unsupported_severity",  # type: ignore
        )


def test_execution_event_hash_chain_and_tamper_detection():
    """Verify cryptographic hash chaining and tamper detection in execution traces."""
    event1 = ExecutionEvent(
        run_id="run-101",
        event_id="evt-1",
        sequence_number=0,
        agent_id="agent-01",
        event_type="agent_start",
        output="Starting run",
    ).seal()

    event2 = ExecutionEvent(
        run_id="run-101",
        event_id="evt-2",
        sequence_number=1,
        agent_id="agent-01",
        event_type="tool_call",
        tool_name="list_files",
        input={"directory": "."},
    ).seal(previous_hash=event1.event_hash)

    event3 = ExecutionEvent(
        run_id="run-101",
        event_id="evt-3",
        sequence_number=2,
        agent_id="agent-01",
        event_type="agent_completion",
        output="Completed",
    ).seal(previous_hash=event2.event_hash)

    events = [event1, event2, event3]

    # Trace integrity must pass
    is_valid, err = verify_trace_integrity(events)
    assert is_valid is True
    assert err is None

    # Tamper with event2 payload
    event2_tampered = event2.model_copy()
    event2_tampered.output = "Tampered output by attacker"

    tampered_events = [event1, event2_tampered, event3]
    is_valid, err = verify_trace_integrity(tampered_events)
    assert is_valid is False
    assert "Hash verification failed" in err


def test_diagnosis_contract_validation():
    """Verify Diagnosis schema and confidence score constraints."""
    diag = Diagnosis(
        failure_id="fail-01",
        category="infinite_loop",
        root_cause="Repeated tool calls without state change",
        explanation="Agent called list_files 5 times consecutively",
        evidence_event_ids=["evt-2", "evt-3"],
        confidence=0.95,
        recommended_action="Introduce loop breaking policy",
    )
    assert diag.confidence == 0.95
    assert len(diag.evidence_event_ids) == 2

    # Confidence must be between 0.0 and 1.0
    with pytest.raises(ValidationError):
        Diagnosis(
            failure_id="fail-02",
            category="infinite_loop",
            root_cause="Root cause",
            explanation="Explanation",
            evidence_event_ids=["evt-1"],
            confidence=1.5,  # Exceeds 1.0
            recommended_action="Fix",
        )


def test_policy_and_policy_patch_validation():
    """Verify AgentPolicy and schema-bounded PolicyPatch."""
    base_policy = AgentPolicy(
        version="1.0.0",
        max_repeated_tool_calls=5,
        max_tool_retries=3,
    )

    # Valid patch
    patch = PolicyPatch(
        patch_id="patch-01",
        base_policy_version="1.0.0",
        changes={"max_repeated_tool_calls": 3, "stop_on_permission_error": True},
        reason="Mitigate observed loop behavior",
        affected_scenarios=["S5"],
    )

    new_policy = patch.apply_to(base_policy, new_version="1.0.1")
    assert new_policy.version == "1.0.1"
    assert new_policy.max_repeated_tool_calls == 3

    # Reject unauthorized policy fields
    with pytest.raises(ValidationError):
        PolicyPatch(
            patch_id="patch-malicious",
            base_policy_version="1.0.0",
            changes={"arbitrary_code_execution": True},  # Unauthorized field!
            reason="Malicious injection",
        )


def test_evaluation_result_validation():
    """Verify EvaluationResult data model."""
    result = EvaluationResult(
        run_id="run-101",
        test_id="TC-01",
        passed=True,
        assertions=[{"assertion": "all_tests_pass", "status": "passed"}],
        failures=[],
        execution_time=1.234,
    )
    assert result.passed is True
    assert result.execution_time == 1.234

