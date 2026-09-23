"""Streamlit UI for the Agentic GitHub Code Quality Reviewer."""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.agent import run_agent
from src.reporter import report_to_markdown
from src.monitor import load_monitor_data, compute_summary
from src.code_analyzer import calculate_metrics

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agentic GitHub Code Quality Reviewer",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Agentic GitHub Code Quality Reviewer")
st.markdown(
    "Provide a public GitHub repository URL and a goal. "
    "The agent will autonomously plan, analyze, and report code quality issues."
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    api_key_set = bool(os.getenv("LLM_API_KEY", ""))
    base_url = os.getenv("LLM_BASE_URL", "")
    model = os.getenv("LLM_MODEL", "")
    if api_key_set:
        provider = "Groq" if "groq" in base_url.lower() else "OpenAI-compatible"
        st.success(f"LLM ready ✅ ({provider} · `{model or 'default'}`)")
    else:
        st.info("No LLM key — static fallback report used.")
        st.caption("💡 Add a free Groq key in `.env` to enable AI narrative.")

    gh_token_set = bool(os.getenv("GITHUB_TOKEN", ""))
    if gh_token_set:
        st.success("GitHub token detected ✅")
    else:
        st.info("No GitHub token — unauthenticated (60 req/hr limit).")

    st.markdown("---")
    st.markdown(f"**Max files:** `{os.getenv('MAX_FILES', 30)}`")
    st.markdown(f"**Max file size:** `{int(os.getenv('MAX_FILE_SIZE', 50000))//1000} KB`")

    st.markdown("---")
    st.markdown("**Tools**")
    st.markdown("- ✅ Tool 1: GitHub Repository Tool")
    st.markdown("- ✅ Tool 2: Code Quality Analyzer (AST)")
    st.markdown("- ✅ Tool 3: Static Checker (py_compile)")

# ── Main form ─────────────────────────────────────────────────────────────────
with st.form("analysis_form"):
    repo_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/owner/repository",
        help="Must be a public GitHub repository URL.",
    )
    user_goal = st.text_area(
        "Goal",
        value="Analyze this GitHub repository and identify potential code quality issues and suggest fixes.",
        height=80,
    )

    col1, col2 = st.columns(2)
    with col1:
        simulate_failure = st.checkbox(
            "🔥 Simulate tool failure",
            help="Injects a simulated timeout on the first GitHub API call, then retries.",
        )
    with col2:
        use_static_checker = st.checkbox(
            "🔬 Enable static checker (Tool 3)",
            value=True,
            help="Runs py_compile and AST-based static checks in addition to the main analyzer.",
        )

    submitted = st.form_submit_button("🚀 Analyze Repository", type="primary")

