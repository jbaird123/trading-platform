#!/usr/bin/env python3
"""Generate comprehensive coverage report.

This script generates:
1. HTML coverage report (code coverage)
2. Requirements coverage report
3. Combined dashboard
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path


def run_pytest_coverage(project_root: Path) -> dict:
    """Run pytest with coverage and return statistics."""
    print("Running pytest with coverage...")

    result = subprocess.run(
        ["poetry", "run", "pytest", "--cov=trading_platform",
         "--cov-report=html", "--cov-report=json", "--cov-report=term",
         "-q"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300
    )

    # Parse coverage.json
    coverage_file = project_root / "coverage.json"
    if coverage_file.exists():
        with open(coverage_file) as f:
            cov_data = json.load(f)

        total_lines = cov_data['totals']['num_statements']
        covered_lines = cov_data['totals']['covered_lines']
        coverage_pct = cov_data['totals']['percent_covered']

        return {
            "total_lines": total_lines,
            "covered_lines": covered_lines,
            "coverage_pct": coverage_pct,
            "html_report": "htmlcov/index.html"
        }

    return {}


def generate_badge(coverage_pct: float) -> str:
    """Generate coverage badge markdown."""
    if coverage_pct >= 90:
        color = "brightgreen"
    elif coverage_pct >= 70:
        color = "yellow"
    else:
        color = "red"

    return f"![Coverage](https://img.shields.io/badge/coverage-{coverage_pct:.0f}%25-{color})"


def generate_report(project_root: Path):
    """Generate complete coverage report."""
    print("=" * 60)
    print("Coverage Report Generator")
    print("=" * 60)

    # Run code coverage
    print("\n1. Running code coverage analysis...")
    code_cov = run_pytest_coverage(project_root)

    # Generate requirement coverage
    print("\n2. Generating requirement coverage...")
    req_result = subprocess.run(
        ["python3", "scripts/validate_requirements_coverage.py"],
        cwd=project_root,
        capture_output=True,
        text=True
    )

    # Create combined report
    report_path = project_root / "COVERAGE_REPORT.md"

    with open(report_path, 'w') as f:
        f.write("# Coverage Report\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Code coverage section
        f.write("## Code Coverage\n\n")
        if code_cov:
            badge = generate_badge(code_cov['coverage_pct'])
            f.write(f"{badge}\n\n")
            f.write(f"- **Lines**: {code_cov['covered_lines']:,} / {code_cov['total_lines']:,}\n")
            f.write(f"- **Coverage**: {code_cov['coverage_pct']:.1f}%\n")
            f.write(f"- **HTML Report**: [{code_cov['html_report']}]({code_cov['html_report']})\n\n")
        else:
            f.write("❌ Code coverage data not available\n\n")

        # Requirements coverage section
        f.write("## Requirements Coverage\n\n")
        f.write("```\n")
        f.write(req_result.stdout)
        f.write("```\n\n")

        # Links
        f.write("## Related Reports\n\n")
        f.write("- [Testing Guide](docs/testing_guide.md)\n")
        f.write("- [Requirement to Test Map](docs/requirement_to_test_map.md)\n")
        f.write("- [Coverage Dashboard](docs/coverage_dashboard.md)\n")
        f.write("- [HTML Coverage Report](htmlcov/index.html)\n")

    print(f"\n✅ Coverage report generated: {report_path}")

    # Also update README badge if README exists
    readme_path = project_root / "README.md"
    if readme_path.exists() and code_cov:
        badge = generate_badge(code_cov['coverage_pct'])
        print(f"\n💡 Add this badge to README.md:\n   {badge}")

    return 0


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    return generate_report(project_root)


if __name__ == "__main__":
    exit(main())
