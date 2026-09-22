"""Evaluator — measures agent precision, recall, and F1 against ground truth."""

import json
from pathlib import Path
from src.code_analyzer import analyze_python_file, reset_counter
from src.models import Finding


def load_ground_truth(path: str) -> dict:
    """Loads ground truth JSON file mapping filenames to lists of expected issue categories."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_test_file(file_path: str) -> list[str]:
    """
    Runs the analyzer on a test file and returns the set of detected category labels.
    Maps internal categories to ground-truth keys.
    """
    reset_counter()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as e:
        print(f"  Could not read {file_path}: {e}")
        return []

    filename = Path(file_path).name
    findings = analyze_python_file(filename, content)

    # Map findings to normalized labels
    detected = set()
    for f in findings:
        label = _finding_to_label(f)
        if label:
            detected.add(label)

    return list(detected)


def _finding_to_label(f: Finding) -> str:
    """Maps a Finding to a ground-truth label key."""
    desc_lower = f.description.lower()
    if "long" in desc_lower and "function" in desc_lower:
        return "long_function"
    if "long" in desc_lower and "file" in desc_lower:
        return "long_file"
    if "unused import" in desc_lower:
        return "unused_import"
    if "docstring" in desc_lower:
        return "missing_docstring"
    if "argument" in desc_lower:
        return "too_many_args"
    if "nesting" in desc_lower or "deep" in desc_lower:
        return "deep_nesting"
    if "broad exception" in desc_lower or "bare" in desc_lower:
        return "broad_exception"
    if "todo" in desc_lower or "fixme" in desc_lower:
        return "todo"
    if "secret" in desc_lower or "hardcoded" in desc_lower:
        return "hardcoded_secret"
    if "syntax" in desc_lower:
        return "syntax_error"
    if "line" in desc_lower and "character" in desc_lower:
        return "long_line"
    return f.category.lower().replace(" ", "_")


def evaluate(test_repo_dir: str, ground_truth_path: str) -> dict:
    """
    Runs evaluation against all test files listed in ground truth.

    Args:
        test_repo_dir: Path to the directory containing test Python files.
        ground_truth_path: Path to ground_truth.json.

    Returns:
        dict with precision, recall, F1, and per-file details.
    """
    ground_truth = load_ground_truth(ground_truth_path)
    results = []

    total_tp = 0
    total_fp = 0
    total_fn = 0

    print("\nEvaluation Results")
    print("------------------")

    for filename, expected_labels in ground_truth.items():
        file_path = str(Path(test_repo_dir) / filename)
        detected_labels = analyze_test_file(file_path)

        expected_set = set(expected_labels)
        detected_set = set(detected_labels)

        tp = expected_set & detected_set
        fp = detected_set - expected_set
        fn = expected_set - detected_set

        total_tp += len(tp)
        total_fp += len(fp)
        total_fn += len(fn)

        results.append({
            "file": filename,
            "expected": sorted(expected_labels),
            "detected": sorted(detected_labels),
            "true_positives": sorted(tp),
            "false_positives": sorted(fp),
            "false_negatives": sorted(fn),
        })

        print(f"\n  File: {filename}")
        print(f"    Expected:  {sorted(expected_set)}")
        print(f"    Detected:  {sorted(detected_set)}")
        print(f"    TP={len(tp)}  FP={len(fp)}  FN={len(fn)}")

    # Precision, Recall, F1
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    summary = {
        "test_cases": len(results),
        "true_positives": total_tp,
        "false_positives": total_fp,
        "false_negatives": total_fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "per_file": results,
    }

    print(f"\n  Test Cases: {summary['test_cases']}")
    print(f"  True Positives: {total_tp}")
    print(f"  False Positives: {total_fp}")
    print(f"  False Negatives: {total_fn}")
    print(f"\n  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print(f"  F1 Score:  {f1:.4f}")

    return summary
