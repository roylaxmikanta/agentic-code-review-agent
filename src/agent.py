"""Agent — orchestrates the full code-review workflow."""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from src.models import AgentState, ToolResult, RetryRecord, Finding
from src.github_tool import parse_github_url, get_repo_info, get_repo_tree, get_file_content
from src.code_analyzer import analyze_repository, calculate_metrics
from src.planner import create_plan, summarize_findings_with_llm
from src.reporter import build_report, report_to_markdown
from src import monitor

# Limits to keep API usage reasonable
MAX_FILES = int(os.getenv("MAX_FILES", "30"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "50000"))  # bytes
MAX_RETRIES = 2
REPORTS_DIR = Path("reports")


def run_agent(
    repo_url: str,
    user_goal: str,
    simulate_failure: bool = False,
    use_static_checker: bool = True,
    on_step: Optional[Callable[[int, str, str], None]] = None,
) -> AgentState:
    """
    Main agent entry point.

    Args:
        repo_url: GitHub repository URL.
        user_goal: User's natural-language goal.
        simulate_failure: Whether to inject a controlled tool failure.
        use_static_checker: Whether to run the optional Tool 3 (py_compile static check).
        on_step: Optional callback on each step: on_step(step_num, status, message).

    Returns:
        AgentState with all results populated.
    """
    state = AgentState(
        user_goal=user_goal,
        repository_url=repo_url,
        simulate_failure=simulate_failure,
        start_time=time.time(),
    )

    def step(num: int, msg: str, status: str = "running"):
        state.current_step = num
        if on_step:
            on_step(num, status, msg)

    # ── Step 0: Generate plan ──────────────────────────────────────────────────
    state.plan = create_plan(user_goal)

    # ── Step 1: Validate URL ───────────────────────────────────────────────────
    step(1, "Validating repository URL...")
    parsed = parse_github_url(repo_url)
    if not parsed:
        state.errors.append("Invalid GitHub URL format.")
        step(1, "Invalid GitHub URL.", "error")
        state.execution_time = time.time() - state.start_time
        _finalize(state, "failed")
        return state

    owner, repo = parsed
    step(1, f"URL valid — owner={owner}, repo={repo}", "success")

    # ── Step 2: Fetch repository metadata ─────────────────────────────────────
    step(2, "Fetching repository metadata...")
    repo_result = _fetch_with_retry(
        owner, repo,
        simulate_failure=simulate_failure,
        state=state,
    )

    if not repo_result.success:
        state.errors.append(f"Could not fetch repository: {repo_result.error}")
        step(2, f"Failed: {repo_result.error}", "error")
        state.execution_time = time.time() - state.start_time
        _finalize(state, "failed")
        return state

    state.repository_info = repo_result.data
    step(2, f"Repository found: {repo_result.data.get('full_name')}", "success")

    # ── Step 3: Fetch file tree ────────────────────────────────────────────────
    step(3, "Inspecting repository file tree...")
    branch = repo_result.data.get("default_branch", "main")
    tree_result = get_repo_tree(owner, repo, branch)
    state.tool_calls.append(tree_result)

    if not tree_result.success:
        state.errors.append(f"Could not fetch file tree: {tree_result.error}")
        step(3, f"Failed: {tree_result.error}", "error")
        state.execution_time = time.time() - state.start_time
        _finalize(state, "failed")
        return state

    all_files = tree_result.data["files"]
    step(3, f"Found {len(all_files)} files in repository.", "success")

    # ── Step 4: Select Python files ────────────────────────────────────────────
    step(4, "Selecting supported Python source files...")
    python_files = [
        f for f in all_files
        if f["path"].endswith(".py")
        and not f["path"].startswith(".")
        and f.get("size", 0) < MAX_FILE_SIZE
    ]
    python_files = python_files[:MAX_FILES]

    if not python_files:
        state.errors.append("No Python source files found in this repository.")
        step(4, "No Python files found. Only Python analysis is currently supported.", "warning")
        state.execution_time = time.time() - state.start_time
        state.final_report = build_report(state)
        _save_report(state)
        _finalize(state, "success")
        return state

    step(4, f"Selected {len(python_files)} Python files for analysis.", "success")

    # ── Step 5: Fetch and analyze files ───────────────────────────────────────
    step(5, f"Analyzing {len(python_files)} Python file(s)...")
    file_contents = []
    for file_info in python_files:
        file_result = get_file_content(owner, repo, file_info["path"])
        state.tool_calls.append(file_result)
        if file_result.success:
            file_contents.append({
                "path": file_info["path"],
                "content": file_result.data["content"],
            })
            state.files_analyzed.append(file_info["path"])

    # Tool 2: AST code quality analysis
    analysis_result = analyze_repository(file_contents)
    state.tool_calls.append(analysis_result)

    if analysis_result.success:
        state.findings = analysis_result.data["findings"]
        step(5, f"Code analysis complete — {len(state.findings)} findings detected.", "success")
    else:
        state.errors.append(f"Analysis error: {analysis_result.error}")
        step(5, "Analysis encountered an error.", "error")

    # Tool 3 (optional): py_compile static checker
    if use_static_checker and file_contents:
        step(5, "Running optional static syntax check (Tool 3)...")
        try:
            from src.static_checker import check_repository_files
            static_result = check_repository_files(file_contents)
            state.tool_calls.append(static_result)
            if static_result.success:
                total_static = static_result.data.get("total_static_issues", 0)
                step(5, f"Static check complete — {total_static} additional static issue(s) found.", "success")
        except Exception as e:
            # Static checker is optional — never crash the main flow
            state.errors.append(f"Static checker skipped: {str(e)}")

    # ── Step 6: Validate and prioritize findings ───────────────────────────────
    step(6, "Validating and prioritizing findings...")
    seen = set()
    deduped = []
    for f in state.findings:
        key = (f.file, f.line, f.category)
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    state.findings = deduped

    metrics = calculate_metrics(state.findings)
    step(6, f"Validated: {metrics['Critical']} critical, {metrics['High']} high, "
         f"{metrics['Medium']} medium, {metrics['Low']} low.", "success")

    # ── Step 7: Generate report ────────────────────────────────────────────────
    step(7, "Generating final report...")
    llm_narrative = None

    api_key = os.getenv("LLM_API_KEY", "")
    if api_key:
        from collections import Counter
        cats = Counter(f.category for f in state.findings)
        top_cats = [cat for cat, _ in cats.most_common(3)]
        findings_summary = {
            "files_analyzed": len(state.files_analyzed),
            "total_findings": len(state.findings),
            **metrics,
            "categories": top_cats,
        }
        llm_narrative = summarize_findings_with_llm(findings_summary, state.repository_info or {})

    state.execution_time = time.time() - state.start_time
    state.final_report = build_report(state, llm_narrative)

    # Save report to reports/ directory
    _save_report(state)

    step(7, "Report generated and saved successfully.", "success")

    run_status = "success"
    if any(r.attempt > 1 and r.status == "success" for r in state.recoveries):
        run_status = "recovered"

    _finalize(state, run_status)
    return state


