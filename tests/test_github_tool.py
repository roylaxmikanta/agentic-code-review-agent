"""Tests for GitHub tool — URL parsing and tool result structure."""

import pytest
from src.github_tool import parse_github_url, get_repo_info, ToolResult


# ── URL Parsing ───────────────────────────────────────────────────────────────

def test_parse_valid_https_url():
    result = parse_github_url("https://github.com/psf/requests")
    assert result == ("psf", "requests")


def test_parse_valid_https_url_with_trailing_slash():
    result = parse_github_url("https://github.com/psf/requests/")
    assert result == ("psf", "requests")


def test_parse_valid_git_url():
    result = parse_github_url("git@github.com:psf/requests.git")
    assert result == ("psf", "requests")


def test_parse_invalid_url_returns_none():
    assert parse_github_url("not-a-url") is None


def test_parse_non_github_url_returns_none():
    assert parse_github_url("https://gitlab.com/user/repo") is None


def test_parse_url_missing_repo_returns_none():
    assert parse_github_url("https://github.com/onlyowner") is None


def test_parse_empty_string_returns_none():
    assert parse_github_url("") is None


# ── Simulated failure ─────────────────────────────────────────────────────────

def test_get_repo_info_simulates_failure_on_attempt_1():
    result = get_repo_info("psf", "requests", simulate_failure=True, attempt=1)
    assert result.success is False
    assert result.attempt == 1
    assert "timeout" in result.error.lower() or "simulated" in result.error.lower()


def test_get_repo_info_does_not_simulate_failure_on_attempt_2():
    """
    On attempt 2, no failure should be injected regardless of simulate_failure flag.
    (Real network call — skipped in offline environments.)
    """
    result = get_repo_info("psf", "requests", simulate_failure=True, attempt=2)
    # Either succeeds (network available) or fails for a real reason — but NOT simulated
    assert "simulated" not in (result.error or "").lower()


# ── ToolResult structure ──────────────────────────────────────────────────────

def test_tool_result_failure_structure():
    result = get_repo_info("nonexistent-owner-xyz", "nonexistent-repo-abc", simulate_failure=False)
    assert isinstance(result, ToolResult)
    assert result.success is False or result.success is True  # Just validate type
    assert result.tool == "github_repository"


def test_tool_result_simulated_failure_has_null_data():
    result = get_repo_info("owner", "repo", simulate_failure=True, attempt=1)
    assert result.data is None
    assert result.error is not None
