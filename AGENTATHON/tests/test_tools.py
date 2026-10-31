"""Unit tests for tool execution, sandboxing, and path-traversal prevention."""

import os
from pathlib import Path
import pytest
from src.tools.file_tools import ListFilesTool, ReadFileTool, SearchCodeTool, WriteFileTool
from src.tools.execution_tools import RunTestsTool
from src.tools.registry import ToolRegistry


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create a temporary isolated workspace for tool testing."""
    workspace = tmp_path / "sandbox_workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    # Populate dummy files
    (workspace / "sample.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    sub = workspace / "subdir"
    sub.mkdir()
    (sub / "nested.txt").write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    return workspace


def test_list_files_tool(temp_workspace: Path):
    """Verify ListFilesTool listing and boundary containment."""
    tool = ListFilesTool(temp_workspace)

    # Valid listing
    result = tool.execute({"directory": "."})
    assert result.success is True
    assert "sample.py" in result.output
    assert "subdir/nested.txt" in result.output

    # Path traversal rejection
    result_traversal = tool.execute({"directory": "../../"})
    assert result_traversal.success is False
    assert "Security violation" in result_traversal.error


def test_read_file_tool(temp_workspace: Path):
    """Verify ReadFileTool safety and line bounding."""
    tool = ReadFileTool(temp_workspace)

    # Read existing file
    result = tool.execute({"file_path": "subdir/nested.txt", "start_line": 1, "max_lines": 2})
    assert result.success is True
    assert "line 1" in result.output
    assert "line 2" in result.output

    # File not found
    result_missing = tool.execute({"file_path": "nonexistent.py"})
    assert result_missing.success is False
    assert "File not found" in result_missing.error

    # Path traversal attack
    result_attack = tool.execute({"file_path": "../../../etc/passwd"})
    assert result_attack.success is False
    assert "Security violation" in result_attack.error


def test_write_file_tool(temp_workspace: Path):
    """Verify WriteFileTool safety and directory creation."""
    tool = WriteFileTool(temp_workspace)

    # Valid write with directory creation
    result = tool.execute({
        "file_path": "new_dir/test_file.py",
        "content": "VAL = 42\n",
    })
    assert result.success is True
    assert (temp_workspace / "new_dir" / "test_file.py").exists()
    assert (temp_workspace / "new_dir" / "test_file.py").read_text() == "VAL = 42\n"

    # Traversal write rejection
    result_attack = tool.execute({
        "file_path": "../escape.txt",
        "content": "Malicious payload",
    })
    assert result_attack.success is False
    assert "Security violation" in result_attack.error


def test_search_code_tool(temp_workspace: Path):
    """Verify SearchCodeTool pattern matching and error handling."""
    tool = SearchCodeTool(temp_workspace)

    # Search existing pattern
    result = tool.execute({"pattern": "def hello"})
    assert result.success is True
    assert "sample.py" in result.output

    # Search non-existent pattern
    result_empty = tool.execute({"pattern": "xyz_not_found_123"})
    assert result_empty.success is True
    assert "No matches found." in result_empty.output

    # Invalid regex
    result_regex = tool.execute({"pattern": "([unclosed_group"})
    assert result_regex.success is False
    assert "Invalid regular expression" in result_regex.error


def test_run_tests_tool_on_benchmark(temp_workspace: Path):
    """Verify RunTestsTool execution and timeout protection."""
    # Create a simple test file in temp workspace
    tests_dir = temp_workspace / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_dummy.py").write_text("def test_pass(): assert True\n", encoding="utf-8")

    tool = RunTestsTool(temp_workspace, timeout_seconds=10)
    result = tool.execute({"test_path": "tests"})
    assert result.success is True
    assert "passed" in result.output

    # Test path traversal in run_tests
    result_traversal = tool.execute({"test_path": "../../tests"})
    assert result_traversal.success is False
    assert "Security violation" in result_traversal.error


def test_tool_registry():
    """Verify ToolRegistry registers all standard tools and generates OpenAI schemas."""
    repo_dir = Path(__file__).resolve().parent.parent / "benchmark" / "repository"
    registry = ToolRegistry(repo_dir)

    tools = registry.list_tool_names()
    assert set(tools) == {"list_files", "read_file", "write_file", "search_code", "run_tests"}

    schemas = registry.get_openai_schemas()
    assert len(schemas) == 5
    schema_names = [s["function"]["name"] for s in schemas]
    assert "run_tests" in schema_names

