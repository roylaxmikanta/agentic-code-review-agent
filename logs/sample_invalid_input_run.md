# Sample Run 3 — Invalid Input

**Date:** 2026-09-22  
**Label:** INVALID_INPUT  
**Input:** `not-a-github-url`  
**Goal:** Analyze this repository.  
**Failure Simulation:** OFF  

---

## Plan

```
1. Validate GitHub repository URL.
2. Fetch repository metadata.
3. Inspect repository file tree.
4. Select supported Python source files.
5. Analyze source files for code quality issues.
6. Validate and prioritize findings.
7. Generate structured final report.
```

---

## Execution Trace

```
[1/7] Validating repository URL...
      ❌ ERROR — Invalid GitHub URL format.

      Agent stopped gracefully. No API calls made.
```

---

## Error Details

```
Input URL: "not-a-github-url"
Validation result: FAILED
Error message: "Invalid GitHub URL format."
Execution halted at step 1.
```

No network requests were made.  
No partial results were generated.  
The user received a clear error message.

---

## Tool Execution Summary

| Tool | Calls | Status |
|------|-------|--------|
| *(none — validation failed before any API call)* | 0 | — |

---

## Execution Metrics

```
Total Execution Time: < 0.01 seconds
Files Analyzed: 0
Findings: 0
Errors: ["Invalid GitHub URL format."]
Status: FAILED
```

---

## Additional Invalid Input Cases

| Input | Error |
|-------|-------|
| `https://gitlab.com/user/repo` | Invalid GitHub URL format |
| `https://github.com` | Invalid GitHub URL format (no owner/repo) |
| *(empty string)* | Please enter a GitHub repository URL |
| `https://github.com/nonexistent-xyz/nonexistent-abc` | Repository not found (HTTP 404) |

> **Note:** The agent never crashes on invalid input. All user-facing errors are shown as friendly messages, not raw stack traces.
