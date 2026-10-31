"""Tool registry managing available tools and sandbox execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from src.core.contracts import ToolCall, ToolResult
from src.tools.base_tool import BaseTool
from src.tools.file_tools import ListFilesTool, ReadFileTool, SearchCodeTool, WriteFileTool
from src.tools.execution_tools import RunTestsTool


class ToolRegistry:
    """Central registry of agent tools with schema export and execution dispatch."""

    def __init__(self, workspace_root: Path, timeout_seconds: int = 15) -> None:
        self.workspace_root = workspace_root.resolve()
        self.timeout_seconds = timeout_seconds
        self._tools: Dict[str, BaseTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the 5 mandatory coding agent tools."""
        self.register(ListFilesTool(self.workspace_root))
        self.register(ReadFileTool(self.workspace_root))
        self.register(WriteFileTool(self.workspace_root))
        self.register(SearchCodeTool(self.workspace_root))
        self.register(RunTestsTool(self.workspace_root, timeout_seconds=self.timeout_seconds))

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Look up tool by name."""
        return self._tools.get(name)

    def list_tool_names(self) -> List[str]:
        """Return names of all registered tools."""
        return list(self._tools.keys())

    def get_openai_schemas(self) -> List[Dict[str, Any]]:
        """Return OpenAI function definition schemas for all tools."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """Dispatch a ToolCall to the matching tool."""
        tool = self.get_tool(tool_call.tool_name)
        if not tool:
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                output="",
                error=f"Unrecognized tool '{tool_call.tool_name}'. Available tools: {self.list_tool_names()}",
                execution_time=0.0,
            )

        # Merge call_id into arguments for result tracking
        args = dict(tool_call.arguments)
        args["call_id"] = tool_call.call_id

        return tool.execute(args)

