#!/usr/bin/env python3
"""Validate that all requirements have tests.

This script checks the test registry database and REQUIREMENTS.md
to ensure all documented requirements have associated tests.

Exit code 0: All requirements covered
Exit code 1: Missing coverage detected
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path


def load_requirements_from_docs(req_file: Path) -> set[str]:
    """Extract all requirement IDs from REQUIREMENTS.md."""
    if not req_file.exists():
        print(f"Warning: {req_file} not found")
        return set()

    content = req_file.read_text()

    # Pattern to match requirement IDs like [SYS-1.2.3], [DH-2.1], etc.
    pattern = r'\[([A-Z]+-[0-9.]+)\]'
    req_ids = set(re.findall(pattern, content))

    return req_ids


def get_covered_requirements(db_path: Path) -> set[str]:
    """Get all requirements that have tests from database."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        print("Run: python3 scripts/create_test_registry.py")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT req_id FROM requirement_tests")
    covered = {row[0] for row in cursor.fetchall()}

    conn.close()
    return covered


def main():
    """Main validation logic."""
    project_root = Path(__file__).parent.parent
    req_file = project_root / "REQUIREMENTS.md"
    db_path = project_root / "test_registry.db"

    print("=" * 60)
    print("Requirements Coverage Validation")
    print("=" * 60)

    # Load documented requirements
    documented_reqs = load_requirements_from_docs(req_file)
    print(f"\n📋 Documented requirements: {len(documented_reqs)}")

    # Load covered requirements
    covered_reqs = get_covered_requirements(db_path)
    print(f"✅ Requirements with tests: {len(covered_reqs)}")

    # Calculate coverage
    if documented_reqs:
        coverage_pct = (len(covered_reqs) / len(documented_reqs)) * 100
        print(f"📊 Coverage: {coverage_pct:.1f}%")
    else:
        coverage_pct = 0.0

    # Find missing coverage
    missing_reqs = documented_reqs - covered_reqs
    extra_reqs = covered_reqs - documented_reqs

    print("\n" + "=" * 60)

    if missing_reqs:
        print(f"\n❌ Missing tests for {len(missing_reqs)} requirements:")
        for req_id in sorted(missing_reqs)[:20]:  # Show first 20
            print(f"   - {req_id}")
        if len(missing_reqs) > 20:
            print(f"   ... and {len(missing_reqs) - 20} more")

    if extra_reqs:
        print(f"\n⚠️  Tests exist for {len(extra_reqs)} undocumented requirements:")
        for req_id in sorted(extra_reqs)[:10]:  # Show first 10
            print(f"   - {req_id}")
        if len(extra_reqs) > 10:
            print(f"   ... and {len(extra_reqs) - 10} more")

    # Coverage by category
    print("\n" + "=" * 60)
    print("Coverage by Category:")
    print("=" * 60)

    categories = {}
    for req_id in documented_reqs:
        category = req_id.split('-')[0] if '-' in req_id else 'OTHER'
        if category not in categories:
            categories[category] = {'total': 0, 'covered': 0}
        categories[category]['total'] += 1
        if req_id in covered_reqs:
            categories[category]['covered'] += 1

    for category in sorted(categories.keys()):
        stats = categories[category]
        cat_coverage = (stats['covered'] / stats['total'] * 100) if stats['total'] > 0 else 0
        status = "✅" if cat_coverage >= 90 else "🟡" if cat_coverage >= 70 else "🔴"
        print(f"{status} {category:10s}: {stats['covered']:3d}/{stats['total']:3d} ({cat_coverage:5.1f}%)")

    # Determine exit code
    print("\n" + "=" * 60)

    target_coverage = 90.0
    if coverage_pct >= target_coverage:
        print(f"✅ PASSED: Coverage {coverage_pct:.1f}% >= {target_coverage}% target")
        return 0
    else:
        print(f"❌ FAILED: Coverage {coverage_pct:.1f}% < {target_coverage}% target")
        print(f"\nTo pass validation:")
        print(f"  - Add tests for {len(missing_reqs)} missing requirements")
        print(f"  - Current gap: {target_coverage - coverage_pct:.1f}%")
        return 1


if __name__ == "__main__":
    exit(main())
