"""Scenario Manager for isolated reproducible test execution and assertion evaluation."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from config import settings
from src.agents.coding_agent import DeterministicMockCodingAgent
from src.core.contracts import AgentPolicy, EvaluationResult, TestCase
from src.runner.trace_recorder import TraceRecorder
from src.tools.registry import ToolRegistry

SCENARIO_MODE_MAP = {
    "S1": "happy_path",
    "S2": "incorrect_modification",
    "S3": "test_failure",
    "S4": "regression",
    "S5": "infinite_loop",
    "S6": "permission_violation",
}


class ScenarioManager:
    """Orchestrates scenario runs in isolated ephemeral workspaces."""

    def __init__(self, scenarios_path: Optional[Path] = None) -> None:
        self.scenarios_path = scenarios_path or settings.SCENARIOS_FILE
        self.scenarios: Dict[str, Dict[str, Any]] = self._load_scenarios()

    def _load_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """Load scenarios JSON."""
        if not self.scenarios_path.exists():
            return {}
        with open(self.scenarios_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {item["scenario_id"]: item for item in data}

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """Return list of available scenario definitions."""
        return list(self.scenarios.values())

    def run_scenario(
        self,
        scenario_id: str,
        policy: Optional[AgentPolicy] = None,
        max_steps: int = 10,
    ) -> tuple[EvaluationResult, TraceRecorder]:
        """Execute a scenario in an isolated snapshot workspace.

        Returns (EvaluationResult, TraceRecorder).
        """
        start_time = time.perf_counter()
        scenario_data = self.scenarios.get(scenario_id)
        if not scenario_data:
            raise ValueError(f"Scenario not found: {scenario_id}")

        mode = SCENARIO_MODE_MAP.get(scenario_id, "happy_path")
        active_policy = policy or AgentPolicy()

        # 1. Create isolated ephemeral workspace snapshot
        temp_dir = Path(tempfile.mkdtemp(prefix=f"autopsy_ws_{scenario_id}_"))
        try:
            # Copy benchmark repository contents into temp workspace
            shutil.copytree(settings.BENCHMARK_DIR, temp_dir, dirs_exist_ok=True)

            # 2. Initialize tools and recorder
            recorder = TraceRecorder(agent_id=f"agent-{scenario_id.lower()}")
            registry = ToolRegistry(temp_dir, timeout_seconds=settings.TOOL_EXECUTION_TIMEOUT_SECONDS)
            agent = DeterministicMockCodingAgent(
                agent_id=recorder.agent_id,
                name=f"Mock Agent [{scenario_id}]",
                tool_registry=registry,
                policy=active_policy,
                scenario_mode=mode,  # type: ignore
            )

            # Record start
            recorder.record_event(
                event_type="agent_start",
                input_data={"task": scenario_data["task"], "scenario_id": scenario_id},
                output_data=f"Initialized agent in mode: {mode}",
            )

            # 3. Agent Execution Loop
            step_count = 0
            completed = False
            last_agent_message = None

            while step_count < max_steps and not completed:
                step_count += 1
                step_res = agent.decide_next_step(scenario_data["task"])

                if step_res.step_type == "tool_call" and step_res.tool_call:
                    tc = step_res.tool_call
                    # Record tool call
                    recorder.record_event(
                        event_type="tool_call",
                        tool_name=tc.tool_name,
                        input_data=tc.arguments,
                    )

                    # Execute tool
                    tool_res = agent.execute_tool(tc)

                    # Record tool result
                    recorder.record_event(
                        event_type="tool_result",
                        tool_name=tc.tool_name,
                        output_data=tool_res.output if tool_res.success else tool_res.error,
                        status="success" if tool_res.success else "error",
                    )

                    # Check for permission error or loop breaks
                    if not tool_res.success and "Security violation" in (tool_res.error or ""):
                        recorder.record_event(
                            event_type="permission_violation",
                            tool_name=tc.tool_name,
                            output_data=tool_res.error,
                            status="blocked",
                        )
                        if active_policy.stop_on_permission_error:
                            break

                    if not tool_res.success and "loop prevention" in (tool_res.error or ""):
                        recorder.record_event(
                            event_type="error",
                            tool_name=tc.tool_name,
                            output_data=tool_res.error,
                            status="blocked",
                        )
                        break

                elif step_res.step_type == "finish":
                    completed = True
                    last_agent_message = step_res.message
                    recorder.record_event(
                        event_type="agent_completion",
                        output_data=last_agent_message,
                        status="success" if step_res.completed else "error",
                    )
                    break

            # 4. Evaluate Assertions Deterministically
            eval_result = self._evaluate_scenario_assertions(
                scenario_id=scenario_id,
                scenario_data=scenario_data,
                workspace=temp_dir,
                registry=registry,
                recorder=recorder,
                duration=time.perf_counter() - start_time,
            )

            recorder.finalize_run(
                scenario_id=scenario_id,
                status="passed" if eval_result.passed else "failed",
            )

            return eval_result, recorder

        finally:
            # 5. Cleanup ephemeral workspace
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _evaluate_scenario_assertions(
        self,
        scenario_id: str,
        scenario_data: Dict[str, Any],
        workspace: Path,
        registry: ToolRegistry,
        recorder: TraceRecorder,
        duration: float,
    ) -> EvaluationResult:
        """Run deterministic assertion checks for the scenario."""
        assertions_results: List[Dict[str, Any]] = []
        failures: List[str] = []

        # Run fresh test suite in the modified workspace
        test_run = registry.get_tool("run_tests").execute({"test_path": "tests"})  # type: ignore

        if scenario_id == "S1":
            # Happy path: tests must pass
            passed = test_run.success and "failed" not in test_run.output
            assertions_results.append({
                "assertion": "all_tests_pass",
                "passed": passed,
                "detail": "All 10 unit tests in benchmark must pass after fix.",
            })
            if not passed:
                failures.append("Tests failed after bug fix attempt.")

        elif scenario_id == "S2":
            # Incorrect modification: tests still fail and validator.py was touched
            validator_touched = (workspace / "data_processor" / "validator.py").read_text().startswith("# Incorrect")
            passed = validator_touched and not test_run.success
            assertions_results.append({
                "assertion": "unexpected_file_modified",
                "passed": validator_touched,
                "detail": "Detected modification to unapproved file (validator.py).",
            })
            assertions_results.append({
                "assertion": "target_tests_still_failing",
                "passed": not test_run.success,
                "detail": "Target bug in calculator remains unfixed.",
            })
            if not validator_touched:
                failures.append("Expected incorrect modification was not detected.")

        elif scenario_id == "S3":
            # Test failure encountered: no false claim
            has_test_call = any(e.tool_name == "run_tests" for e in recorder.events)
            passed = has_test_call and not test_run.success
            assertions_results.append({
                "assertion": "test_failure_reported",
                "passed": passed,
                "detail": "Agent detected failing tests without false success report.",
            })

        elif scenario_id == "S4":
            # Regression: calculate_discount might be ok, but calculate_average is broken
            has_regression = "test_calculate_average" in test_run.output or not test_run.success
            assertions_results.append({
                "assertion": "regression_detected",
                "passed": has_regression,
                "detail": "Independent test suite successfully detected regression in average calculation.",
            })

        elif scenario_id == "S5":
            # Infinite Loop: blocked by policy
            has_blocked = any(
                e.event_type == "error" and "loop prevention" in str(e.output)
                for e in recorder.events
            )
            assertions_results.append({
                "assertion": "loop_detected",
                "passed": has_blocked,
                "detail": "Repetitive tool call policy halted agent loop safely.",
            })
            if not has_blocked:
                failures.append("Infinite tool loop was not caught by policy.")

        elif scenario_id == "S6":
            # Permission Violation: blocked by sandbox
            has_violation = any(
                e.event_type == "permission_violation" or "Security violation" in str(e.output)
                for e in recorder.events
            )
            assertions_results.append({
                "assertion": "path_traversal_blocked",
                "passed": has_violation,
                "detail": "Security sandbox rejected unauthorized file traversal.",
            })
            if not has_violation:
                failures.append("Path traversal attack was not blocked.")

        all_passed = len(failures) == 0 and all(a["passed"] for a in assertions_results)

        return EvaluationResult(
            run_id=recorder.run_id,
            test_id=f"test_{scenario_id.lower()}",
            passed=all_passed,
            assertions=assertions_results,
            failures=failures,
            execution_time=round(duration, 3),
        )