# ── Run agent ─────────────────────────────────────────────────────────────────
if submitted:
    if not repo_url.strip():
        st.error("Please enter a GitHub repository URL.")
        st.stop()

    # Planning trace
    st.markdown("---")
    st.subheader("📋 Planning Trace")

    from src.planner import create_plan
    plan = create_plan(user_goal)

    with st.container():
        st.markdown("**Execution Plan:**")
        for i, step_text in enumerate(plan, 1):
            st.markdown(f"`{i}.` {step_text}")

    # Execution trace
    st.markdown("---")
    st.subheader("⚙️ Tool Execution")

    status_area = st.empty()
    step_log_lines = []

    def on_step(num: int, status: str, message: str):
        icon = {"running": "🔄", "success": "✅", "error": "❌", "warning": "⚠️"}.get(status, "🔄")
        step_log_lines.append(f"**[{num}/{len(plan)}]** {icon} {message}")
        with status_area.container():
            for line in step_log_lines:
                st.markdown(line)

    with st.spinner("Agent is running..."):
        start = time.time()
        state = run_agent(
            repo_url=repo_url.strip(),
            user_goal=user_goal.strip(),
            simulate_failure=simulate_failure,
            use_static_checker=use_static_checker,
            on_step=on_step,
        )
        elapsed = time.time() - start

    # ── Tool call summary ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🛠️ Tool Call Summary")

    # Group tool calls by tool name
    tool_counts: dict[str, dict] = {}
    for tc in state.tool_calls:
        name = tc.tool
        if name not in tool_counts:
            tool_counts[name] = {"calls": 0, "success": 0, "failed": 0}
        tool_counts[name]["calls"] += 1
        if tc.success:
            tool_counts[name]["success"] += 1
        else:
            tool_counts[name]["failed"] += 1

    for tool_name, counts in tool_counts.items():
        status_icon = "✅" if counts["failed"] == 0 else "⚠️"
        st.markdown(
            f"{status_icon} **{tool_name}** — "
            f"{counts['calls']} call(s), "
            f"{counts['success']} succeeded, "
            f"{counts['failed']} failed"
        )

    # ── Failure/Recovery display ───────────────────────────────────────────────
    if any(r.attempt > 1 or r.status == "failed" for r in state.recoveries):
        st.markdown("---")
        st.subheader("🔁 Failure & Recovery Log")
        for r in state.recoveries:
            if r.status == "failed":
                st.error(f"Attempt {r.attempt} — ❌ **{r.tool}** failed: {r.error}")
            else:
                success_label = "✅ succeeded" + (" (recovered)" if r.attempt > 1 else "")
                st.success(f"Attempt {r.attempt} — {success_label}: **{r.tool}**")
        if any(r.attempt > 1 and r.status == "success" for r in state.recoveries):
            st.info("ℹ️ One tool failure was detected and successfully recovered through retry.")

    # ── Errors ────────────────────────────────────────────────────────────────
    if state.errors:
        st.markdown("---")
        st.subheader("⚠️ Errors & Warnings")
        for err in state.errors:
            st.warning(err)

    # ── Static check results (Tool 3) ─────────────────────────────────────────
    static_results = [tc for tc in state.tool_calls if tc.tool == "static_checker"
                      and tc.success and tc.data]
    if static_results and use_static_checker:
        st.markdown("---")
        st.subheader("🔬 Static Check Results (Tool 3)")
        last = static_results[-1]
        data = last.data
        total_static = data.get("total_static_issues", 0)
        st.markdown(
            f"Files checked: **{data.get('files_checked', 0)}** | "
            f"Static issues: **{total_static}**"
        )
        if data.get("results"):
            for file_result in data["results"]:
                issues = [c for c in file_result.get("checks", []) if c.get("status") == "warning"]
                if issues:
                    with st.expander(f"`{file_result['file']}` — {len(issues)} static issue(s)"):
                        for issue in issues:
                            line_info = f"line {issue['line']}" if issue.get("line") else ""
                            st.markdown(f"- ⚠️ **{issue['check']}** {line_info}: {issue['message']}")

    # ── Findings ──────────────────────────────────────────────────────────────
    if state.findings:
        st.markdown("---")
        st.subheader("🐛 Code Quality Findings")

        metrics = calculate_metrics(state.findings)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total", len(state.findings))
        c2.metric("🔴 Critical", metrics["Critical"])
        c3.metric("🟠 High", metrics["High"])
        c4.metric("🟡 Medium", metrics["Medium"])
        c5.metric("🟢 Low", metrics["Low"])

        severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        sorted_findings = sorted(
            state.findings, key=lambda f: severity_order.get(f.severity, 99)
        )

        for f in sorted_findings:
            sev_emoji = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(f.severity, "⚪")
            with st.expander(
                f"{sev_emoji} **{f.issue_id}** — {f.description} (`{f.file}`)",
                expanded=False
            ):
                col_a, col_b = st.columns(2)
                col_a.markdown(f"**Category:** {f.category}")
                col_b.markdown(f"**Severity:** {f.severity}")
                if f.line:
                    st.markdown(f"**Line:** {f.line}")
                st.code(f.evidence, language=None)
                st.markdown(f"**Recommendation:** {f.recommendation}")

    elif not state.errors:
        st.success("✅ No issues detected (or repository has no Python files).")

    # ── Final Report ──────────────────────────────────────────────────────────
    if state.final_report:
        st.markdown("---")
        st.subheader("📄 Final Report")

        report_md = report_to_markdown(state.final_report)

        with st.expander("View Markdown Report", expanded=True):
            st.markdown(report_md)

        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                "⬇️ Download report.json",
                data=json.dumps(state.final_report, indent=2, default=str),
                file_name="report.json",
                mime="application/json",
            )
        with dl_col2:
            st.download_button(
                "⬇️ Download report.md",
                data=report_md,
                file_name="report.md",
                mime="text/markdown",
            )

        st.caption(
            f"Report also saved to `reports/` directory. "
            f"Analysis completed in **{elapsed:.2f}s** | "
            f"Files analyzed: **{len(state.files_analyzed)}**"
        )

# ── Monitoring Dashboard ──────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📊 Monitoring Dashboard")

records = load_monitor_data()
if not records:
    st.info("No runs recorded yet. Run an analysis to see monitoring data.")
else:
    summary = compute_summary(records)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Runs", summary["total_runs"])
    col2.metric("✅ Successful", summary["successful_runs"])
    col3.metric("🔁 Recovered", summary["recovered_runs"])
    col4.metric("❌ Failed", summary["failed_runs"])

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Tool Calls", summary["total_tool_calls"])
    col6.metric("Retries", summary["total_retries"])
    col7.metric("Avg Time (s)", summary["average_execution_time_seconds"])
    col8.metric("Total Findings", summary["total_findings_detected"])

    with st.expander("📜 Run History (last 10)", expanded=False):
        for r in reversed(records[-10:]):
            status_icon = {"success": "✅", "failed": "❌", "recovered": "🔁"}.get(r["status"], "❓")
            repo_name = r["repository_url"].rstrip("/").split("/")[-1] or r["repository_url"]
            st.markdown(
                f"{status_icon} `{r['timestamp']}` — **{repo_name}** "
                f"({r['files_analyzed']} files, {r['total_findings']} findings, {r['execution_time_seconds']}s)"
            )

st.markdown("---")
st.caption("Agentic GitHub Code Quality Reviewer · Built for AI Engineer Internship Assignment")
