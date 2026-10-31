"""Deterministic Mock Model Adapter for offline testing and reproducible benchmarks."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from src.adapters.base import AdapterResponse, BaseModelAdapter, ChatMessage


class MockModelAdapter(BaseModelAdapter):
    """Deterministic mock adapter that yields pre-programmed responses or dynamic handlers."""

    def __init__(
        self,
        model_name: str = "mock-coding-model",
        responses: Optional[List[AdapterResponse]] = None,
        handler: Optional[Callable[[List[ChatMessage], Optional[List[Dict[str, Any]]]], AdapterResponse]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, **kwargs)
        self.responses: List[AdapterResponse] = list(responses or [])
        self.handler = handler
        self.call_history: List[List[ChatMessage]] = []

    def add_response(self, response: AdapterResponse) -> None:
        """Enqueue a scripted response."""
        self.responses.append(response)

    def complete(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> AdapterResponse:
        """Return next scripted response or evaluate handler."""
        self.call_history.append(list(messages))
        if self.handler is not None:
            return self.handler(messages, tools)

        if self.responses:
            return self.responses.pop(0)

        # Default fallback response
        return AdapterResponse(
            content="Task completed successfully.",
            tool_calls=[],
            finish_reason="stop",
            model_name=self.model_name,
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

    async def acomplete(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> AdapterResponse:
        """Asynchronously return next scripted response."""
        return self.complete(messages, tools, temperature, max_tokens)

    def get_provider_name(self) -> str:
        return "mock"

