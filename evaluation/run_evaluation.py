"""
Evaluation runner — tests the code analyzer against known test repositories.
Usage: python evaluation/run_evaluation.py
"""

import sys
import json
from pathlib import Path

# Make sure src/ is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluator import evaluate

TEST_REPO_DIR = Path(__file__).parent.parent / "test_repositories" / "sample_bad_repo"
GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"
OUTPUT_FILE = Path(__file__).parent / "evaluation_results.json"


def main():
    print("=" * 50)
    print("  Agentic Code Review — Evaluation Framework")
    print("=" * 50)

    if not GROUND_TRUTH.exists():
        print(f"ERROR: Ground truth not found at {GROUND_TRUTH}")
        sys.exit(1)

    if not TEST_REPO_DIR.exists():
        print(f"ERROR: Test repository not found at {TEST_REPO_DIR}")
        sys.exit(1)

    summary = evaluate(str(TEST_REPO_DIR), str(GROUND_TRUTH))

    # Save results
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults saved to: {OUTPUT_FILE}")
    print("=" * 50)

    # Failure recovery check (not network-dependent for evaluation)
    print("\nFailure Recovery:")
    print("  N/A for static evaluation (see agent logs for runtime recovery data)")
    print("=" * 50)


if __name__ == "__main__":
    main()
