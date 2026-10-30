"""Enforce coverage above 95% for every Efteling integration module."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_ROOT = ROOT / "custom_components" / "efteling"
COVERAGE_REPORT = ROOT / "coverage.json"
MINIMUM_COVERAGE = 95.0


def main() -> int:
    """Check that every integration Python file is present and above threshold."""
    report: dict[str, Any] = json.loads(COVERAGE_REPORT.read_text(encoding="utf-8"))
    coverage_files: dict[str, dict[str, Any]] = {}

    for path, details in report["files"].items():
        report_path = Path(path)
        absolute_path = report_path if report_path.is_absolute() else ROOT / report_path
        try:
            relative_path = absolute_path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            continue
        coverage_files[relative_path] = details

    problems: list[str] = []
    for source_path in sorted(INTEGRATION_ROOT.rglob("*.py")):
        relative_path = source_path.relative_to(ROOT).as_posix()
        details = coverage_files.get(relative_path)
        if details is None:
            problems.append(f"{relative_path}: missing from coverage report")
            continue

        percent = details["summary"]["percent_covered"]
        if percent <= MINIMUM_COVERAGE:
            problems.append(f"{relative_path}: {percent:.2f}% (must exceed 95%)")

    if problems:
        sys.stderr.write("Per-module coverage requirements not met:\n")
        sys.stderr.write("\n".join(problems) + "\n")
        return 1

    module_count = len(list(INTEGRATION_ROOT.rglob("*.py")))
    sys.stdout.write(f"All {module_count} integration modules exceed 95% coverage.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
