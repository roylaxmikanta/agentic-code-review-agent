"""Code Quality Analysis Tool — analyzes Python source files using AST."""

import ast
import re
import tokenize
import io
from typing import Optional
from src.models import Finding, ToolResult

# Configurable limits
MAX_FUNCTION_LINES = 50
MAX_FILE_LINES = 300
MAX_ARGS = 6
MAX_NESTING_DEPTH = 4
MAX_LINE_LENGTH = 120
ISSUE_COUNTER = 0


def _next_id() -> str:
    global ISSUE_COUNTER
    ISSUE_COUNTER += 1
    return f"CQ-{ISSUE_COUNTER:03d}"


def reset_counter():
    global ISSUE_COUNTER
    ISSUE_COUNTER = 0


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_function_lines(node: ast.FunctionDef) -> int:
    """Count lines in a function body."""
    if node.body:
        return node.end_lineno - node.lineno + 1
    return 0


def _nesting_depth(node: ast.AST, current: int = 0) -> int:
    """Recursively compute maximum nesting depth of control-flow constructs."""
    nesting_nodes = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)
    max_depth = current
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, nesting_nodes):
            depth = _nesting_depth(child, current + 1)
            max_depth = max(max_depth, depth)
    return max_depth


SECRET_PATTERNS = [
    (r'(?i)(password|passwd|pwd)\s*=\s*["\']([^"\']{3,})["\']', "password"),
    (r'(?i)(api_key|apikey|api_secret)\s*=\s*["\']([^"\']{3,})["\']', "api_key"),
    (r'(?i)(secret|token|auth_token)\s*=\s*["\']([^"\']{3,})["\']', "secret/token"),
    (r'(?i)(access_key|private_key)\s*=\s*["\']([^"\']{3,})["\']', "access_key"),
]


def _mask(value: str) -> str:
    """Mask a secret value for safe display."""
    if len(value) <= 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


# ── Per-file analysis ─────────────────────────────────────────────────────────

