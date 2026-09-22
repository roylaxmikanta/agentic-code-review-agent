"""Tests for the code quality analyzer."""

import pytest
from src.code_analyzer import analyze_python_file, calculate_metrics, reset_counter
from src.models import Finding


@pytest.fixture(autouse=True)
def fresh_counter():
    reset_counter()


# ── Long function detection ───────────────────────────────────────────────────

def test_detects_long_function():
    code = "def long_function():\n" + "    x = 1\n" * 55
    findings = analyze_python_file("test.py", code)
    categories = [f.description.lower() for f in findings]
    assert any("long" in d and "function" in d for d in categories)


def test_short_function_not_flagged():
    code = "def short():\n    return 42\n"
    findings = analyze_python_file("test.py", code)
    assert not any("long" in f.description.lower() and "function" in f.description.lower() for f in findings)


# ── Hardcoded secrets ─────────────────────────────────────────────────────────

def test_detects_hardcoded_password():
    code = 'password = "supersecret123"\n'
    findings = analyze_python_file("test.py", code)
    assert any("password" in f.description.lower() or "secret" in f.description.lower() for f in findings)


def test_detects_api_key():
    code = 'api_key = "sk-abcdefghijklmnop"\n'
    findings = analyze_python_file("test.py", code)
    assert any("api_key" in f.description.lower() or "secret" in f.description.lower() for f in findings)


def test_secret_evidence_is_masked():
    code = 'password = "mypassword123"\n'
    findings = analyze_python_file("test.py", code)
    sec_findings = [f for f in findings if f.severity == "Critical"]
    for f in sec_findings:
        assert "mypassword123" not in f.evidence


# ── TODO detection ─────────────────────────────────────────────────────────────

def test_detects_todo_marker():
    code = "# TODO: fix this later\nx = 1\n"
    findings = analyze_python_file("test.py", code)
    assert any("todo" in f.description.lower() for f in findings)


def test_detects_fixme_marker():
    code = "# FIXME: broken logic\nx = 1\n"
    findings = analyze_python_file("test.py", code)
    assert any("todo" in f.description.lower() or "fixme" in f.description.lower() for f in findings)


# ── Broad exception handling ──────────────────────────────────────────────────

def test_detects_broad_exception():
    code = (
        "def foo():\n"
        "    try:\n"
        "        pass\n"
        "    except Exception:\n"
        "        pass\n"
    )
    findings = analyze_python_file("test.py", code)
    assert any("broad" in f.description.lower() for f in findings)


def test_detects_bare_except():
    code = (
        "def foo():\n"
        "    try:\n"
        "        pass\n"
        "    except:\n"
        "        pass\n"
    )
    findings = analyze_python_file("test.py", code)
    assert any("broad" in f.description.lower() for f in findings)


# ── Missing docstring ─────────────────────────────────────────────────────────

def test_detects_missing_docstring():
    code = "def public_func():\n    return 1\n"
    findings = analyze_python_file("test.py", code)
    assert any("docstring" in f.description.lower() for f in findings)


def test_private_function_no_docstring_not_flagged():
    code = "def _private():\n    return 1\n"
    findings = analyze_python_file("test.py", code)
    assert not any("docstring" in f.description.lower() for f in findings)


def test_function_with_docstring_not_flagged():
    code = 'def public_func():\n    """Does something."""\n    return 1\n'
    findings = analyze_python_file("test.py", code)
    assert not any("docstring" in f.description.lower() for f in findings)


# ── Too many arguments ────────────────────────────────────────────────────────

def test_detects_too_many_args():
    code = "def func(a, b, c, d, e, f, g):\n    pass\n"
    findings = analyze_python_file("test.py", code)
    assert any("argument" in f.description.lower() for f in findings)


# ── Unused imports ────────────────────────────────────────────────────────────

def test_detects_unused_import():
    code = "import os\n\ndef foo():\n    return 1\n"
    findings = analyze_python_file("test.py", code)
    assert any("unused" in f.description.lower() for f in findings)


def test_used_import_not_flagged():
    code = "import os\n\ndef foo():\n    return os.getcwd()\n"
    findings = analyze_python_file("test.py", code)
    assert not any("unused import" in f.description.lower() and "os" in f.evidence for f in findings)


# ── Syntax error ──────────────────────────────────────────────────────────────

def test_syntax_error_returns_finding():
    code = "def broken(\n    pass\n"
    findings = analyze_python_file("test.py", code)
    assert any("syntax" in f.description.lower() for f in findings)


# ── Metrics calculation ───────────────────────────────────────────────────────

def test_calculate_metrics_empty():
    metrics = calculate_metrics([])
    assert metrics == {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}


def test_calculate_metrics_counts():
    f1 = Finding("CQ-001", "Security", "Critical", "f.py", 1, "desc", "ev", "rec")
    f2 = Finding("CQ-002", "Style", "Low", "f.py", 2, "desc", "ev", "rec")
    f3 = Finding("CQ-003", "Design", "Medium", "f.py", 3, "desc", "ev", "rec")
    metrics = calculate_metrics([f1, f2, f3])
    assert metrics["Critical"] == 1
    assert metrics["Low"] == 1
    assert metrics["Medium"] == 1
    assert metrics["High"] == 0
