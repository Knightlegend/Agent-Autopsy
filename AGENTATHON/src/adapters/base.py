"""Base Model Adapter Interface.

Provides a provider-agnostic interface for LLM interaction,
supporting both synchronous and asynchronous message completion,
structured tool calling, and deterministic mocking.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Normalized chat message."""

    role: str = Field(..., description="Role: system, user, assistant, tool")
    content: Optional[str] = Field(default=None, description="Message text content")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Structured tool calls requested by assistant"
    )
    tool_call_id: Optional[str] = Field(
        default=None, description="Tool call ID this message responds to"
    )
    name: Optional[str] = Field(default=None, description="Optional name of the tool or sender")


class AdapterResponse(BaseModel):
    """Standardized response from an LLM provider."""

    content: Optional[str] = Field(default=None, description="Generated assistant text response")
    tool_calls: List[Dict[str, Any]] = Field(
        default_factory=list, description="Extracted tool calls with 'id', 'name', 'arguments'"
    )
    finish_reason: str = Field(default="stop", description="stop, tool_calls, length, error")
    model_name: str = Field(..., description="Name of the model that generated this response")
    usage: Dict[str, int] = Field(
        default_factory=dict, description="Token usage statistics (prompt, completion, total)"
    )
    raw_response: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional raw provider response payload"
    )


class BaseModelAdapter(ABC):
    """Abstract base adapter for LLM providers."""

    def __init__(self, model_name: str, **kwargs: Any) -> None:
        self.model_name = model_name
        self.extra_config = kwargs

    @abstractmethod
    def complete(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> AdapterResponse:
        """Execute a synchronous completion request."""
        pass

    @abstractmethod
    async def acomplete(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> AdapterResponse:
        """Execute an asynchronous completion request."""
        pass

    def get_provider_name(self) -> str:
        """Return the provider identifier."""
        return self.__class__.__name__

