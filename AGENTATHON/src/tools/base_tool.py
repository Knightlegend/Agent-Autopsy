"""Base tool definition and security sandbox for Agent Autopsy tools."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict
from src.core.contracts import ToolResult


class BaseTool(ABC):
    """Abstract base class for all tools accessible to agents."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed tool description for the LLM."""
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """JSON Schema dictionary describing accepted arguments."""
        pass

    def to_openai_schema(self) -> Dict[str, Any]:
        """Format as an OpenAI-compatible function definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    def resolve_safe_path(self, rel_path: str) -> Path:
        """Sanitize and resolve a relative path against workspace root.

        Enforces strict boundary containment to prevent path traversal attacks
        (e.g. '../', absolute paths, symlink escapes).
        """
        # Clean stripped path
        clean = rel_path.strip().lstrip("/")
        target_path = (self.workspace_root / clean).resolve()

        # Check containment
        try:
            target_path.relative_to(self.workspace_root)
        except ValueError:
            raise PermissionError(
                f"Security violation: path '{rel_path}' resolves outside workspace boundary '{self.workspace_root}'"
            )

        return target_path

    @abstractmethod
    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool deterministically within safety constraints."""
        pass

