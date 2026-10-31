"""Configuration management for Agent Autopsy.

Loads settings from environment variables and optional .env file,
providing strongly-typed configurations with sensible defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field


def _load_dotenv(dotenv_path: Path) -> None:
    """Minimal zero-dependency .env loader."""
    if not dotenv_path.is_file():
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("\"'")
                if key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


class Settings(BaseModel):
    """Global configuration settings for Agent Autopsy."""

    # Project paths
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent)
    DATA_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "data")
    BENCHMARK_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "benchmark" / "repository"
    )
    EXPECTED_RESULTS_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "benchmark" / "expected_results"
    )
    TRACES_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "data" / "traces"
    )
    DB_PATH: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "data" / "agent_autopsy.db"
    )
    SCENARIOS_FILE: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "scenarios" / "scenarios.json"
    )
    DEFAULT_POLICY_FILE: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "policies" / "default_policy.json"
    )

    # Model settings
    MODEL_PROVIDER: str = "mock"
    MODEL_NAME: str = "mock-coding-agent"
    OPENAI_API_BASE: str = "http://localhost:8000/v1"
    OPENAI_API_KEY: str = ""
    MOCK_MODE: bool = True

    # Execution limits & safety policies
    AGENT_TIMEOUT_SECONDS: int = 30
    TOOL_EXECUTION_TIMEOUT_SECONDS: int = 15
    MAX_TOOL_RETRIES: int = 3
    MAX_REPEATED_TOOL_CALLS: int = 5
    WORKSPACE_SANDBOX_STRICT: bool = True

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @classmethod
    def load(cls) -> Settings:
        """Instantiate Settings reading from environment variables."""
        base_dir = Path(__file__).resolve().parent
        _load_dotenv(base_dir / ".env")

        def _get_path(env_name: str, default: Path) -> Path:
            val = os.getenv(env_name)
            if not val:
                return default
            p = Path(val)
            return p if p.is_absolute() else base_dir / p

        return cls(
            BASE_DIR=base_dir,
            DATA_DIR=_get_path("DATA_DIR", base_dir / "data"),
            BENCHMARK_DIR=_get_path(
                "BENCHMARK_DIR", base_dir / "benchmark" / "repository"
            ),
            EXPECTED_RESULTS_DIR=_get_path(
                "EXPECTED_RESULTS_DIR", base_dir / "benchmark" / "expected_results"
            ),
            TRACES_DIR=_get_path("TRACES_DIR", base_dir / "data" / "traces"),
            DB_PATH=_get_path("DB_PATH", base_dir / "data" / "agent_autopsy.db"),
            SCENARIOS_FILE=_get_path(
                "SCENARIOS_FILE", base_dir / "scenarios" / "scenarios.json"
            ),
            DEFAULT_POLICY_FILE=_get_path(
                "DEFAULT_POLICY_FILE", base_dir / "policies" / "default_policy.json"
            ),
            MODEL_PROVIDER=os.getenv("MODEL_PROVIDER", "mock"),
            MODEL_NAME=os.getenv("MODEL_NAME", "mock-coding-agent"),
            OPENAI_API_BASE=os.getenv("OPENAI_API_BASE", "http://localhost:8000/v1"),
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
            MOCK_MODE=os.getenv("MOCK_MODE", "true").lower() in ("true", "1", "yes"),
            AGENT_TIMEOUT_SECONDS=int(os.getenv("AGENT_TIMEOUT_SECONDS", "30")),
            TOOL_EXECUTION_TIMEOUT_SECONDS=int(os.getenv("TOOL_EXECUTION_TIMEOUT_SECONDS", "15")),
            MAX_TOOL_RETRIES=int(os.getenv("MAX_TOOL_RETRIES", "3")),
            MAX_REPEATED_TOOL_CALLS=int(os.getenv("MAX_REPEATED_TOOL_CALLS", "5")),
            WORKSPACE_SANDBOX_STRICT=os.getenv("WORKSPACE_SANDBOX_STRICT", "true").lower()
            in ("true", "1", "yes"),
            LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),  # type: ignore
        )

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.TRACES_DIR.mkdir(parents=True, exist_ok=True)
        self.BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
        self.EXPECTED_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        self.SCENARIOS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.DEFAULT_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)


# Global settings singleton
settings = Settings.load()
settings.ensure_directories()

