"""Planner — converts a user goal into a concrete execution plan."""

import os
import json
import requests
from typing import Optional


PLAN_STEPS = [
    "Validate GitHub repository URL.",
    "Fetch repository metadata.",
    "Inspect repository file tree.",
    "Select supported Python source files.",
    "Analyze source files for code quality issues.",
    "Validate and prioritize findings.",
    "Generate structured final report.",
]


def create_plan(user_goal: str, use_llm: bool = True) -> list[str]:
    """
    Returns the execution plan steps.
    If an LLM is available and use_llm=True, it may refine the plan.
    Falls back to the default plan if LLM is unavailable.
    """
    api_key = os.getenv("LLM_API_KEY", "")
    if use_llm and api_key:
        refined = _llm_refine_plan(user_goal, api_key)
        if refined:
            return refined

    return PLAN_STEPS[:]


def _llm_refine_plan(goal: str, api_key: str) -> Optional[list[str]]:
    """
    Asks the LLM to produce a concise action plan.
    Returns None on any failure so the caller falls back gracefully.
    """
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    url = f"{base_url}/chat/completions"

    system_prompt = (
        "You are an AI planning assistant. Given a user goal involving GitHub code review, "
        "output a numbered JSON array of concise action steps (max 8 steps). "
        "Each step should be a short, active-voice sentence describing an action the agent will take. "
        "Do NOT include private reasoning — only operational steps. "
        "Respond ONLY with valid JSON, e.g.: [\"Step 1\", \"Step 2\"]"
    )

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Goal: {goal}"},
                ],
                "max_tokens": 300,
                "temperature": 0.2,
            },
            timeout=15,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        steps = json.loads(content)
        if isinstance(steps, list) and all(isinstance(s, str) for s in steps):
            return steps
    except Exception:
        pass  # Fall back silently

    return None


def summarize_findings_with_llm(findings_summary: dict, repo_info: dict) -> Optional[str]:
    """
    Sends a summary of findings (NOT raw code) to the LLM to generate
    a human-readable analysis narrative.
    Returns None if LLM is unavailable.
    """
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        return None

    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    url = f"{base_url}/chat/completions"

    prompt = (
        f"Repository: {repo_info.get('full_name', 'unknown')}\n"
        f"Language: {repo_info.get('language', 'unknown')}\n"
        f"Files analyzed: {findings_summary.get('files_analyzed', 0)}\n"
        f"Total findings: {findings_summary.get('total_findings', 0)}\n"
        f"Critical: {findings_summary.get('Critical', 0)}\n"
        f"High: {findings_summary.get('High', 0)}\n"
        f"Medium: {findings_summary.get('Medium', 0)}\n"
        f"Low: {findings_summary.get('Low', 0)}\n"
        f"Top categories: {findings_summary.get('categories', [])}\n\n"
        "Write a concise 3-4 sentence code quality assessment based on these findings. "
        "Be specific and practical. Do not invent findings not listed above."
    )

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a senior software engineer reviewing code quality metrics."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 250,
                "temperature": 0.3,
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
