"""Tests for agent retry/recovery logic and report generation."""

import pytest
from unittest.mock import patch, MagicMock
from src.models import AgentState, ToolResult, RetryRecord
from src.agent import _fetch_with_retry
from src.reporter import build_report, report_to_markdown


# ── Retry behavior ────────────────────────────────────────────────────────────

def test_retry_succeeds_on_second_attempt():
    """When failure is simulated, the first attempt fails and the second succeeds."""
    state = AgentState(simulate_failure=True)

    with patch("src.agent.get_repo_info") as mock_get:
        # Attempt 1: simulated failure
        mock_get.side_effect = [
            ToolResult(success=False, tool="github_repository", data=None,
                       error="Simulated timeout", attempt=1),
            ToolResult(success=True, tool="github_repository",
                       data={"full_name": "owner/repo", "default_branch": "main",
                             "name": "repo", "description": "", "language": "Python",
                             "stars": 0, "forks": 0},
                       error=None, attempt=2),
        ]
        result = _fetch_with_retry("owner", "repo", simulate_failure=True, state=state)

    assert result.success is True
    assert result.attempt == 2
    assert len(state.recoveries) == 2
    assert state.recoveries[0].status == "failed"
    assert state.recoveries[1].status == "success"


def test_retry_records_failure_then_success():
    """Verify recovery records are appended correctly."""
    state = AgentState(simulate_failure=True)

    with patch("src.agent.get_repo_info") as mock_get:
        mock_get.side_effect = [
            ToolResult(success=False, tool="github_repository", data=None,
                       error="Simulated timeout", attempt=1),
            ToolResult(success=True, tool="github_repository",
                       data={"full_name": "o/r", "default_branch": "main",
                             "name": "r", "description": "", "language": "Python",
                             "stars": 0, "forks": 0},
                       error=None, attempt=2),
        ]
        _fetch_with_retry("o", "r", simulate_failure=True, state=state)

    assert any(r.status == "failed" for r in state.recoveries)
    assert any(r.status == "success" and r.attempt == 2 for r in state.recoveries)


def test_no_retry_when_no_failure():
    """Without failure simulation, only one attempt is made."""
    state = AgentState(simulate_failure=False)

    with patch("src.agent.get_repo_info") as mock_get:
        mock_get.return_value = ToolResult(
            success=True, tool="github_repository",
            data={"full_name": "o/r", "default_branch": "main",
                  "name": "r", "description": "", "language": "Python",
                  "stars": 0, "forks": 0},
            error=None, attempt=1,
        )
        result = _fetch_with_retry("o", "r", simulate_failure=False, state=state)

    assert result.success is True
    assert len(state.recoveries) == 1
    assert state.recoveries[0].attempt == 1


# ── Report generation ─────────────────────────────────────────────────────────

def test_build_report_contains_required_keys():
    state = AgentState(
        user_goal="Test",
        repository_url="https://github.com/test/repo",
        repository_info={"name": "repo", "full_name": "test/repo", "description": "",
                         "language": "Python", "stars": 0, "forks": 0},
        files_analyzed=["test.py"],
        plan=["Step 1", "Step 2"],
        execution_time=1.5,
    )
    report = build_report(state)
    assert "repository" in report
    assert "findings" in report
    assert "summary" in report
    assert "tool_execution" in report
    assert "limitations" in report
    assert "generated_at" in report


def test_report_to_markdown_produces_string():
    state = AgentState(
        user_goal="Test",
        repository_url="https://github.com/test/repo",
        repository_info={"name": "repo", "full_name": "test/repo", "description": "",
                         "language": "Python", "stars": 0, "forks": 0},
        files_analyzed=["test.py"],
        plan=["Step 1"],
        execution_time=1.0,
    )
    report = build_report(state)
    md = report_to_markdown(report)
    assert isinstance(md, str)
    assert "# Repository Code Quality Report" in md
    assert "test/repo" in md


def test_report_summary_counts_match_findings():
    from src.models import Finding
    f = Finding("CQ-001", "Security", "Critical", "a.py", 1, "desc", "ev", "rec")
    state = AgentState(
        user_goal="Test",
        repository_url="https://github.com/x/y",
        repository_info={"name": "y", "full_name": "x/y", "description": "",
                         "language": "Python", "stars": 0, "forks": 0},
        findings=[f],
        plan=[],
        execution_time=0.5,
    )
    report = build_report(state)
    assert report["summary"]["Critical"] == 1
    assert report["summary"]["total_findings"] == 1
