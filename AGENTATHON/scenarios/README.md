# Agent Autopsy — Foundation v0.1
**TRINITY.EXE | Agentathon 2026 | Developer Productivity**

*A Model-Agnostic AI Agent Testing, Diagnosis, and Improvement Platform.*

---

## 1. Overview

Agent Autopsy is an external reliability, testing, and improvement platform for AI agents. Rather than acting as a simple chatbot or unconstrained code runner, Agent Autopsy treats AI agents (initially **AI Coding Agents**) as targets under test.

It systematically:
1. Profiles the target agent's capabilities, schemas, and risk boundaries.
2. Subject the agent to reproducible test scenarios with deterministic fault injection.
3. Captures immutable, tamper-evident execution traces linked via SHA-256 hash chains.
4. Identifies failures, diagnoses root causes, and generates evidence-based citations.
5. Synthesizes schema-bounded policy repair proposals (e.g., loop prevention, retry thresholds).
6. Evaluates fixes independently via regression testing before human approval.

---

## 2. Core Architectural Principles

- **Separation of Target and Evaluator**: The coding agent under test and Agent Autopsy are strictly separated.
- **Model-Agnostic Integration**: Supports OpenAI-compatible endpoints (vLLM, SGLang, local/hosted endpoints) and offline deterministic mock modes.
- **Strict Sandboxing & Least Privilege**:
  - File tools are strictly bounded to a dedicated benchmark directory with symlink/path traversal rejection (`resolve_safe_path`).
  - No arbitrary shell execution; only whitelisted `pytest` commands run via non-shell subprocesses with timeouts and sanitized environment variables.
- **Cryptographic Trace Integrity**: Every execution event is sealed with an incremental sequence number, UTC timestamp, and SHA-256 hash referencing the previous event.
- **Schema-Bounded Policy Patches**: Patches can only modify verified, approved policy fields (`APPROVED_POLICY_FIELDS`) preventing prompt injection or arbitrary code execution.

---

## 3. Project Structure

```
agent-autopsy/
├── config.py                  # Strongly-typed environment configuration (Pydantic)
├── main.py                    # Verification and CLI entrypoint
├── requirements.txt           # Core dependencies (pydantic, pytest, httpx, streamlit)
├── .env.example               # Configuration template
├── README.md
│
├── src/
│   ├── core/
│   │   ├── contracts.py       # Core Pydantic contracts (AgentProfile, TestCase, ExecutionEvent, Diagnosis, PolicyPatch)
│   ├── adapters/
│   │   ├── base.py            # Model-agnostic LLM adapter base interface
│   │   └── mock_adapter.py    # Deterministic mock adapter for offline benchmarking
│   ├── agents/
│   │   └── coding_agent.py    # BaseCodingAgent and DeterministicMockCodingAgent with scenario state machines
│   ├── tools/
│   │   ├── base_tool.py       # BaseTool abstract class with sandbox path resolver
│   │   ├── file_tools.py      # list_files, read_file, write_file, search_code tools
│   │   ├── execution_tools.py # run_tests tool with sanitized pytest runner
│   │   └── registry.py        # ToolRegistry managing schemas and dispatch
│   ├── runner/                # Scenario manager, fault injector, trace recorder (Milestone 2)
│   ├── evaluation/            # Assertion engine and regression runner (Milestone 5)
│   └── storage/               # SQLite and failure memory storage
│
├── benchmark/
│   ├── repository/            # Isolated mock codebase with intentional bugs
│   │   ├── data_processor/    # calculator.py, validator.py, formatter.py
│   │   └── tests/             # Pytest test suite
│   └── expected_results/      # Ground-truth fix definitions (e.g. expected_s1_fix.json)
│
├── scenarios/
│   └── scenarios.json         # Seeded scenarios (S1-S6)
├── policies/
│   └── default_policy.json    # Baseline agent operational policy
└── tests/
    ├── test_contracts.py      # Contract validation & hash-chain integrity tests
    ├── test_tools.py          # Sandbox and tool security tests
    └── test_mock_agent.py     # Deterministic mock coding agent tests
```

---

## 4. Benchmark Repository

Located at `benchmark/repository/`:
- `data_processor/calculator.py`: Contains an intentional calculation bug in `calculate_discount` (subtracting flat discount percent instead of price percentage).
- `data_processor/validator.py`: Email and number validation utilities (regression suite).
- `data_processor/formatter.py`: Currency and string formatting utilities (regression suite).
- `tests/`: 10 unit tests where exactly 2 fail under the intentional bug and 8 pass.

---

## 5. Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run test suite
pytest tests -v

# Run benchmark test suite directly
PYTHONPATH=benchmark/repository pytest benchmark/repository/tests
```

