"""Monitor — tracks run metrics and persists them to a log file."""

import json
import os
import time
from pathlib import Path
from typing import Optional

LOGS_DIR = Path("logs")
MONITOR_LOG = LOGS_DIR / "run_monitor.json"


def ensure_logs_dir():
    LOGS_DIR.mkdir(exist_ok=True)


def record_run(
    run_id: str,
    repository_url: str,
    status: str,  # "success" | "failed" | "recovered"
    execution_time: float,
    tool_calls: int,
    successful_tool_calls: int,
    failed_tool_calls: int,
    retries: int,
    recovered_failures: int,
    files_analyzed: int,
    total_findings: int,
    llm_calls: int,
    errors: list[str],
):
    """Appends a run record to the monitor log."""
    ensure_logs_dir()

    record = {
        "run_id": run_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repository_url": repository_url,
        "status": status,
        "execution_time_seconds": round(execution_time, 2),
        "tool_calls": tool_calls,
        "successful_tool_calls": successful_tool_calls,
        "failed_tool_calls": failed_tool_calls,
        "retries": retries,
        "recovered_failures": recovered_failures,
        "files_analyzed": files_analyzed,
        "total_findings": total_findings,
        "llm_calls": llm_calls,
        "errors": errors,
    }

    # Load existing records
    records = []
    if MONITOR_LOG.exists():
        try:
            with open(MONITOR_LOG, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (json.JSONDecodeError, IOError):
            records = []

    records.append(record)

    with open(MONITOR_LOG, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    return record


def load_monitor_data() -> list[dict]:
    """Loads all recorded run metrics."""
    if not MONITOR_LOG.exists():
        return []
    try:
        with open(MONITOR_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def compute_summary(records: list[dict]) -> dict:
    """Computes aggregate statistics from all run records."""
    if not records:
        return {}

    total = len(records)
    successful = sum(1 for r in records if r["status"] == "success")
    failed = sum(1 for r in records if r["status"] == "failed")
    recovered = sum(1 for r in records if r["status"] == "recovered")
    total_tool_calls = sum(r.get("tool_calls", 0) for r in records)
    total_retries = sum(r.get("retries", 0) for r in records)
    total_recovered = sum(r.get("recovered_failures", 0) for r in records)
    avg_time = sum(r.get("execution_time_seconds", 0) for r in records) / total
    total_findings = sum(r.get("total_findings", 0) for r in records)

    return {
        "total_runs": total,
        "successful_runs": successful,
        "failed_runs": failed,
        "recovered_runs": recovered,
        "total_tool_calls": total_tool_calls,
        "total_retries": total_retries,
        "total_recovered_failures": total_recovered,
        "average_execution_time_seconds": round(avg_time, 2),
        "total_findings_detected": total_findings,
    }
