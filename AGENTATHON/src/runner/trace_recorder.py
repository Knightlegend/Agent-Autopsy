"""Append-only tamper-evident execution trace recorder and SQLite persistence."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from config import settings
from src.core.contracts import ExecutionEvent, verify_trace_integrity


class TraceRecorder:
    """Manages append-only JSONL execution traces with cryptographic hash chains."""

    def __init__(self, run_id: Optional[str] = None, agent_id: str = "mock-coding-agent-01") -> None:
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        self.agent_id = agent_id
        self.sequence_number = 0
        self.previous_hash: Optional[str] = None
        self.events: List[ExecutionEvent] = []

        # File paths
        settings.TRACES_DIR.mkdir(parents=True, exist_ok=True)
        self.trace_file = settings.TRACES_DIR / f"{self.run_id}.jsonl"

        # Initialize SQLite DB schema
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite tables for indexed search and run metadata."""
        settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(settings.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    scenario_id TEXT,
                    status TEXT,
                    event_count INTEGER
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    sequence_number INTEGER,
                    timestamp TEXT,
                    event_type TEXT,
                    tool_name TEXT,
                    status TEXT,
                    event_hash TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
            """)
            conn.commit()

    def record_event(
        self,
        event_type: str,
        tool_name: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Any] = None,
        status: str = "success",
    ) -> ExecutionEvent:
        """Construct, seal with hash-chain, append to JSONL, and index into SQLite."""
        event = ExecutionEvent(
            run_id=self.run_id,
            event_id=f"evt_{uuid.uuid4().hex[:10]}",
            sequence_number=self.sequence_number,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=self.agent_id,
            event_type=event_type,  # type: ignore
            tool_name=tool_name,
            input=input_data,
            output=output_data,
            status=status,  # type: ignore
        )

        # Seal with SHA-256 hash linking to previous event
        event.seal(previous_hash=self.previous_hash)
        self.previous_hash = event.event_hash
        self.sequence_number += 1
        self.events.append(event)

        # Append to JSONL file
        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")

        # Index into SQLite
        try:
            with sqlite3.connect(settings.DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO events
                    (event_id, run_id, sequence_number, timestamp, event_type, tool_name, status, event_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.run_id,
                        event.sequence_number,
                        event.timestamp,
                        event.event_type,
                        event.tool_name,
                        event.status,
                        event.event_hash,
                    ),
                )
                conn.commit()
        except Exception:
            pass

        return event

    def finalize_run(self, scenario_id: str, status: str = "completed") -> None:
        """Update run summary record in SQLite."""
        start_time = self.events[0].timestamp if self.events else datetime.now(timezone.utc).isoformat()
        end_time = self.events[-1].timestamp if self.events else start_time
        try:
            with sqlite3.connect(settings.DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO runs
                    (run_id, agent_id, start_time, end_time, scenario_id, status, event_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.run_id,
                        self.agent_id,
                        start_time,
                        end_time,
                        scenario_id,
                        status,
                        len(self.events),
                    ),
                )
                conn.commit()
        except Exception:
            pass

    def verify_trace(self) -> tuple[bool, Optional[str]]:
        """Verify the cryptographic integrity of recorded events in this run."""
        return verify_trace_integrity(self.events)

    @classmethod
    def load_trace(cls, run_id: str) -> List[ExecutionEvent]:
        """Load and parse an execution trace from disk."""
        trace_file = settings.TRACES_DIR / f"{run_id}.jsonl"
        if not trace_file.exists():
            raise FileNotFoundError(f"Trace file not found: {trace_file}")

        events = []
        with open(trace_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(ExecutionEvent.model_validate_json(line))
        return events

