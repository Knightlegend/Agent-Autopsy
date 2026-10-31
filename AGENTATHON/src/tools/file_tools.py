"""Safe file manipulation tools for target coding agents."""

from __future__ import annotations

import fnmatch
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.core.contracts import ToolResult
from src.tools.base_tool import BaseTool

# Directories and patterns to ignore
IGNORED_PATTERNS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    ".coverage",
    "*.pyc",
    "*.pyo",
    "*.swp",
}


class ListFilesTool(BaseTool):
    """Tool to inspect files in the workspace directory."""

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return (
            "List files and directories in the workspace. "
            "Pass an optional relative directory path (defaults to root '.')."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Relative directory path to list (e.g. '.' or 'src')",
                    "default": ".",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum recursion depth (1 to 5)",
                    "default": 3,
                },
            },
            "required": [],
        }

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start_t = time.perf_counter()
        call_id = arguments.get("call_id", "call_list_files")
        rel_dir = arguments.get("directory", ".")
        max_depth = min(max(int(arguments.get("max_depth", 3)), 1), 5)

        try:
            target_dir = self.resolve_safe_path(rel_dir)
            if not target_dir.exists():
                return ToolResult(
                    call_id=call_id,
                    tool_name=self.name,
                    success=False,
                    output="",
                    error=f"Directory not found: '{rel_dir}'",
                    execution_time=time.perf_counter() - start_t,
                )
            if not target_dir.is_dir():
                return ToolResult(
                    call_id=call_id,
                    tool_name=self.name,
                    success=False,
                    output="",
                    error=f"Path is not a directory: '{rel_dir}'",
                    execution_time=time.perf_counter() - start_t,
                )

            results: List[str] = []
            base_parts_len = len(target_dir.parts)

            for root, dirs, files in os.walk(target_dir):
                root_path = Path(root)
                depth = len(root_path.parts) - base_parts_len
                if depth >= max_depth:
                    dirs.clear()
                    continue

                # Filter ignored directories in-place
                dirs[:] = [
                    d for d in dirs
                    if not any(fnmatch.fnmatch(d, pat) for pat in IGNORED_PATTERNS)
                ]

                for f in sorted(files):
                    if any(fnmatch.fnmatch(f, pat) for pat in IGNORED_PATTERNS):
                        continue
                    file_path = root_path / f
                    rel = file_path.relative_to(self.workspace_root)
                    results.append(str(rel))

            output_text = "\n".join(results) if results else "(Empty directory)"
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=output_text,
                execution_time=time.perf_counter() - start_t,
            )
        except PermissionError as pe:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error=str(pe),
                execution_time=time.perf_counter() - start_t,
            )
        except Exception as exc:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error=f"Unexpected error listing files: {exc}",
                execution_time=time.perf_counter() - start_t,
            )


