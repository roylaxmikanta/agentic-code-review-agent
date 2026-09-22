"""Tests for the optional static checker (Tool 3)."""

import pytest
from src.static_checker import run_static_check, check_repository_files


# ── Syntax check ──────────────────────────────────────────────────────────────

def test_clean_file_compiles_ok():
    code = 'def hello():\n    """Say hello."""\n    return "hello"\n'
    result = run_static_check("clean.py", code)
    assert result.success is True
    checks = result.data["checks"]
    syntax_checks = [c for c in checks if c["check"] == "syntax"]
    assert len(syntax_checks) == 1
    assert syntax_checks[0]["status"] == "ok"


def test_syntax_error_caught_by_static_checker():
    code = "def broken(\n    pass\n"
    result = run_static_check("broken.py", code)
    assert result.success is True
    checks = result.data["checks"]
    syntax_checks = [c for c in checks if c["check"] == "syntax"]
    assert any(c["status"] == "error" for c in syntax_checks)


# ── Suppressed exception check ────────────────────────────────────────────────

def test_detects_suppressed_exception():
    code = (
        "def foo():\n"
        "    try:\n"
        "        pass\n"
        "    except Exception:\n"
        "        pass\n"
    )
    result = run_static_check("test.py", code)
    assert result.success is True
    checks = result.data["checks"]
    assert any(c["check"] == "suppressed_exception" for c in checks)


def test_no_false_positive_for_logging_exception():
    code = (
        "def foo():\n"
        "    try:\n"
        "        pass\n"
        "    except Exception as e:\n"
        "        print(e)\n"
    )
    result = run_static_check("test.py", code)
    checks = result.data["checks"]
    assert not any(c["check"] == "suppressed_exception" for c in checks)


# ── Stub function check ───────────────────────────────────────────────────────

def test_detects_stub_function():
    code = 'def my_func():\n    """This is a stub."""\n'
    result = run_static_check("test.py", code)
    checks = result.data["checks"]
    assert any(c["check"] == "stub_function" for c in checks)


def test_implemented_function_not_flagged_as_stub():
    code = 'def my_func():\n    """Docstring."""\n    return 42\n'
    result = run_static_check("test.py", code)
    checks = result.data["checks"]
    assert not any(c["check"] == "stub_function" for c in checks)


# ── Repository-level check ────────────────────────────────────────────────────

def test_check_repository_files_returns_aggregated_result():
    files = [
        {"path": "a.py", "content": 'def f():\n    return 1\n'},
        {"path": "b.py", "content": 'x = 1\n'},
    ]
    result = check_repository_files(files)
    assert result.success is True
    assert result.data["files_checked"] == 2
    assert "total_static_issues" in result.data
