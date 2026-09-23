---
title: Agentic GitHub Code Quality Reviewer
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: "1.40.0"
app_file: app.py
pinned: false
license: mit
short_description: Agentic AI that reviews GitHub repos for code quality issues
---

# 🔍 Agentic GitHub Code Quality Reviewer

An agentic AI system that autonomously analyzes GitHub repositories for code quality issues, handles failures gracefully, and generates structured reports.

Built as a take-home assignment for an AI Engineer Internship.

---

## Overview

The agent accepts a GitHub repository URL and a natural-language goal, then:

1. **Plans** — creates a visible execution plan before doing anything
2. **Fetches** — uses the GitHub REST API to get repository metadata and file contents
3. **Analyzes** — runs Python AST-based static analysis to detect real code quality issues
4. **Recovers** — detects and retries on tool failures
5. **Reports** — generates a structured JSON + Markdown report with findings, metrics, and recommendations

---

## Why This Project?

GitHub code quality review is a genuinely useful agentic task: the agent must discover information, make decisions about what to analyze, use multiple tools with different responsibilities, handle real-world failures (rate limits, 404s, network errors), and synthesize findings into something actionable. It naturally demonstrates all the key agentic properties without artificial complexity.

---

## Features

- ✅ Natural-language goal input
- ✅ Visible execution plan before each run
- ✅ Two distinct tools: GitHub API + Python AST Analyzer
- ✅ Deliberate failure injection + retry/recovery
- ✅ Structured JSON and Markdown report export
- ✅ Secret detection (pattern-based, masked in output)
- ✅ Monitoring dashboard (aggregate run metrics)
- ✅ Evaluation framework (precision / recall / F1)
- ✅ Synthetic test repository with ground truth
- ✅ Optional LLM integration (fallback available)
- ✅ No API key required for public repository analysis

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full Mermaid diagram.

```
User → Streamlit UI → Agent → Planner
                                ↓
                         Tool Executor
                         ├── GitHub Repository Tool
                         └── Code Quality Analyzer
                                ↓
                         Failure Handler (retry)
                                ↓
                         Report Generator
                                ↓
                         Monitor / Log → Final Output
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit |
| HTTP | requests |
| Code Analysis | Python `ast` (standard library) |
| LLM (optional) | OpenAI-compatible API |
| Testing | pytest |
| Config | python-dotenv |

No unnecessary dependencies. The core project works without any API keys.

---

## Project Structure

```
agentic-code-review-agent/
│
├── app.py                          # Streamlit UI
├── requirements.txt
├── .env.example
├── .gitignore
│
├── src/
│   ├── agent.py                    # Main agent orchestrator
│   ├── planner.py                  # Plan generation + LLM refinement
│   ├── github_tool.py              # GitHub REST API tool
│   ├── code_analyzer.py            # Python AST analysis tool
│   ├── reporter.py                 # JSON + Markdown report builder
│   ├── monitor.py                  # Run metrics logger
│   ├── evaluator.py                # Precision/recall/F1 evaluation
│   └── models.py                   # Shared dataclasses
│
├── tests/
│   ├── test_github_tool.py
│   ├── test_code_analyzer.py
│   ├── test_agent.py
│   └── test_evaluator.py
│
├── evaluation/
│   ├── ground_truth.json           # Expected findings per test file
│   ├── run_evaluation.py           # Evaluation runner
│   └── test_traces/                # Labeled behavioral traces
│       ├── trace_001.json          # SUCCESS
│       ├── trace_002.json          # RECOVERED
│       └── trace_003.json          # INVALID_INPUT
│
├── test_repositories/
│   └── sample_bad_repo/
│       └── bad_code.py             # Synthetic file with known issues
│
├── logs/
│   ├── sample_success_run.md
│   ├── sample_failure_recovery_run.md
│   └── sample_invalid_input_run.md
│
├── docs/
│   ├── architecture.md
│   ├── writeup.md
│   └── form_answers.md
│
└── reports/                        # Generated reports saved here
```

---

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/agentic-code-review-agent
cd agentic-code-review-agent

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

---

## Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Optional — enables LLM plan refinement and narrative generation
LLM_API_KEY=your_openai_api_key_here
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1

# Optional — increases GitHub rate limit from 60 to 5000 req/hr
GITHUB_TOKEN=your_github_token_here

# Analysis limits (optional — defaults shown)
MAX_FILES=30
MAX_FILE_SIZE=50000
```

