"""Safe execution tools for running tests in an isolated sandbox."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.core.contracts import ToolResult
from src.tools.base_tool import BaseTool

ALLOWED_PYTEST_FLAGS = {"-v", "-q", "-s", "--tb=short", "--tb=line", "--tb=auto"}


class RunTestsTool(BaseTool):
    """Tool to execute pytest on benchmark tests under strict isolation."""

    def __init__(self, workspace_root: Path, timeout_seconds: int = 15) -> None:
        super().__init__(workspace_root)
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "run_tests"

    @property
    def description(self) -> str:
        return (
            "Run pytest against the test suite within the workspace. "
            "Accepts optional test_path (e.g. 'tests/test_calculator.py') "
            "and optional filter_expression (e.g. 'test_add')."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_path": {
                    "type": "string",
                    "description": "Optional relative path to specific test file or directory",
                    "default": "tests",
                },
                "filter_expression": {
                    "type": "string",
                    "description": "Optional pytest expression filter (-k argument)",
                    "default": "",
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Run pytest in verbose mode (-v)",
                    "default": False,
                },
            },
            "required": [],
        }

    def _sanitize_env(self) -> Dict[str, str]:
        """Construct a minimal, leak-free environment for subprocess execution."""
        clean_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": str(self.workspace_root),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        return clean_env

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start_t = time.perf_counter()
        call_id = arguments.get("call_id", "call_run_tests")
        rel_test_path = arguments.get("test_path", "tests").strip()
        filter_expr = arguments.get("filter_expression", "").strip()
        verbose = bool(arguments.get("verbose", False))

        # Command construction - strictly list-based, no shell
        cmd: List[str] = [sys.executable, "-m", "pytest"]

        if verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")

        # Validate and sanitize test path
        if rel_test_path:
            try:
                resolved_test = self.resolve_safe_path(rel_test_path)
                if not resolved_test.exists():
                    return ToolResult(
                        call_id=call_id,
                        tool_name=self.name,
                        success=False,
                        output="",
                        error=f"Test path does not exist: '{rel_test_path}'",
                        execution_time=time.perf_counter() - start_t,
                    )
                cmd.append(str(resolved_test.relative_to(self.workspace_root)))
            except PermissionError as pe:
                return ToolResult(
                    call_id=call_id,
                    tool_name=self.name,
                    success=False,
                    output="",
                    error=str(pe),
                    execution_time=time.perf_counter() - start_t,
                )

        if filter_expr:
            # Basic validation of filter expression to prevent flag injection
            if filter_expr.startswith("-"):
                return ToolResult(
                    call_id=call_id,
                    tool_name=self.name,
                    success=False,
                    output="",
                    error="filter_expression must be a test name or expression, not a flag",
                    execution_time=time.perf_counter() - start_t,
                )
            cmd.extend(["-k", filter_expr])

        clean_env = self._sanitize_env()

        try:
            process = subprocess.run(
                cmd,
                cwd=str(self.workspace_root),
                env=clean_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )

            stdout = process.stdout or ""
            stderr = process.stderr or ""
            passed = process.returncode == 0

            combined_output = stdout
            if stderr:
                combined_output = f"{stdout}\n[STDERR]\n{stderr}".strip()

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=passed,
                output=combined_output,
                error=None if passed else f"Pytest exited with status {process.returncode}",
                execution_time=time.perf_counter() - start_t,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error=f"Test execution timed out after {self.timeout_seconds}s",
                execution_time=time.perf_counter() - start_t,
            )
        except Exception as exc:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error=f"Failed to execute tests: {exc}",
                execution_time=time.perf_counter() - start_t,
            )

