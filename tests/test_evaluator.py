"""Tests for the evaluator — precision, recall, F1 calculation."""

import pytest
from src.evaluator import _finding_to_label
from src.models import Finding


def make_finding(description: str, category: str = "Test", severity: str = "Low") -> Finding:
    return Finding("CQ-001", category, severity, "test.py", 1, description, "ev", "rec")


def safe_f1(p, r):
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


# ── Label mapping ─────────────────────────────────────────────────────────────

def test_label_long_function():
    f = make_finding("Function 'foo' is too long (60 lines, limit 50).")
    assert _finding_to_label(f) == "long_function"


def test_label_unused_import():
    f = make_finding("Possibly unused import: 'os'.")
    assert _finding_to_label(f) == "unused_import"


def test_label_docstring():
    f = make_finding("Public function 'bar' is missing a docstring.")
    assert _finding_to_label(f) == "missing_docstring"


def test_label_broad_exception():
    f = make_finding("Broad exception handler in 'foo' — catches all exceptions.")
    assert _finding_to_label(f) == "broad_exception"


def test_label_todo():
    f = make_finding("TODO/FIXME marker found — unfinished work.")
    assert _finding_to_label(f) == "todo"


def test_label_hardcoded_secret():
    f = make_finding("Possible hardcoded api_key detected.", category="Security", severity="Critical")
    assert _finding_to_label(f) == "hardcoded_secret"


# ── Precision/Recall/F1 math ──────────────────────────────────────────────────

def test_perfect_precision_recall():
    tp, fp, fn = 5, 0, 0
    p = tp / (tp + fp)
    r = tp / (tp + fn)
    f1 = safe_f1(p, r)
    assert p == 1.0
    assert r == 1.0
    assert f1 == 1.0


def test_zero_precision_when_all_fp():
    tp, fp, fn = 0, 5, 3
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = safe_f1(p, r)
    assert p == 0.0
    assert f1 == 0.0


def test_zero_recall_when_all_fn():
    tp, fp, fn = 0, 0, 5
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = safe_f1(p, r)
    assert r == 0.0
    assert f1 == 0.0


def test_no_division_by_zero_when_empty():
    tp, fp, fn = 0, 0, 0
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = safe_f1(p, r)
    assert f1 == 0.0


def test_partial_overlap():
    # 3 expected, detected 2 correctly + 1 wrong
    tp, fp, fn = 2, 1, 1
    p = tp / (tp + fp)
    r = tp / (tp + fn)
    f1 = safe_f1(p, r)
    assert abs(p - 2/3) < 1e-9
    assert abs(r - 2/3) < 1e-9
    assert abs(f1 - 2/3) < 1e-9
