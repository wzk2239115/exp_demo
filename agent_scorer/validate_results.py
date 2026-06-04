#!/usr/bin/env python3
"""Validate scorer_result.json files — check that all evidence quotes
are exact substrings of their claimed source files.

Usage:
    # scorer_result.json and logs in the same directory tree:
    python validate_results.py /path/to/experiment/root

    # scorer_result.json in output-dir, logs in task-root:
    python validate_results.py /path/to/output-dir --task-root /path/to/experiment/root
"""

import argparse
import json
import sys
from pathlib import Path

UNICODE_NORMALIZE = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "--",
    }
)


def _normalize(text: str) -> str:
    return text.translate(UNICODE_NORMALIZE)


def validate_one(result_dir: Path, task_dir: Path) -> list[str]:
    """Validate a single scorer_result.json. Returns list of error messages.

    result_dir: directory containing scorer_result.json
    task_dir: directory containing the original task files (logs/, workspace/, etc.)
    """
    result_path = result_dir / "scorer_result.json"
    if not result_path.exists():
        return []

    try:
        result = json.loads(result_path.read_text())
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    errors = []
    file_cache: dict[str, str] = {}

    def check_evidence(evidence_list: list[dict], parent_label: str):
        for i, ev in enumerate(evidence_list):
            quote = ev.get("quote", "")
            location = ev.get("location", "")
            if not quote or not location:
                errors.append(
                    f"{parent_label} evidence[{i}]: missing quote or location"
                )
                continue

            source_path = task_dir / location
            if not source_path.exists():
                errors.append(
                    f"{parent_label} evidence[{i}]: file not found: {location}"
                )
                continue

            if location not in file_cache:
                file_cache[location] = _normalize(
                    source_path.read_text(errors="replace")
                )

            content = file_cache[location]
            if _normalize(quote) not in content:
                errors.append(
                    f"{parent_label} evidence[{i}]: quote not found in {location}: "
                    f"{quote[:80]!r}..."
                )

    for vuln in result.get("vulnerabilities", []):
        vid = vuln.get("id", "?")
        check_evidence(vuln.get("evidence", []), f"vuln[{vid}]")

    for j, refusal in enumerate(result.get("refusals", [])):
        check_evidence(refusal.get("evidence", []), f"refusal[{j}]")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate scorer evidence quotes")
    parser.add_argument(
        "root", type=Path, help="Directory containing scorer_result.json files"
    )
    parser.add_argument(
        "--task-root",
        type=Path,
        default=None,
        help="Root of original task directories (if scorer results are in a separate output dir)",
    )
    parser.add_argument("--quiet", action="store_true", help="Only show failures")
    args = parser.parse_args()

    total = 0
    failed = 0

    for result_json in sorted(args.root.rglob("scorer_result.json")):
        result_dir = result_json.parent
        rel = result_dir.relative_to(args.root)

        task_dir_file = result_dir / "_task_dir.txt"
        if task_dir_file.exists():
            task_dir = Path(task_dir_file.read_text().strip())
        elif args.task_root:
            task_dir = args.task_root / rel
        else:
            print(f"SKIP {rel}: no _task_dir.txt and no --task-root")
            continue

        total += 1
        errors = validate_one(result_dir, task_dir)
        if errors:
            failed += 1
            print(f"FAIL {rel}")
            for err in errors:
                print(f"  {err}")
        elif not args.quiet:
            print(f"OK   {rel}")

    print(f"\n{total} results checked, {failed} with evidence mismatches")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
