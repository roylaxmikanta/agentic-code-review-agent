# Architecture

## System Overview

```mermaid
flowchart TD
    User([👤 User]) -->|URL + Goal| UI[Streamlit UI\napp.py]
    UI -->|validated input| Agent[Agent\nagent.py]
    Agent -->|goal| Planner[Planner\nplanner.py]
    Planner -->|plan steps| Agent

    Agent --> Step1[Step 1: Validate URL]
    Agent --> Step2[Step 2: Fetch Repo Info]
    Agent --> Step3[Step 3: Fetch File Tree]
    Agent --> Step4[Step 4: Select Files]
    Agent --> Step5[Step 5: Analyze Files]
    Agent --> Step6[Step 6: Validate Findings]
    Agent --> Step7[Step 7: Generate Report]

    Step2 --> GHT[GitHub Repository Tool\ngithub_tool.py]
    Step3 --> GHT
    Step4 --> GHT
    Step5 --> CA[Code Quality Analyzer\ncode_analyzer.py]

    GHT -->|success| Agent
    GHT -->|failure| FH[Failure Handler\nretry logic in agent.py]
    FH -->|retry| GHT

    CA --> Reporter[Reporter\nreporter.py]
    Reporter -->|JSON + MD| UI

    Agent --> Monitor[Monitor\nmonitor.py]
    Monitor -->|run metrics| LogFile[(logs/run_monitor.json)]

    UI -->|read| LogFile

    Planner -.->|optional| LLM[LLM API\nOpenAI-compatible]
    Reporter -.->|optional narrative| LLM
```

## Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| Streamlit UI | `app.py` | User input, step display, findings, downloads, monitoring |
| Agent | `src/agent.py` | Orchestrates all steps, handles retry logic |
| Planner | `src/planner.py` | Converts goal to execution plan, optional LLM refinement |
| GitHub Tool | `src/github_tool.py` | URL validation, repo metadata, file tree, file content |
| Code Analyzer | `src/code_analyzer.py` | AST-based Python quality analysis |
| Reporter | `src/reporter.py` | Builds JSON report, renders Markdown |
| Monitor | `src/monitor.py` | Records run metrics, computes aggregate stats |
| Models | `src/models.py` | Shared dataclasses (AgentState, Finding, ToolResult, etc.) |
| Evaluator | `src/evaluator.py` | Precision/recall/F1 evaluation framework |

## Data Flow

```
User Input (URL + Goal)
        │
        ▼
URL Validation (regex)
        │
        ▼
GitHub API → repo metadata → repo file tree → file contents
        │
        ▼ (if failure)
Retry Logic (up to 2 attempts)
        │
        ▼
AST Parser → Code Quality Findings
        │
        ▼
Deduplication + Severity Sort
        │
        ▼
Optional LLM Narrative (from findings summary, NOT raw code)
        │
        ▼
Structured Report (JSON + Markdown)
        │
        ▼
Monitor Log → Aggregate Statistics
```

## Tool Interface Contract

All tools return a `ToolResult`:

```python
@dataclass
class ToolResult:
    success: bool
    tool: str
    data: Optional[Any]
    error: Optional[str]
    attempt: int = 1
```

## Failure & Recovery

```
Attempt 1 → simulate_failure=True → ToolResult(success=False, error="Simulated timeout")
                                              │
                                              ▼
                                    RetryRecord logged
                                              │
                                              ▼
Attempt 2 → simulate_failure=False (attempt>1) → ToolResult(success=True)
                                              │
                                              ▼
                                    RetryRecord logged
                                    Execution continues
```