def analyze_python_file(path: str, content: str) -> list[Finding]:
    """
    Parse a Python file and return a list of code quality findings.
    Returns an empty list if the file cannot be parsed.
    """
    findings: list[Finding] = []
    lines = content.splitlines()

    # ── Try parsing AST ───────────────────────────────────────────────────────
    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError as e:
        findings.append(Finding(
            issue_id=_next_id(),
            category="Syntax",
            severity="Critical",
            file=path,
            line=e.lineno,
            description="Python syntax error — file could not be parsed.",
            evidence=str(e),
            recommendation="Fix the syntax error before running further analysis.",
        ))
        return findings

    # ── File length ───────────────────────────────────────────────────────────
    if len(lines) > MAX_FILE_LINES:
        findings.append(Finding(
            issue_id=_next_id(),
            category="Maintainability",
            severity="Medium",
            file=path,
            line=None,
            description=f"File is very long ({len(lines)} lines, limit {MAX_FILE_LINES}).",
            evidence=f"{len(lines)} lines",
            recommendation="Consider splitting this file into smaller modules.",
        ))

    # ── Imports ───────────────────────────────────────────────────────────────
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name.split(".")[0]
                imported_names.add(name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported_names.add(name)

    # Simple unused import check: name never appears elsewhere in source
    used_names = set(re.findall(r"\b([a-zA-Z_]\w*)\b", content))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            lineno = node.lineno
            for alias in node.names:
                imported = alias.asname if alias.asname else alias.name.split(".")[0]
                # Count occurrences of the name excluding the import line itself
                rest = "\n".join(l for i, l in enumerate(lines, 1) if i != lineno)
                occurrences = len(re.findall(rf"\b{re.escape(imported)}\b", rest))
                if occurrences == 0 and imported != "*":
                    findings.append(Finding(
                        issue_id=_next_id(),
                        category="Maintainability",
                        severity="Low",
                        file=path,
                        line=lineno,
                        description=f"Possibly unused import: '{imported}'.",
                        evidence=f"Line {lineno}: {lines[lineno-1].strip()}",
                        recommendation=f"Remove unused import '{imported}' if not needed.",
                    ))

    # ── Function-level checks ─────────────────────────────────────────────────
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        func_name = node.name
        func_line = node.lineno
        func_lines = _get_function_lines(node)

        # Long function
        if func_lines > MAX_FUNCTION_LINES:
            findings.append(Finding(
                issue_id=_next_id(),
                category="Maintainability",
                severity="Medium",
                file=path,
                line=func_line,
                description=f"Function '{func_name}' is too long ({func_lines} lines, limit {MAX_FUNCTION_LINES}).",
                evidence=f"def {func_name}(...) at line {func_line}, ends at line {node.end_lineno}",
                recommendation="Break this function into smaller, focused functions.",
            ))

        # Too many arguments
        args = node.args
        total_args = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
        if args.vararg:
            total_args += 1
        if args.kwarg:
            total_args += 1
        if total_args > MAX_ARGS:
            findings.append(Finding(
                issue_id=_next_id(),
                category="Design",
                severity="Medium",
                file=path,
                line=func_line,
                description=f"Function '{func_name}' has too many arguments ({total_args}, limit {MAX_ARGS}).",
                evidence=f"def {func_name}({', '.join(a.arg for a in args.args)}...)",
                recommendation="Group related arguments into a dataclass or configuration object.",
            ))

        # Missing docstring for public functions
        if not func_name.startswith("_"):
            has_docstring = (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )
            if not has_docstring:
                findings.append(Finding(
                    issue_id=_next_id(),
                    category="Documentation",
                    severity="Low",
                    file=path,
                    line=func_line,
                    description=f"Public function '{func_name}' is missing a docstring.",
                    evidence=f"def {func_name}(...) at line {func_line}",
                    recommendation=f"Add a docstring to '{func_name}' explaining its purpose and parameters.",
                ))

        # Deep nesting
        depth = _nesting_depth(node)
        if depth > MAX_NESTING_DEPTH:
            findings.append(Finding(
                issue_id=_next_id(),
                category="Complexity",
                severity="High",
                file=path,
                line=func_line,
                description=f"Function '{func_name}' has deep nesting (depth {depth}, limit {MAX_NESTING_DEPTH}).",
                evidence=f"Nesting depth {depth} in '{func_name}'",
                recommendation="Use early returns, extract helper functions, or simplify conditional logic.",
            ))

        # Broad exception handling
        for child in ast.walk(node):
            if isinstance(child, ast.ExceptHandler):
                if child.type is None or (
                    isinstance(child.type, ast.Name) and child.type.id == "Exception"
                ):
                    findings.append(Finding(
                        issue_id=_next_id(),
                        category="Robustness",
                        severity="Medium",
                        file=path,
                        line=child.lineno,
                        description=f"Broad exception handler in '{func_name}' — catches all exceptions.",
                        evidence=f"except {'Exception' if child.type else 'bare'}: at line {child.lineno}",
                        recommendation="Catch specific exceptions rather than using a broad except clause.",
                    ))

    # ── TODO / FIXME markers ───────────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line, re.IGNORECASE):
            findings.append(Finding(
                issue_id=_next_id(),
                category="Maintenance",
                severity="Low",
                file=path,
                line=i,
                description="TODO/FIXME marker found — unfinished work.",
                evidence=line.strip(),
                recommendation="Resolve or track this item in an issue tracker.",
            ))

    # ── Long lines ────────────────────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        if len(line) > MAX_LINE_LENGTH:
            findings.append(Finding(
                issue_id=_next_id(),
                category="Style",
                severity="Low",
                file=path,
                line=i,
                description=f"Line {i} exceeds {MAX_LINE_LENGTH} characters ({len(line)} chars).",
                evidence=line.strip()[:80] + "...",
                recommendation="Break long lines to improve readability.",
            ))

    # ── Hardcoded secrets ─────────────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        for pattern, label in SECRET_PATTERNS:
            m = re.search(pattern, line)
            if m:
                raw_val = m.group(2) if len(m.groups()) >= 2 else "****"
                findings.append(Finding(
                    issue_id=_next_id(),
                    category="Security",
                    severity="Critical",
                    file=path,
                    line=i,
                    description=f"Possible hardcoded {label} detected.",
                    evidence=f"Line {i}: {line.strip().replace(raw_val, _mask(raw_val))}",
                    recommendation=f"Move '{label}' to environment variables or a secrets manager. "
                                   "NEVER commit credentials to source control.",
                ))
                break  # one finding per line

    return findings


# ── Repository-level analysis ─────────────────────────────────────────────────

def analyze_repository(files: list[dict]) -> ToolResult:
    """
    Runs analysis on a list of file dicts: [{"path": ..., "content": ...}].
    Returns a ToolResult with all findings and per-file metrics.
    """
    reset_counter()
    all_findings: list[Finding] = []
    metrics: dict[str, dict] = {}

    for f in files:
        path = f["path"]
        content = f["content"]
        file_findings = analyze_python_file(path, content)
        all_findings.extend(file_findings)
        lines = content.splitlines()
        metrics[path] = {
            "lines": len(lines),
            "findings": len(file_findings),
        }

    return ToolResult(
        success=True,
        tool="code_quality_analyzer",
        data={
            "findings": all_findings,
            "metrics": metrics,
            "total_findings": len(all_findings),
        },
        error=None,
    )


def calculate_metrics(findings: list[Finding]) -> dict:
    """Counts findings by severity."""
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1
    return counts
