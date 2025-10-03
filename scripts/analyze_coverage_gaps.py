#!/usr/bin/env python3
"""Analyze coverage gaps and identify functions with 0% coverage.

This script parses coverage.json and identifies:
1. Files with lowest coverage
2. Functions/methods with 0% coverage
3. Critical paths that need coverage
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_coverage_data(coverage_file: str) -> dict[Any, Any]:
    """Load coverage data from coverage.json."""
    with open(coverage_file) as f:
        data = json.load(f)
        return dict(data) if data else {}


def analyze_gaps(coverage_data: dict):
    """Analyze coverage gaps and generate report."""
    files = coverage_data.get("files", {})

    # Collect file statistics
    file_stats = []
    for file_path, data in files.items():
        if not file_path.startswith("trading_platform/"):
            continue

        summary = data.get("summary", {})
        covered = summary.get("covered_lines", 0)
        total = summary.get("num_statements", 0)

        if total > 0:
            pct = (covered / total) * 100
            file_stats.append(
                {
                    "file": file_path,
                    "covered": covered,
                    "total": total,
                    "percent": pct,
                    "missing": total - covered,
                }
            )

    # Sort by coverage percentage
    file_stats.sort(key=lambda x: x["percent"])

    return file_stats


def generate_report(file_stats: list[dict], output_path: Path):
    """Generate coverage gaps report."""
    print("=" * 70)
    print("Coverage Gaps Analysis")
    print("=" * 70)

    # Top 20 files with lowest coverage
    print("\n📉 Files with Lowest Coverage (Top 20):\n")
    for stat in file_stats[:20]:
        print(f"  {stat['percent']:5.1f}%  {stat['file']}")
        print(
            f"         ({stat['covered']}/{stat['total']} lines, "
            f"{stat['missing']} missing)"
        )

    # Files with 0% coverage
    zero_coverage = [s for s in file_stats if s["percent"] == 0.0]
    if zero_coverage:
        print(f"\n❌ Files with 0% Coverage ({len(zero_coverage)} files):\n")
        for stat in zero_coverage[:10]:
            print(f"  - {stat['file']}")
        if len(zero_coverage) > 10:
            print(f"  ... and {len(zero_coverage) - 10} more")

    # Save detailed report
    with open(output_path, "w") as f:
        f.write("# Coverage Gaps Report\n\n")
        f.write("## Files with Lowest Coverage\n\n")
        f.write("| File | Coverage | Lines Covered | Lines Total | Missing |\n")
        f.write("|------|----------|---------------|-------------|----------|\n")

        for stat in file_stats[:30]:
            f.write(
                f"| `{stat['file']}` | {stat['percent']:.1f}% | "
                f"{stat['covered']} | {stat['total']} | {stat['missing']} |\n"
            )

        f.write("\n## Files with 0% Coverage\n\n")
        for stat in zero_coverage:
            f.write(f"- `{stat['file']}` ({stat['total']} lines)\n")

        f.write("\n## Action Items\n\n")
        f.write("1. Prioritize files with 0% coverage\n")
        f.write("2. Add tests for critical paths\n")
        f.write("3. Aim for 80%+ coverage on core modules\n")

    print(f"\n✅ Detailed report saved to: {output_path}")


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    coverage_file = project_root / "coverage.json"

    if not coverage_file.exists():
        print("Error: coverage.json not found")
        print("Run: poetry run pytest --cov=trading_platform --cov-report=json")
        return 1

    coverage_data = load_coverage_data(str(coverage_file))
    file_stats = analyze_gaps(coverage_data)

    output_path = project_root / "COVERAGE_GAPS.md"
    generate_report(file_stats, output_path)

    return 0


if __name__ == "__main__":
    exit(main())
