#!/usr/bin/env python3
"""Find tests without requirement traceability comments.

This script identifies:
1. Tests without # Validates: comments
2. Test files without module-level validation
3. Utility/helper tests
"""

from __future__ import annotations

import re
from pathlib import Path


def check_file_has_validates(file_path: Path) -> tuple[bool, list[str]]:
    """Check if file has Validates comments and return all requirement IDs."""
    try:
        content = file_path.read_text()
        pattern = r'#\s*Validates:\s*\[([^\]]+)\]'
        matches = re.findall(pattern, content)

        if not matches:
            return False, []

        # Extract all requirement IDs
        req_ids = []
        for match in matches:
            for req_id in match.split(','):
                req_ids.append(req_id.strip())

        return True, req_ids

    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False, []


def is_utility_test(file_path: Path) -> bool:
    """Check if test file appears to be a utility/infrastructure test."""
    utility_patterns = [
        'conftest',
        '__init__',
        'fixture',
        'helper',
        'utils',
        'common',
        'base',
    ]

    name_lower = file_path.name.lower()
    return any(pattern in name_lower for pattern in utility_patterns)


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "tests"

    print("=" * 70)
    print("Orphaned Test Review")
    print("=" * 70)

    all_test_files = list(test_dir.rglob("test_*.py"))
    orphaned_files = []
    utility_files = []
    validated_files = []

    for test_file in all_test_files:
        has_validates, req_ids = check_file_has_validates(test_file)

        if is_utility_test(test_file):
            utility_files.append(test_file)
        elif not has_validates:
            orphaned_files.append(test_file)
        else:
            validated_files.append((test_file, req_ids))

    # Print summary
    print(f"\n📊 Summary:")
    print(f"   Total test files: {len(all_test_files)}")
    print(f"   ✅ Validated: {len(validated_files)}")
    print(f"   🔧 Utility: {len(utility_files)}")
    print(f"   ❌ Orphaned: {len(orphaned_files)}")

    # List orphaned tests
    if orphaned_files:
        print(f"\n{'=' * 70}")
        print(f"Orphaned Tests (no # Validates: comment):")
        print(f"{'=' * 70}\n")

        # Group by directory
        by_dir = {}
        for file in orphaned_files:
            rel_path = file.relative_to(test_dir)
            dir_name = rel_path.parts[0] if len(rel_path.parts) > 1 else "root"

            if dir_name not in by_dir:
                by_dir[dir_name] = []
            by_dir[dir_name].append(rel_path)

        for dir_name in sorted(by_dir.keys()):
            print(f"\n{dir_name}/")
            for file_path in sorted(by_dir[dir_name]):
                print(f"  - {file_path}")

    # List utility tests
    if utility_files:
        print(f"\n{'=' * 70}")
        print(f"Utility/Infrastructure Tests:")
        print(f"{'=' * 70}\n")

        for file in sorted(utility_files):
            rel_path = file.relative_to(test_dir)
            print(f"  - {rel_path}")

    # Coverage statistics by category
    print(f"\n{'=' * 70}")
    print(f"Coverage by Category:")
    print(f"{'=' * 70}\n")

    category_stats = {}
    for file_path, req_ids in validated_files:
        for req_id in req_ids:
            category = req_id.split('-')[0] if '-' in req_id else 'OTHER'
            if category not in category_stats:
                category_stats[category] = set()
            category_stats[category].add(req_id)

    for category in sorted(category_stats.keys()):
        count = len(category_stats[category])
        print(f"  {category:10s}: {count:3d} requirements")

    # Recommendations
    print(f"\n{'=' * 70}")
    print(f"Recommendations:")
    print(f"{'=' * 70}\n")

    if orphaned_files:
        print(f"1. Review {len(orphaned_files)} orphaned test files")
        print(f"   - Add # Validates: [REQ-ID] comments")
        print(f"   - Or mark as utility tests if appropriate")
        print(f"   - Or remove if obsolete")

    if len(validated_files) < len(all_test_files) * 0.9:
        print(f"\n2. Target 90%+ traceability")
        current_pct = (len(validated_files) / len(all_test_files) * 100) if all_test_files else 0
        print(f"   Current: {current_pct:.1f}%")
        print(f"   Gap: {90 - current_pct:.1f}%")

    print(f"\n3. Document utility tests separately")
    print(f"   Create docs/utility_tests.md listing all utility/infrastructure tests")

    # Save report
    report_path = project_root / "ORPHANED_TESTS.md"
    with open(report_path, 'w') as f:
        f.write("# Orphaned Tests Report\n\n")
        f.write(f"**Generated**: {Path.cwd()}\n\n")

        f.write("## Summary\n\n")
        f.write(f"- Total test files: {len(all_test_files)}\n")
        f.write(f"- Validated: {len(validated_files)}\n")
        f.write(f"- Utility: {len(utility_files)}\n")
        f.write(f"- Orphaned: {len(orphaned_files)}\n\n")

        if orphaned_files:
            f.write("## Orphaned Tests\n\n")
            for dir_name in sorted(by_dir.keys()):
                f.write(f"\n### {dir_name}/\n\n")
                for file_path in sorted(by_dir[dir_name]):
                    f.write(f"- `{file_path}`\n")

    print(f"\n✅ Report saved to: {report_path}")

    return 0


if __name__ == "__main__":
    exit(main())
