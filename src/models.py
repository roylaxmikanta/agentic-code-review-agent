"""Data models for the agent state and tool outputs."""

from dataclasses import dataclass, field
from typing import Any, Optional
import time


@dataclass
class Finding:
    """A single code quality issue found during analysis."""
    issue_id: str
    category: str
    severity: str  # Critical, High, Medium, Low
    file: str
    line: Optional[int]
    description: str
    evidence: str
    recommendation: str


@dataclass
class ToolResult:
    """Standard output format for all tools."""
    success: bool
    tool: str
    data: Optional[Any]
    error: Optional[str]
    attempt: int = 1


@dataclass
class RetryRecord:
    """Log of a retry attempt."""
    tool: str
    attempt: int
    status: str  # "failed" or "success"
    error: Optional[str]


@dataclass
class AgentState:
    """Holds all state for a single agent run."""
    user_goal: str = ""
    repository_url: str = ""
    plan: list[str] = field(default_factory=list)
    current_step: int = 0
    repository_info: Optional[dict] = None
    files_analyzed: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    tool_calls: list[ToolResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recoveries: list[RetryRecord] = field(default_factory=list)
    final_report: Optional[dict] = None
    execution_time: float = 0.0
    start_time: float = field(default_factory=time.time)
    simulate_failure: bool = False
    failure_triggered: bool = False
