"""
Synthetic bad code for evaluation testing.
This file intentionally contains multiple known code quality issues.

Known issues (ground truth):
- long_function: process_data is > 50 lines
- hardcoded_secret: api_key and password are hardcoded
- broad_exception: bare except and except Exception
- todo: TODO and FIXME markers
- missing_docstring: several public functions lack docstrings
- unused_import: 'json' is imported but not used
- too_many_args: configure() has 7 arguments
- deep_nesting: deeply nested logic in validate_data()
"""

import os
import sys
import json  # unused import — intentional for evaluation

# Hardcoded secret — intentional for evaluation
api_key = "sk-abcdef1234567890secret"
password = "admin123"


def process_data(data, mode, verbose, retries):
    # TODO: refactor this entire function
    results = []
    errors = []
    skipped = []
    summary = {}
    index = 0

    for item in data:
        index += 1
        if item is None:
            skipped.append(index)
            continue

        if mode == "strict":
            if isinstance(item, dict):
                if "value" in item:
                    val = item["value"]
                    if val > 0:
                        results.append(val * 2)
                    else:
                        errors.append(f"Negative value at index {index}")
                else:
                    errors.append(f"Missing key at index {index}")
            else:
                errors.append(f"Not a dict at index {index}")
        elif mode == "lenient":
            try:
                results.append(float(item))
            except:  # bare except — intentional
                errors.append(str(item))
        else:
            results.append(item)

        if verbose:
            print(f"Processed item {index}")

    # Post-processing block — deliberately verbose to push function over 50-line limit
    clean_results = []
    for r in results:
        if r is not None:
            clean_results.append(r)

    deduped = []
    seen_vals = set()
    for r in clean_results:
        if r not in seen_vals:
            deduped.append(r)
            seen_vals.add(r)

    total_valid = len(deduped)
    total_errors = len(errors)
    total_skipped = len(skipped)
    error_rate = total_errors / max(index, 1)
    skip_rate = total_skipped / max(index, 1)

    summary["results"] = deduped
    summary["errors"] = errors
    summary["skipped"] = skipped
    summary["total"] = index
    summary["total_valid"] = total_valid
    summary["error_rate"] = error_rate
    summary["skip_rate"] = skip_rate
    summary["success_rate"] = len(deduped) / max(index, 1)

    return summary


def validate_data(records):
    # Deep nesting — intentional
    valid = []
    for r in records:
        if r:
            if isinstance(r, dict):
                if "type" in r:
                    if r["type"] == "A":
                        if "value" in r:
                            if r["value"] > 0:
                                valid.append(r)
    return valid


def configure(host, port, user, password, db, timeout, retries):
    # FIXME: this needs proper validation
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "db": db,
        "timeout": timeout,
        "retries": retries,
    }


def fetch_records(source):
    try:
        data = source.get_all()
        return data
    except Exception:
        return []


def save_results(results, path):
    try:
        with open(path, "w") as f:
            for r in results:
                f.write(str(r) + "\n")
    except Exception as e:
        print(f"Error: {e}")


def run_pipeline(source, output_path, mode="strict", verbose=False):
    data = fetch_records(source)
    processed = process_data(data, mode, verbose, retries=3)
    save_results(processed.get("results", []), output_path)
    return processed