class ReadFileTool(BaseTool):
    """Tool to safely read file content."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read content of a file within the workspace. "
            "Optionally provide start_line (1-indexed) and max_lines."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path of file to read",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed)",
                    "default": 1,
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum number of lines to read",
                    "default": 300,
                },
            },
            "required": ["file_path"],
        }

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start_t = time.perf_counter()
        call_id = arguments.get("call_id", "call_read_file")
        rel_path = arguments.get("file_path", "")
        start_line = max(int(arguments.get("start_line", 1)), 1)
        max_lines = min(max(int(arguments.get("max_lines", 300)), 1), 1000)

        if not rel_path:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error="Missing required argument 'file_path'",
                execution_time=time.perf_counter() - start_t,
            )

        try:
            target_path = self.resolve_safe_path(rel_path)
            if not target_path.exists():
                return ToolResult(
                    call_id=call_id,
                    tool_name=self.name,
                    success=False,
                    output="",
                    error=f"File not found: '{rel_path}'",
                    execution_time=time.perf_counter() - start_t,
                )
            if not target_path.is_file():
                return ToolResult(
                    call_id=call_id,
                    tool_name=self.name,
                    success=False,
                    output="",
                    error=f"Path is not a regular file: '{rel_path}'",
                    execution_time=time.perf_counter() - start_t,
                )

            # Read with line bounds
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            selected = lines[start_line - 1 : start_line - 1 + max_lines]

            numbered = [
                f"{start_line + i:4d} | {line.rstrip()}"
                for i, line in enumerate(selected)
            ]
            header = f"[File: {rel_path} | Lines {start_line}-{min(start_line + len(selected) - 1, total_lines)} of {total_lines}]\n"
            content = header + "\n".join(numbered)

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=content,
                execution_time=time.perf_counter() - start_t,
            )
        except PermissionError as pe:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error=str(pe),
                execution_time=time.perf_counter() - start_t,
            )
        except Exception as exc:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error=f"Failed to read file: {exc}",
                execution_time=time.perf_counter() - start_t,
            )


class WriteFileTool(BaseTool):
    """Tool to safely write or modify files within workspace."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Write full content to a file in the workspace. "
            "Creates parent directories if necessary. Overwrites existing content."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path of file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content to write",
                },
            },
            "required": ["file_path", "content"],
        }

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start_t = time.perf_counter()
        call_id = arguments.get("call_id", "call_write_file")
        rel_path = arguments.get("file_path", "")
        content = arguments.get("content", "")

        if not rel_path:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error="Missing required argument 'file_path'",
                execution_time=time.perf_counter() - start_t,
            )

        try:
            target_path = self.resolve_safe_path(rel_path)
            # Ensure parent directories
            target_path.parent.mkdir(parents=True, exist_ok=True)

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=f"Successfully wrote {len(content)} characters to '{rel_path}'",
                execution_time=time.perf_counter() - start_t,
            )
        except PermissionError as pe:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error=str(pe),
                execution_time=time.perf_counter() - start_t,
            )
        except Exception as exc:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error=f"Failed to write file: {exc}",
                execution_time=time.perf_counter() - start_t,
            )


class SearchCodeTool(BaseTool):
    """Tool to search code across files in workspace."""

    @property
    def name(self) -> str:
        return "search_code"

    @property
    def description(self) -> str:
        return (
            "Search for a text substring or regex pattern across files in the workspace. "
            "Returns matching file paths, line numbers, and matching lines."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search string or regular expression",
                },
                "file_extension": {
                    "type": "string",
                    "description": "Optional file extension filter, e.g. '.py'",
                    "default": "",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of matches to return",
                    "default": 50,
                },
            },
            "required": ["pattern"],
        }

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start_t = time.perf_counter()
        call_id = arguments.get("call_id", "call_search_code")
        pattern = arguments.get("pattern", "")
        ext = arguments.get("file_extension", "").strip()
        max_results = min(max(int(arguments.get("max_results", 50)), 1), 200)

        if not pattern:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error="Missing required argument 'pattern'",
                execution_time=time.perf_counter() - start_t,
            )

        try:
            regex = re.compile(pattern)
        except re.error as re_err:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error=f"Invalid regular expression pattern: {re_err}",
                execution_time=time.perf_counter() - start_t,
            )

        matches: List[str] = []
        try:
            for root, dirs, files in os.walk(self.workspace_root):
                # Filter ignored dirs
                dirs[:] = [
                    d for d in dirs
                    if not any(fnmatch.fnmatch(d, pat) for pat in IGNORED_PATTERNS)
                ]

                for f in sorted(files):
                    if ext and not f.endswith(ext):
                        continue
                    if any(fnmatch.fnmatch(f, pat) for pat in IGNORED_PATTERNS):
                        continue

                    full_path = Path(root) / f
                    try:
                        rel = full_path.relative_to(self.workspace_root)
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                            for idx, line in enumerate(file_obj, 1):
                                if regex.search(line):
                                    matches.append(f"{rel}:{idx}: {line.strip()}")
                                    if len(matches) >= max_results:
                                        break
                    except Exception:
                        continue

                    if len(matches) >= max_results:
                        break
                if len(matches) >= max_results:
                    break

            output_text = "\n".join(matches) if matches else "No matches found."
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=output_text,
                execution_time=time.perf_counter() - start_t,
            )
        except Exception as exc:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output="",
                error=f"Error searching code: {exc}",
                execution_time=time.perf_counter() - start_t,
            )