> **Important:** Never commit `.env`. It is in `.gitignore`.  
> Public repository analysis works without any tokens.

---

## Run

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## Example Input

```
Repository URL: https://github.com/psf/requests
Goal: Analyze this GitHub repository and identify potential code quality issues and suggest fixes.
```

---

## How the Agent Works

### 1. Planning
The agent converts the user's goal into a concrete execution plan (7 steps). If an LLM API key is configured, it may refine the plan. The plan is shown to the user *before* any tool is called.

### 2. Tool Execution
**GitHub Repository Tool** (`src/github_tool.py`):
- Validates the URL with regex
- Fetches repository metadata via GitHub REST API
- Retrieves the file tree
- Downloads individual file contents

**Code Quality Analyzer** (`src/code_analyzer.py`):
- Parses Python files with the built-in `ast` module
- Detects: long functions, deep nesting, broad exceptions, missing docstrings, unused imports, too many arguments, TODO markers, long lines, hardcoded secrets

### 3. Failure Recovery
If a tool call fails, the agent logs a `RetryRecord`, waits briefly, and retries (up to 2 attempts total). The failure and recovery are shown in the UI in real time.

### 4. Report Generation
All findings are deduplicated, sorted by severity, and assembled into a structured report. The report is available for download as JSON or Markdown.

---

## Failure Simulation

Check **"Simulate tool failure"** in the UI, or set `simulate_failure=True` when calling `run_agent()`.

This injects a fake timeout on the first GitHub API call. The agent:
1. Logs the failure
2. Displays an error in the UI
3. Retries immediately
4. Continues execution normally after recovery
5. Notes the recovered failure in the final report

---

## Testing

```bash
pytest tests/ -v
```

Tests cover:
- URL parsing (valid, invalid, edge cases)
- Simulated failure injection
- Long function detection
- Secret detection and masking
- TODO marker detection
- Broad exception detection
- Missing docstring detection
- Unused import detection
- Retry logic and recovery records
- Report structure and correctness
- Precision/recall/F1 math

---

## Evaluation

```bash
python evaluation/run_evaluation.py
```

This runs the code analyzer against `test_repositories/sample_bad_repo/bad_code.py` and compares the detected issues to `evaluation/ground_truth.json`.

Output:
```
Evaluation Results
------------------
Test Cases: 1
True Positives: X
False Positives: X
False Negatives: X

Precision: X.XX
Recall:    X.XX
F1 Score:  X.XX
```

Results are saved to `evaluation/evaluation_results.json`.

---

## Monitoring

The Streamlit UI includes a monitoring dashboard at the bottom of the page showing aggregate statistics from all runs:

- Total / Successful / Recovered / Failed runs
- Total tool calls, retries, recovered failures
- Average execution time
- Total findings detected
- Run history (last 10 runs)

Raw data is in `logs/run_monitor.json`.

---

##  Limitations
 
- **Python only** — AST analysis is language-specific. Other languages are reported as unsupported.
- **Heuristic rules** — Rules are intentionally simple. Not equivalent to Semgrep, Bandit, or SonarQube.
- **Secret detection** — Pattern-based. Will miss obfuscated or encrypted secrets.
- **Unused import detection** — Name matching only; may have false positives with dynamic imports.
- **GitHub rate limits** — 60 req/hr unauthenticated. Large repositories may hit this limit.
- **LLM dependency** — Narrative quality depends on the configured model. Fallback is always available.
- **No PR integration** — Currently read-only. Does not post findings to GitHub.

---

## Future Improvements

- JavaScript/TypeScript support via tree-sitter
- Async file fetching for faster large-repo analysis
- GitHub Actions integration for automated PR review
- Persistent findings storage for trend analysis
- Configurable rule sets
- Entropy-based secret detection
- GitHub PR comment posting

---

## Assignment Deliverables

| Item | Location |
|------|----------|
| Source code | `src/`, `app.py` |
| Architecture diagram | `docs/architecture.md` |
| Sample run logs | `logs/` |
| Technical write-up | `docs/writeup.md` |
| Form answers | `docs/form_answers.md` |
| Evaluation traces | `evaluation/test_traces/` |
| Ground truth | `evaluation/ground_truth.json` |
| Evaluation results | `evaluation/evaluation_results.json` (after running) |
| Monitoring report | `logs/run_monitor.json` (after running) |
