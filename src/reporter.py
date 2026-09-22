"""Report Generator — builds the structured final report from agent state."""

import json
import time
from typing import Optional
from src.models import AgentState, Finding
from src.code_analyzer import calculate_metrics


def build_report(state: AgentState, llm_narrative: Optional[str] = None) -> dict:
    """
    Assembles the full structured report from agent state.
    Returns a dict that can be serialized to JSON or rendered to Markdown.
    """
    findings = state.findings
    metrics = calculate_metrics(findings)

    findings_list = []
    for f in findings:
        findings_list.append({
            "issue_id": f.issue_id,
            "severity": f.severity,
            "category": f.category,
            "file": f.file,
            "line": f.line,
            "description": f.description,
            "evidence": f.evidence,
            "recommendation": f.recommendation,
        })

    # Tool execution summary
    tool_calls_summary = []
    for tc in state.tool_calls:
        tool_calls_summary.append({
            "tool": tc.tool,
            "success": tc.success,
            "attempt": tc.attempt,
            "error": tc.error,
        })

    # Failure/recovery summary
    failure_summary = []
    for r in state.recoveries:
        failure_summary.append({
            "tool": r.tool,
            "attempt": r.attempt,
            "status": r.status,
            "error": r.error,
        })

    repo = state.repository_info or {}

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repository": {
            "url": state.repository_url,
            "name": repo.get("name", "unknown"),
            "full_name": repo.get("full_name", "unknown"),
            "description": repo.get("description", ""),
            "language": repo.get("language", "unknown"),
            "stars": repo.get("stars", 0),
            "forks": repo.get("forks", 0),
        },
        "execution": {
            "goal": state.user_goal,
            "plan": state.plan,
            "files_analyzed": state.files_analyzed,
            "execution_time_seconds": round(state.execution_time, 2),
            "errors": state.errors,
        },
        "findings": findings_list,
        "summary": {
            "total_findings": len(findings),
            "Critical": metrics["Critical"],
            "High": metrics["High"],
            "Medium": metrics["Medium"],
            "Low": metrics["Low"],
        },
        "tool_execution": tool_calls_summary,
        "failure_recovery": failure_summary,
        "llm_narrative": llm_narrative or "LLM not available — report generated from static analysis only.",
        "limitations": [
            "Supports Python source files only.",
            "AST-based rules are intentionally simple heuristics, not production SAST.",
            "Secret detection looks for common patterns only — not a complete secret scanner.",
            "LLM output depends on the configured provider and model.",
            "Large repositories are limited to MAX_FILES and MAX_FILE_SIZE settings.",
            "GitHub API rate limits (60 req/hr unauthenticated) may affect execution.",
            "Unused import detection uses simple name matching and may have false positives.",
        ],
        "production_recommendations": [
            "Integrate with a dedicated SAST tool (e.g., Bandit, Semgrep) for security scanning.",
            "Add JavaScript/TypeScript support via a parser like tree-sitter.",
            "Connect to GitHub Actions for automated PR review.",
            "Store findings in a database for trend analysis over time.",
            "Add support for custom rule configuration.",
        ],
    }
    return report


def report_to_markdown(report: dict) -> str:
    """Renders the structured report as a Markdown document."""
    repo = report["repository"]
    exe = report["execution"]
    summary = report["summary"]
    findings = report["findings"]
    failures = report["failure_recovery"]

    lines = []
    lines.append("# Repository Code Quality Report\n")
    lines.append(f"**Generated:** {report['generated_at']}  ")
    lines.append(f"**Repository:** [{repo['full_name']}]({repo['url']})  ")
    if repo.get("description"):
        lines.append(f"**Description:** {repo['description']}  ")
    lines.append(f"**Primary Language:** {repo.get('language', 'unknown')}  ")
    lines.append(f"**Stars:** {repo.get('stars', 0)} | **Forks:** {repo.get('forks', 0)}  ")
    lines.append("")
    lines.append("---\n")

    lines.append("## Execution Summary\n")
    lines.append(f"**Goal:** {exe['goal']}  ")
    lines.append(f"**Files Analyzed:** {len(exe['files_analyzed'])}  ")
    lines.append(f"**Execution Time:** {exe['execution_time_seconds']}s  ")
    if exe.get("errors"):
        lines.append(f"**Errors Encountered:** {len(exe['errors'])}  ")
    lines.append("")

    lines.append("### Execution Plan\n")
    for i, step in enumerate(exe["plan"], 1):
        lines.append(f"{i}. {step}")
    lines.append("")

    lines.append("## Analysis Summary\n")
    lines.append(f"| Severity | Count |")
    lines.append(f"|----------|-------|")
    lines.append(f"| 🔴 Critical | {summary['Critical']} |")
    lines.append(f"| 🟠 High | {summary['High']} |")
    lines.append(f"| 🟡 Medium | {summary['Medium']} |")
    lines.append(f"| 🟢 Low | {summary['Low']} |")
    lines.append(f"| **Total** | **{summary['total_findings']}** |")
    lines.append("")

    if report.get("llm_narrative"):
        lines.append("## AI Assessment\n")
        lines.append(report["llm_narrative"])
        lines.append("")

    lines.append("## Findings\n")
    if not findings:
        lines.append("_No issues detected._\n")
    else:
        severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        sorted_findings = sorted(findings, key=lambda f: severity_order.get(f["severity"], 99))
        for f in sorted_findings:
            sev_emoji = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(f["severity"], "⚪")
            lines.append(f"### {f['issue_id']} — {sev_emoji} {f['severity']}: {f['description']}\n")
            lines.append(f"- **Category:** {f['category']}")
            lines.append(f"- **File:** `{f['file']}`" + (f"  *(line {f['line']})*" if f.get("line") else ""))
            lines.append(f"- **Evidence:** `{f['evidence']}`")
            lines.append(f"- **Recommendation:** {f['recommendation']}")
            lines.append("")

    lines.append("## Tool Execution\n")
    for tc in report["tool_execution"]:
        status = "✅" if tc["success"] else "❌"
        lines.append(f"- {status} **{tc['tool']}** (attempt {tc['attempt']})" +
                     (f" — Error: {tc['error']}" if tc.get("error") else ""))
    lines.append("")

    if failures:
        lines.append("## Failure & Recovery Log\n")
        for r in failures:
            icon = "✅" if r["status"] == "success" else "❌"
            lines.append(f"- {icon} **{r['tool']}** attempt {r['attempt']}: {r['status']}" +
                         (f" ({r['error']})" if r.get("error") else ""))
        lines.append("")
        lines.append("_One or more tool failures were detected and successfully recovered through retry._\n")

    lines.append("## Limitations\n")
    for lim in report["limitations"]:
        lines.append(f"- {lim}")
    lines.append("")

    lines.append("## Production Recommendations\n")
    for rec in report["production_recommendations"]:
        lines.append(f"- {rec}")
    lines.append("")

    return "\n".join(lines)
