"""GitHub Repository Tool — validates URLs, fetches repo info, tree, and file content."""

import re
import time
import requests
import os
from typing import Optional
from src.models import ToolResult


GITHUB_API = "https://api.github.com"
DEFAULT_TIMEOUT = 10  # seconds


def _headers() -> dict:
    token = os.getenv("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def parse_github_url(url: str) -> Optional[tuple[str, str]]:
    """
    Extracts (owner, repo) from a GitHub URL.
    Returns None if the URL is not a valid GitHub repo URL.
    """
    url = url.strip().rstrip("/")
    # Match https://github.com/owner/repo or git@github.com:owner/repo
    patterns = [
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
        r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        m = re.match(pattern, url)
        if m:
            return m.group(1), m.group(2)
    return None


def get_repo_info(owner: str, repo: str, simulate_failure: bool = False, attempt: int = 1) -> ToolResult:
    """
    Fetches basic repository metadata from the GitHub API.
    If simulate_failure is True and attempt == 1, raises a fake timeout.
    """
    if simulate_failure and attempt == 1:
        return ToolResult(
            success=False,
            tool="github_repository",
            data=None,
            error="Simulated GitHub API timeout",
            attempt=attempt,
        )

    try:
        url = f"{GITHUB_API}/repos/{owner}/{repo}"
        resp = requests.get(url, headers=_headers(), timeout=DEFAULT_TIMEOUT)

        if resp.status_code == 404:
            return ToolResult(
                success=False,
                tool="github_repository",
                data=None,
                error=f"Repository '{owner}/{repo}' not found (HTTP 404).",
                attempt=attempt,
            )
        if resp.status_code == 403:
            return ToolResult(
                success=False,
                tool="github_repository",
                data=None,
                error="GitHub API rate limit exceeded or access denied (HTTP 403).",
                attempt=attempt,
            )
        resp.raise_for_status()
        data = resp.json()
        return ToolResult(
            success=True,
            tool="github_repository",
            data={
                "name": data.get("name"),
                "full_name": data.get("full_name"),
                "description": data.get("description"),
                "language": data.get("language"),
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "size_kb": data.get("size", 0),
                "default_branch": data.get("default_branch", "main"),
                "topics": data.get("topics", []),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
            },
            error=None,
            attempt=attempt,
        )
    except requests.Timeout:
        return ToolResult(
            success=False,
            tool="github_repository",
            data=None,
            error="Request timed out while contacting GitHub API.",
            attempt=attempt,
        )
    except requests.RequestException as e:
        return ToolResult(
            success=False,
            tool="github_repository",
            data=None,
            error=f"Network error: {str(e)}",
            attempt=attempt,
        )


def get_repo_tree(owner: str, repo: str, branch: str = "main") -> ToolResult:
    """
    Fetches the full file tree of a repository using the Git Trees API.
    Returns a flat list of all file paths.
    """
    try:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        resp = requests.get(url, headers=_headers(), timeout=DEFAULT_TIMEOUT)

        if resp.status_code == 404:
            # Try 'master' as fallback
            url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/master?recursive=1"
            resp = requests.get(url, headers=_headers(), timeout=DEFAULT_TIMEOUT)

        if resp.status_code == 404:
            return ToolResult(
                success=False,
                tool="github_tree",
                data=None,
                error="Could not retrieve repository file tree (branch not found).",
            )

        resp.raise_for_status()
        tree = resp.json().get("tree", [])
        files = [
            {"path": item["path"], "size": item.get("size", 0), "type": item["type"]}
            for item in tree
            if item["type"] == "blob"
        ]
        return ToolResult(success=True, tool="github_tree", data={"files": files}, error=None)

    except requests.Timeout:
        return ToolResult(
            success=False,
            tool="github_tree",
            data=None,
            error="Timed out fetching repository tree.",
        )
    except requests.RequestException as e:
        return ToolResult(
            success=False,
            tool="github_tree",
            data=None,
            error=f"Network error: {str(e)}",
        )


def get_file_content(owner: str, repo: str, path: str) -> ToolResult:
    """
    Fetches the raw content of a single file from GitHub.
    """
    try:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
        resp = requests.get(url, headers=_headers(), timeout=DEFAULT_TIMEOUT)

        if resp.status_code == 404:
            return ToolResult(
                success=False,
                tool="github_file",
                data=None,
                error=f"File not found: {path}",
            )
        resp.raise_for_status()
        return ToolResult(
            success=True,
            tool="github_file",
            data={"path": path, "content": resp.text},
            error=None,
        )
    except requests.Timeout:
        return ToolResult(
            success=False,
            tool="github_file",
            data=None,
            error=f"Timed out fetching file: {path}",
        )
    except requests.RequestException as e:
        return ToolResult(
            success=False,
            tool="github_file",
            data=None,
            error=f"Network error fetching {path}: {str(e)}",
        )
