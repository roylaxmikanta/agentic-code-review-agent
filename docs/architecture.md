# Architecture

## Diagram

![Architecture Diagram](architecture.png)

## System Overview

```mermaid
flowchart TD
    User([👤 User]) -->|URL + Goal| UI[Streamlit UI\napp.py]
    UI -->|validated input| Agent[Agent\nagent.py]
    Agent -->|goal| Planner[Planner\nplanner.py]
    Planner -.->|optional plan refinement| LLM[Groq LLM\nllama-3.1-8b-instant]
    Planner -->|plan steps| Agent

    Agent --> Step1[Step 1: Validate URL]
    Agent --> Step2[Step 2: Fetch Repo Info]
    Agent --> Step3[Step 3: Fetch File Tree]
    Agent --> Step4[Step 4: Select Files]
    Agent --> Step5[Step 5: Analyze Files]
    Agent --> Step6[Step 6: Validate Findings]
    Agent --> Step7[Step 7: Generate Report]

    Step2 --> T1[Tool 1: GitHub Repository Tool\ngithub_tool.py]
    Step3 --> T1
    Step4 --> T1
    Step5 --> T2[Tool 2: Code Quality Analyzer\ncode_analyzer.py]
    Step5 --> T3[Tool 3: Static Checker\nstatic_checker.py]

    T1 -->|success| Agent
    T1 -->|failure| FH[Failure Handler\nretry logic in agent.py]
    FH -->|retry| T1

    T2 --> Reporter[Reporter\nreporter.py]
    T3 --> Reporter
    Reporter -->|JSON + MD| ReportsDir[(reports/)]
    Reporter -->|rendered| UI

    Agent --> Monitor[Monitor\nmonitor.py]
    Monitor -->|run metrics| LogFile[(logs/run_monitor.json)]
    UI -->|dashboard| LogFile

    Reporter -.->|findings summary only| LLM
```

## Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| Streamlit UI | `app.py` | User input, step display, findings, downloads, monitoring dashboard |
| Agent | `src/agent.py` | Orchestrates all 7 steps, handles retry logic, saves reports |
| Planner | `src/planner.py` | Converts goal to execution plan; optional Groq LLM refinement |
| Tool 1: GitHub | `src/github_tool.py` | URL validation, repo metadata, file tree, file content |
| Tool 2: Analyzer | `src/code_analyzer.py` | AST-based Python quality analysis (10 check types) |
| Tool 3: Static | `src/static_checker.py` | py_compile syntax check + AST static checks |
| Reporter | `src/reporter.py` | Builds JSON report, renders Markdown |
| Monitor | `src/monitor.py` | Records per-run metrics, computes aggregate stats |
| Models | `src/models.py` | Shared dataclasses (AgentState, Finding, ToolResult, etc.) |
| Evaluator | `src/evaluator.py` | Precision/recall/F1 evaluation framework |

## Data Flow

```
User Input (URL + Goal)
        │
        ▼
URL Validation (regex — no API call)
        │
        ▼
GitHub API → repo metadata → repo file tree → file contents (Tool 1)
        │
        ▼ (on failure)
Retry Logic (up to 2 attempts, logged as RetryRecord)
        │
        ▼
AST Parser → Code Quality Findings (Tool 2)
py_compile → Static Check Findings (Tool 3)
        │
        ▼
Deduplication + Severity Sort
        │
        ▼
Optional Groq Narrative  ←── findings summary ONLY (no raw code)
        │
        ▼
Structured Report → reports/ (JSON + MD)
        │
        ▼
Monitor Log → logs/run_monitor.json → Aggregate Stats in UI
```

## LLM Integration (Groq)

The LLM receives **only**:
- Repository name and language
- Count of findings per severity
- Top 3 finding categories

Raw source code is **never** sent to the LLM.

## Failure & Recovery Flow

```
Attempt 1 → simulate_failure=True
          → ToolResult(success=False, error="Simulated timeout")
          → RetryRecord(attempt=1, status="failed") logged
          ↓
Attempt 2 → simulate_failure=False (attempt > 1 skips injection)
          → ToolResult(success=True)
          → RetryRecord(attempt=2, status="success") logged
          ↓
Execution continues normally
Final report notes: "One failure recovered through retry"
```
