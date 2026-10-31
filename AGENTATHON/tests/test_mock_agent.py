"""Unit tests for the Deterministic Mock Coding Agent and policy enforcement."""

from pathlib import Path
import pytest
from src.agents.coding_agent import DeterministicMockCodingAgent
from src.core.contracts import AgentPolicy
from src.tools.registry import ToolRegistry


@pytest.fixture
def test_registry(tmp_path: Path) -> ToolRegistry:
    """Fixture providing a ToolRegistry on a temporary workspace."""
    workspace = tmp_path / "agent_ws"
    workspace.mkdir()
    (workspace / "data_processor").mkdir()
    (workspace / "data_processor" / "calculator.py").write_text("# initial", encoding="utf-8")
    return ToolRegistry(workspace)


def test_agent_profile_generation(test_registry: ToolRegistry):
    """Verify agent static profile extraction."""
    agent = DeterministicMockCodingAgent(tool_registry=test_registry)
    profile = agent.get_profile()

    assert profile.agent_id == "mock-coding-agent-01"
    assert "list_files" in profile.available_tools
    assert "run_tests" in profile.available_tools
    assert len(profile.tool_schemas) == 5


def test_agent_happy_path_steps(test_registry: ToolRegistry):
    """Verify sequence of actions in happy_path mode."""
    agent = DeterministicMockCodingAgent(
        tool_registry=test_registry,
        scenario_mode="happy_path",
    )

    # Step 0: list_files
    s0 = agent.decide_next_step("Fix calculator bug")
    assert s0.step_type == "tool_call"
    assert s0.tool_call.tool_name == "list_files"
    r0 = agent.execute_tool(s0.tool_call)
    assert r0.success is True

    # Step 1: read_file
    s1 = agent.decide_next_step("Fix calculator bug")
    assert s1.step_type == "tool_call"
    assert s1.tool_call.tool_name == "read_file"
    r1 = agent.execute_tool(s1.tool_call)
    assert r1.success is True

    # Step 2: write_file
    s2 = agent.decide_next_step("Fix calculator bug")
    assert s2.step_type == "tool_call"
    assert s2.tool_call.tool_name == "write_file"
    r2 = agent.execute_tool(s2.tool_call)
    assert r2.success is True

    # Step 3: run_tests
    s3 = agent.decide_next_step("Fix calculator bug")
    assert s3.step_type == "tool_call"
    assert s3.tool_call.tool_name == "run_tests"

    # Step 4: completion
    s4 = agent.decide_next_step("Fix calculator bug")
    assert s4.step_type == "finish"
    assert s4.completed is True


def test_agent_infinite_loop_policy_enforcement(test_registry: ToolRegistry):
    """Verify loop detection halts repetitive tool calls when threshold is hit."""
    policy = AgentPolicy(max_repeated_tool_calls=3)
    agent = DeterministicMockCodingAgent(
        tool_registry=test_registry,
        policy=policy,
        scenario_mode="infinite_loop",
    )

    results = []
    for _ in range(5):
        step_res = agent.decide_next_step("Infinite loop test")
        if step_res.step_type == "tool_call":
            tool_res = agent.execute_tool(step_res.tool_call)
            results.append(tool_res)

    # The 3rd repetitive call should be blocked by policy
    assert results[0].success is True
    assert results[1].success is True
    assert results[2].success is False
    assert "infinite loop prevention" in results[2].error


def test_agent_permission_violation_blocked(test_registry: ToolRegistry):
    """Verify that agent cannot perform directory traversal outside workspace."""
    agent = DeterministicMockCodingAgent(
        tool_registry=test_registry,
        scenario_mode="permission_violation",
    )

    s0 = agent.decide_next_step("Security test")
    assert s0.step_type == "tool_call"
    res = agent.execute_tool(s0.tool_call)

    assert res.success is False
    assert "Security violation" in res.error