def _fetch_with_retry(owner: str, repo: str, simulate_failure: bool, state: AgentState) -> ToolResult:
    """
    Attempts to fetch repo info, retrying up to MAX_RETRIES times.
    The first attempt may be a simulated failure if simulate_failure=True.
    """
    last_result = None
    for attempt in range(1, MAX_RETRIES + 1):
        inject = simulate_failure and attempt == 1 and not state.failure_triggered
        result = get_repo_info(owner, repo, simulate_failure=inject, attempt=attempt)

        retry_record = RetryRecord(
            tool="github_repository",
            attempt=attempt,
            status="success" if result.success else "failed",
            error=result.error,
        )
        state.recoveries.append(retry_record)
        state.tool_calls.append(result)

        if inject and not result.success:
            state.failure_triggered = True

        if result.success:
            last_result = result
            break
        last_result = result

    return last_result


def _save_report(state: AgentState):
    """Saves report.json and report.md to the reports/ directory."""
    if not state.final_report:
        return
    try:
        REPORTS_DIR.mkdir(exist_ok=True)
        run_id = str(uuid.uuid4())[:8]
        repo_slug = state.repository_url.rstrip("/").split("/")[-1] or "report"

        json_path = REPORTS_DIR / f"{repo_slug}_{run_id}.json"
        md_path = REPORTS_DIR / f"{repo_slug}_{run_id}.md"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(state.final_report, f, indent=2, default=str)

        md_content = report_to_markdown(state.final_report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
    except Exception:
        pass  # Report saving is best-effort — never crash the agent


def _finalize(state: AgentState, run_status: str):
    """Records run metrics to the monitor log."""
    total_calls = len(state.tool_calls)
    success_calls = sum(1 for t in state.tool_calls if t.success)
    failed_calls = total_calls - success_calls
    retries = sum(1 for r in state.recoveries if r.attempt > 1)
    recovered = 1 if any(r.status == "success" and r.attempt > 1 for r in state.recoveries) else 0
    llm_calls = 1 if os.getenv("LLM_API_KEY") and state.final_report else 0

    monitor.record_run(
        run_id=str(uuid.uuid4())[:8],
        repository_url=state.repository_url,
        status=run_status,
        execution_time=state.execution_time,
        tool_calls=total_calls,
        successful_tool_calls=success_calls,
        failed_tool_calls=failed_calls,
        retries=retries,
        recovered_failures=recovered,
        files_analyzed=len(state.files_analyzed),
        total_findings=len(state.findings),
        llm_calls=llm_calls,
        errors=state.errors,
    )
