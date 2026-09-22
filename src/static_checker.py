"""
Optional Tool 3 — Python Static Checker.

Uses the standard library `py_compile` and `ast` to perform lightweight
static checks that complement the AST-based code analyzer.

This tool is optional — the project works without it.
It requires no external dependencies.
"""

import ast
import py_compile
import tempfile
import os
from src.models import ToolResult


def run_static_check(path: str, content: str) -> ToolResult:
    """
    Runs lightweight static checks on a Python file's content:
    1. py_compile syntax validation
    2. AST-level checks (unreachable code after return, empty except bodies)

    Args:
        path: The display path/name of the file.
        content: The full source code as a string.

    Returns:
        ToolResult with a list of static check findings.
    """
    findings = []

    # ── 1. py_compile syntax check ────────────────────────────────────────────
    # Write content to a temp file so py_compile can check it
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        py_compile.compile(tmp_path, doraise=True)
        findings.append({
            "check": "syntax",
            "status": "ok",
            "message": "File compiles cleanly.",
        })
    except py_compile.PyCompileError as e:
        findings.append({
            "check": "syntax",
            "status": "error",
            "message": f"Compilation error: {str(e)}",
        })
        return ToolResult(
            success=True,
            tool="static_checker",
            data={"file": path, "checks": findings},
            error=None,
        )
    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # ── 2. AST-level static checks ────────────────────────────────────────────
    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError:
        # Already caught above
        return ToolResult(
            success=True,
            tool="static_checker",
            data={"file": path, "checks": findings},
            error=None,
        )

    # Check: unreachable code after return/raise/break/continue
    unreachable_issues = _check_unreachable(tree)
    findings.extend(unreachable_issues)

    # Check: pass-only exception handlers (suppressed exceptions)
    suppressed = _check_suppressed_exceptions(tree)
    findings.extend(suppressed)

    # Check: functions with no body (just a docstring, no actual logic)
    stub_funcs = _check_stub_functions(tree)
    findings.extend(stub_funcs)

    return ToolResult(
        success=True,
        tool="static_checker",
        data={"file": path, "checks": findings, "total_issues": len([
            f for f in findings if f["status"] == "warning"
        ])},
        error=None,
    )


def _check_unreachable(tree: ast.AST) -> list[dict]:
    """Detects statements that appear after return/raise/break/continue."""
    findings = []
    terminals = (ast.Return, ast.Raise, ast.Break, ast.Continue)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.For, ast.While, ast.If)):
            continue

        body = getattr(node, "body", [])
        for i, stmt in enumerate(body):
            if isinstance(stmt, terminals) and i + 1 < len(body):
                next_stmt = body[i + 1]
                # Skip if the next statement is another terminal (e.g. else branch)
                if not isinstance(next_stmt, (ast.If, ast.Try)):
                    findings.append({
                        "check": "unreachable_code",
                        "status": "warning",
                        "line": next_stmt.lineno,
                        "message": f"Unreachable code detected at line {next_stmt.lineno} "
                                   f"(after {type(stmt).__name__}).",
                    })
    return findings


def _check_suppressed_exceptions(tree: ast.AST) -> list[dict]:
    """Detects except blocks that only contain `pass` (silently swallowing errors)."""
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            findings.append({
                "check": "suppressed_exception",
                "status": "warning",
                "line": node.lineno,
                "message": f"Exception silently suppressed with 'pass' at line {node.lineno}. "
                           "Consider at least logging the error.",
            })
    return findings


def _check_stub_functions(tree: ast.AST) -> list[dict]:
    """Detects public functions that only have a docstring and nothing else (stubs)."""
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue

        body = node.body
        # A stub has only a docstring (Expr with a Constant string) and nothing else
        is_stub = (
            len(body) == 1
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        )
        # Or a bare pass
        is_pass_only = len(body) == 1 and isinstance(body[0], ast.Pass)

        if is_stub or is_pass_only:
            findings.append({
                "check": "stub_function",
                "status": "warning",
                "line": node.lineno,
                "message": f"Function '{node.name}' at line {node.lineno} appears to be "
                           "a stub (no implementation). Either implement it or mark it with NotImplementedError.",
            })
    return findings


def check_repository_files(files: list[dict]) -> ToolResult:
    """
    Runs static checks on a list of file dicts: [{"path": ..., "content": ...}].
    Aggregates all results.
    """
    all_results = []
    total_issues = 0

    for f in files:
        result = run_static_check(f["path"], f["content"])
        if result.success and result.data:
            all_results.append(result.data)
            total_issues += result.data.get("total_issues", 0)

    return ToolResult(
        success=True,
        tool="static_checker",
        data={
            "files_checked": len(files),
            "total_static_issues": total_issues,
            "results": all_results,
        },
        error=None,
    )
