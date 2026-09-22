# Internship Submission Form — Draft Answers

> Instructions: Fill in the sections marked `[FILL_IN]` after running the project.
> Do NOT submit placeholder values as real results.

---

## 1. GitHub Repo / Code Link

```
[FILL_IN: Add your GitHub repository URL after pushing]
Example: https://github.com/YOUR_USERNAME/agentic-code-review-agent
```

---

## 2. Upload Code

Upload the ZIP of the repository, or link to the GitHub repository above.

---

## 3. Architecture Diagram

See: `docs/architecture.md`

The architecture uses a Mermaid flowchart showing:
- User → Streamlit UI → Agent → Planner
- Tool Executor: GitHub Repository Tool + Code Quality Analyzer
- Failure Handler (retry logic)
- Report Generator
- Monitor / Log

---

## 4. Sample Run Transcripts/Logs

Three sample run logs are provided in `logs/`:

- `logs/sample_success_run.md` — Normal successful run (label: SUCCESS)
- `logs/sample_failure_recovery_run.md` — Deliberate failure + recovery (label: RECOVERED)
- `logs/sample_invalid_input_run.md` — Invalid URL input (label: INVALID_INPUT)

---

## 5. Write-up: Design Decisions & Limitations

See: `docs/writeup.md`

Key points:
- Domain: GitHub code quality review
- Two tools: GitHub REST API tool + Python AST analyzer
- LLM used only for planning and narrative, NOT for raw code analysis
- Failure injection via `simulate_failure` flag with 2-attempt retry
- Limitations: Python-only, heuristic rules, basic secret detection

---

## 6. Which domain/goal did you choose?

**Domain:** GitHub Code Quality Analysis

**Goal:** "Analyze a GitHub repository and identify potential code quality issues and suggest fixes."

I chose this domain because it naturally requires genuine tool orchestration:
- The agent must discover what files exist (GitHub tool)
- Decide what to analyze (file selector)
- Execute deterministic analysis (AST tool)
- Synthesize findings into an actionable report
- Handle real-world failures (rate limits, 404s, network issues)

---

## 7. Any assumptions or mock data used?

**Assumptions:**
- Repositories are public (no authentication required for the core flow)
- Python is the primary analysis language (other languages are skipped with a message)
- GitHub API rate limit is 60 req/hr unauthenticated, which is sufficient for small repositories

**Mock/Simulated data:**
- `test_repositories/sample_bad_repo/bad_code.py` — Synthetic Python file with intentionally planted issues for evaluation
- `evaluation/ground_truth.json` — Manually curated ground truth labels for the synthetic file
- Failure injection via `simulate_failure=True` — triggers a fake timeout on attempt 1 only

**No fabricated metrics:** All precision/recall/F1 scores are computed by running `python evaluation/run_evaluation.py`.

---

## 8. Total time spent

```
TOTAL_TIME_TO_BE_FILLED_AFTER_COMPLETION
```

---

## 9. Synthetic/Test Traces Used

Three labeled test traces in `evaluation/test_traces/`:

| Trace | Label | Description |
|-------|-------|-------------|
| `trace_001.json` | SUCCESS | Normal run, no failures |
| `trace_002.json` | RECOVERED | Simulated failure + retry recovery |
| `trace_003.json` | INVALID_INPUT | Malformed URL, agent stops gracefully |

**Generation method:** Traces were designed by hand based on the three key behavioral cases the agent must handle. Each trace specifies the input, expected plan, expected tool calls, expected failures, and expected output. The RECOVERED trace is validated by running the agent with `simulate_failure=True` and checking the `recoveries` field in the agent state.

---

## 10. Monitoring Report / Dashboard Output

The monitoring dashboard is embedded in the Streamlit UI (bottom of the page).

It reads from `logs/run_monitor.json` and displays:
- Total Runs
- Successful / Recovered / Failed
- Total Tool Calls, Retries, Recovered Failures
- Average Execution Time
- Total Findings Detected

After running the agent at least once, you can also read the raw log at `logs/run_monitor.json`.

```
MONITORING_SUMMARY_TO_BE_FILLED_AFTER_RUNNING
Example after 3 runs:
  Total Runs: 3
  Successful: 1
  Recovered: 1
  Failed: 1
  Total Tool Calls: 63
  Avg Execution Time: Xs
```

---

## 11. Write-up: Approach, Precision/Recall, Production Readiness

**Approach:**  
Built a 7-step agentic pipeline: validate → fetch → inspect → select → analyze → validate findings → report. Used Python AST for deterministic analysis (not LLM-dependent). LLM optional for plan refinement and plain-English narrative.

**Precision / Recall / F1 (actual results from `python evaluation/run_evaluation.py`):**
```
Test Cases:      1 (bad_code.py — 8 planted issues)
True Positives:  8
False Positives: 0
False Negatives: 0

Precision: 1.0000
Recall:    1.0000
F1 Score:  1.0000
```
All 8 planted issues detected with zero false positives.
Checks covered: long_function, hardcoded_secret, broad_exception, todo,
missing_docstring, unused_import, too_many_args, deep_nesting.

**Production Readiness:**  
This is a prototype suitable for demonstration. For production:
- Replace AST heuristics with Semgrep/Bandit rules
- Add async file fetching for large repos
- Implement persistent storage for trend analysis
- Add GitHub PR comment integration
- Add proper authentication management

---

## 12. How did you generate/label your test traces?

Test traces were generated by identifying the three core behavioral scenarios:

1. **SUCCESS** — The happy path where all steps complete without errors. Expected behavior is defined by the 7-step plan completing with tool calls returning success.

2. **RECOVERED** — A deliberate failure is injected at step 2 using `simulate_failure=True`. The agent must detect the failure (logged as `RetryRecord(status="failed")`), retry, and continue. Validated by checking that `state.recoveries` contains both a failed and successful attempt.

3. **INVALID_INPUT** — An obviously invalid URL is provided. The agent must stop at step 1 without making any API calls. Validated by checking that `state.tool_calls` is empty and `state.errors` contains the validation error.

Each trace in `evaluation/test_traces/` is a JSON document specifying: input, expected plan, expected tool calls, injected failures, and expected output fields to verify.
