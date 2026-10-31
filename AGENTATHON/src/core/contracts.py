"""Core data contracts for Agent Autopsy.

All domain models are strictly validated Pydantic models ensuring
reproducibility, schema integrity, and tamper-evident tracing.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 1. Agent Profile
# ---------------------------------------------------------------------------

class AgentProfile(BaseModel):
    """Specification and observed profile of a target agent under test."""

    agent_id: str = Field(..., min_length=1, description="Unique identifier for the agent instance")
    name: str = Field(..., min_length=1, description="Human-readable agent name")
    model_provider: str = Field(..., description="Provider name, e.g. openai, vllm, mock")
    model_name: str = Field(..., description="Model name or identifier")
    system_instructions: Optional[str] = Field(
        default=None, description="Accessible system instructions if available"
    )
    available_tools: List[str] = Field(
        default_factory=list, description="Names of tools exposed to this agent"
    )
    tool_schemas: List[Dict[str, Any]] = Field(
        default_factory=list, description="JSON schemas describing tool parameters"
    )
    capabilities: List[str] = Field(
        default_factory=list, description="Inferred or stated agent capabilities"
    )
    constraints: List[str] = Field(
        default_factory=list, description="Operational boundaries and safety constraints"
    )
    identified_risks: List[str] = Field(
        default_factory=list, description="Static risk factors flagged by the profiler"
    )


# ---------------------------------------------------------------------------
# 2. Test Case & Scenarios
# ---------------------------------------------------------------------------

class TestCase(BaseModel):
    """A deterministic or generated test scenario to evaluate an agent."""

    __test__ = False  # Inform pytest this is a data contract, not a test suite class

    test_id: str = Field(..., min_length=1, description="Unique test case ID")
    scenario_id: str = Field(..., min_length=1, description="Parent scenario group ID (e.g. S1)")
    category: str = Field(..., description="Category, e.g. bug_fix, permission, loop, regression")
    task: str = Field(..., min_length=1, description="Task prompt presented to the agent")
    injected_fault: Optional[str] = Field(
        default=None, description="Fault identifier or description to inject during run"
    )
    expected_behaviour: str = Field(..., description="Expected behavioural outcome")
    assertions: List[str] = Field(
        default_factory=list, description="List of assertions to verify against execution trace"
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        default="medium", description="Failure severity"
    )


# ---------------------------------------------------------------------------
# 3. Execution Event & Hash Chaining
# ---------------------------------------------------------------------------

class ExecutionEvent(BaseModel):
    """Immutable, tamper-evident log of a single agent or environment event."""

    run_id: str = Field(..., min_length=1, description="Execution run identifier")
    event_id: str = Field(..., min_length=1, description="Unique event identifier")
    sequence_number: int = Field(..., ge=0, description="Monotonically increasing sequence index")
    timestamp: str = Field(default_factory=_utc_now_iso, description="ISO 8601 UTC timestamp")
    agent_id: str = Field(..., description="Identifier of the agent associated with this run")
    event_type: Literal[
        "agent_start",
        "agent_thought",
        "tool_call",
        "tool_result",
        "fault_injection",
        "permission_violation",
        "agent_completion",
        "error",
        "test_assertion",
    ] = Field(..., description="Type of event occurred")
    tool_name: Optional[str] = Field(default=None, description="Tool name if tool-related event")
    input: Optional[Dict[str, Any]] = Field(default=None, description="Inputs or tool parameters")
    output: Optional[Any] = Field(default=None, description="Output or response payload")
    status: Literal["success", "error", "blocked", "in_progress", "timeout"] = Field(
        default="success", description="Status code of the event"
    )
    previous_hash: Optional[str] = Field(
        default=None, description="SHA-256 hash of the preceding event in the run"
    )
    event_hash: Optional[str] = Field(
        default=None, description="SHA-256 hash of this event including previous_hash"
    )

    def calculate_hash(self) -> str:
        """Deterministically calculate SHA-256 hash of this event."""
        payload = {
            "run_id": self.run_id,
            "event_id": self.event_id,
            "sequence_number": self.sequence_number,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "tool_name": self.tool_name,
            "input": self.input,
            "output": self.output,
            "status": self.status,
            "previous_hash": self.previous_hash or "GENESIS",
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def seal(self, previous_hash: Optional[str] = None) -> ExecutionEvent:
        """Assign previous_hash and compute event_hash."""
        self.previous_hash = previous_hash or "GENESIS"
        self.event_hash = self.calculate_hash()
        return self

    def verify_hash(self) -> bool:
        """Verify that current event_hash matches recalculation."""
        if not self.event_hash:
            return False
        return self.calculate_hash() == self.event_hash


def verify_trace_integrity(events: List[ExecutionEvent]) -> tuple[bool, Optional[str]]:
    """Verify hash chain integrity across an ordered sequence of events.

    Returns (is_valid, error_message).
    """
    if not events:
        return True, None

    # Verify sequence continuity and hash linkage
    expected_prev_hash = "GENESIS"
    for i, event in enumerate(events):
        if event.sequence_number != i:
            return False, f"Sequence number mismatch at index {i}: got {event.sequence_number}, expected {i}"

        if not event.verify_hash():
            return False, f"Hash verification failed for event {event.event_id} at sequence {i}"

        actual_prev = event.previous_hash or "GENESIS"
        if actual_prev != expected_prev_hash:
            return False, (
                f"Hash chain broken at event {event.event_id} (seq {i}): "
                f"expected prev_hash {expected_prev_hash}, got {actual_prev}"
            )

        expected_prev_hash = event.event_hash or ""

    return True, None


# ---------------------------------------------------------------------------
# 4. Diagnosis
# ---------------------------------------------------------------------------

class Diagnosis(BaseModel):
    """Structured diagnosis of an agent failure with concrete evidence citations."""

    failure_id: str = Field(..., min_length=1, description="Unique diagnosis identifier")
    category: Literal[
        "tool_misuse",
        "hallucination",
        "permission_violation",
        "infinite_loop",
        "regression",
        "test_failure",
        "timeout",
        "unhandled_error",
        "other",
    ] = Field(..., description="Class of failure")
    root_cause: str = Field(..., min_length=1, description="Concise statement of root cause")
    explanation: str = Field(..., min_length=1, description="Detailed explanatory breakdown")
    evidence_event_ids: List[str] = Field(
        ..., min_length=1, description="Citations of specific ExecutionEvent event_ids"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Investigator confidence score between 0.0 and 1.0"
    )
    recommended_action: str = Field(..., min_length=1, description="Suggested corrective strategy")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return round(float(v), 4)


# ---------------------------------------------------------------------------
# 5. Policy & Policy Patch
# ---------------------------------------------------------------------------

# Approved policy parameter names
APPROVED_POLICY_FIELDS = {
    "revalidate_before_action",
    "max_tool_retries",
    "stop_on_permission_error",
    "verify_tests_before_success",
    "max_repeated_tool_calls",
}


class AgentPolicy(BaseModel):
    """Operational bounds, safety policies and execution constraints."""

    version: str = Field(default="1.0.0", description="Policy version string")
    revalidate_before_action: bool = Field(
        default=False, description="Whether agent must re-read or verify before modifying files"
    )
    max_tool_retries: int = Field(
        default=3, ge=1, le=10, description="Max consecutive retry attempts for failed tools"
    )
    stop_on_permission_error: bool = Field(
        default=True, description="Immediately halt execution upon security/permission violation"
    )
    verify_tests_before_success: bool = Field(
        default=True, description="Require running test suite before claiming task completion"
    )
    max_repeated_tool_calls: int = Field(
        default=5, ge=1, le=20, description="Max identical sequential tool calls before loop break"
    )

    model_config = ConfigDict(extra="forbid")  # Strictly reject unknown fields for security!


class PolicyPatch(BaseModel):
    """Bounded, schema-validated modification proposal to an AgentPolicy."""

    patch_id: str = Field(..., min_length=1, description="Unique patch identifier")
    base_policy_version: str = Field(..., min_length=1, description="Version patch applies against")
    changes: Dict[str, Any] = Field(
        ..., min_length=1, description="Key-value modifications to apply to policy"
    )
    reason: str = Field(..., min_length=1, description="Engineering justification for changes")
    affected_scenarios: List[str] = Field(
        default_factory=list, description="Scenarios this patch is expected to address"
    )

    @field_validator("changes")
    @classmethod
    def validate_changes(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        disallowed = set(v.keys()) - APPROVED_POLICY_FIELDS
        if disallowed:
            raise ValueError(
                f"PolicyPatch contains unauthorized policy fields: {disallowed}. "
                f"Approved fields are: {APPROVED_POLICY_FIELDS}"
            )
        return v

    def apply_to(self, base_policy: AgentPolicy, new_version: Optional[str] = None) -> AgentPolicy:
        """Apply patch to a base policy and return a new updated AgentPolicy instance."""
        data = base_policy.model_dump()
        data.update(self.changes)
        if new_version:
            data["version"] = new_version
        return AgentPolicy(**data)


# ---------------------------------------------------------------------------
# 6. Evaluation Result
# ---------------------------------------------------------------------------

class EvaluationResult(BaseModel):
    """Deterministic evaluation outcome for a test case run."""

    run_id: str = Field(..., min_length=1, description="Execution run identifier")
    test_id: str = Field(..., min_length=1, description="Evaluated test case identifier")
    passed: bool = Field(..., description="Whether all assertions passed")
    assertions: List[Dict[str, Any]] = Field(
        default_factory=list, description="Individual assertion results"
    )
    failures: List[str] = Field(
        default_factory=list, description="Descriptions of failed assertions"
    )
    execution_time: float = Field(..., ge=0.0, description="Total execution duration in seconds")


# ---------------------------------------------------------------------------
# 7. Tool Invocation & Step Contracts
# ---------------------------------------------------------------------------

class ToolCall(BaseModel):
    """Structured tool call produced by an agent."""

    call_id: str = Field(..., min_length=1, description="Unique call identifier")
    tool_name: str = Field(..., min_length=1, description="Target tool name")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Named parameters for tool execution"
    )


class ToolResult(BaseModel):
    """Structured output returned from a tool execution."""

    call_id: str = Field(..., description="Matching ToolCall call_id")
    tool_name: str = Field(..., description="Tool name executed")
    success: bool = Field(..., description="Whether execution completed without error")
    output: str = Field(default="", description="Captured stdout / result text")
    error: Optional[str] = Field(default=None, description="Captured stderr or error message")
    execution_time: float = Field(default=0.0, ge=0.0, description="Duration in seconds")


class AgentStepResult(BaseModel):
    """A single step decision by the agent."""

    step_type: Literal["tool_call", "finish", "error"] = Field(
        ..., description="Type of step taken"
    )
    tool_call: Optional[ToolCall] = Field(default=None, description="ToolCall if step_type is tool_call")
    message: Optional[str] = Field(
        default=None, description="Agent explanation or completion report"
    )
    completed: bool = Field(default=False, description="Whether the overall task is marked complete")
