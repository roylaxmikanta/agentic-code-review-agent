# Design Write-Up

## 1. Design Decisions

**Domain:** I chose GitHub code quality review because it creates a genuine agentic loop — the agent must discover information (what files exist), decide what to analyze, use real tools to fetch data, and synthesize findings into something actionable. This is more interesting than a toy calculator.

**Two distinct tools:** The GitHub Repository Tool and Code Quality Analyzer Tool have completely different responsibilities. The GitHub tool handles all network I/O and authentication; the analyzer is purely local and deterministic (AST-based). This separation makes each tool independently testable and replaceable.

**LLM usage:** The LLM is used only for planning (refining the step list) and narrative generation (summarizing findings in plain English). Critically, raw code is never sent to the LLM — only a findings summary (counts, categories, repo metadata). This is both cost-efficient and avoids leaking potentially private code.

**State management:** A single `AgentState` dataclass carries all run state. This is intentionally simple — no queues, no databases, no pub/sub. The state is self-contained and easy to inspect or serialize.

**Fallbacks everywhere:** If the LLM is unavailable, the plan and report still work using deterministic Python logic. If a file can't be fetched, it's skipped. If the whole tool fails, retry logic kicks in.

## 2. Agent Workflow

```
User Input → URL Validation → Repo Fetch (with retry) → File Tree →
File Selection → AST Analysis → Deduplication → LLM Narrative (optional) →
Structured Report → Monitor Log
```

The plan is shown to the user before execution starts. Each step reports its status in real time via the Streamlit callback.

## 3. Tool Selection

| Tool | Why chosen |
|------|-----------|
| GitHub REST API + `requests` | Simple HTTP, no SDK dependency, works unauthenticated for public repos |
| Python `ast` module | Built-in, deterministic, no external SAST dependency |
| `py_compile` (optional) | Lightweight syntax check, standard library only |

`requests` was chosen over `httpx` or `aiohttp` because it's simpler to read, widely known, and synchronous execution is fine at this scale.

## 4. Failure Handling

A `simulate_failure` flag injects a fake timeout on the first GitHub API call. This is visible in the UI as a deliberate red error box, followed by a recovery notification. The retry logic is capped at 2 attempts to prevent infinite loops. All retry attempts are logged as `RetryRecord` objects in the agent state.

Real failures handled: invalid URL, HTTP 404, HTTP 403 (rate limit), network timeout, empty repository, no Python files, AST parse errors, LLM API errors.

## 5. Evaluation

A synthetic test repository (`test_repositories/sample_bad_repo/bad_code.py`) contains intentionally planted issues: long function, hardcoded secrets, broad exceptions, TODO markers, missing docstrings, unused imports, too many arguments, and deep nesting.

`evaluation/ground_truth.json` records which issues are expected. `run_evaluation.py` runs the analyzer and computes precision, recall, and F1. Results are saved to `evaluation/evaluation_results.json`.

## 6. Limitations

- Only Python files are analyzed (AST is language-specific).
- The heuristics are intentionally simple — not equivalent to Semgrep, Bandit, or SonarQube.
- Secret detection is pattern-based; it will miss encrypted or obfuscated secrets.
- Unused import detection uses name matching and may produce false positives (e.g., `__all__` or dynamic imports).
- GitHub API rate limits (60 req/hr unauthenticated) can slow large analyses.
- The LLM narrative depends on the configured provider — if the model changes, tone and quality may vary.

## 7. What I Would Improve With More Time

1. **JavaScript/TypeScript support** via tree-sitter for multi-language analysis.
2. **PR integration** — comment findings directly on GitHub Pull Requests via the API.
3. **Persistent storage** — save findings to SQLite for trend analysis across multiple runs.
4. **Configurable rules** — let users enable/disable specific checks via a config file.
5. **Stronger secret detection** — entropy analysis (Shannon entropy on string literals) catches more real secrets.
6. **Async file fetching** — use `asyncio` + `httpx` to fetch all files in parallel, reducing analysis time.
7. **Better duplicate detection** — compare function ASTs for structural similarity, not just names.
8. **CI/CD integration** — run as a GitHub Action on every push.
