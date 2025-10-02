#!/usr/bin/env python3
"""Generate requirement-to-test mapping documentation.

This script scans all test files and extracts requirement validation comments
to create a comprehensive mapping of requirements to their implementing tests.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path


def extract_validates_comments(file_path: Path) -> list[str]:
    """Extract all requirement IDs from # Validates: comments in a file."""
    req_ids = []

    try:
        content = file_path.read_text()

        # Find all "# Validates:" comments
        pattern = r'#\s*Validates:\s*\[([^\]]+)\]'
        matches = re.findall(pattern, content)

        for match in matches:
            # Split by commas and clean up each requirement ID
            ids = [req_id.strip() for req_id in match.split(',')]
            req_ids.extend(ids)

    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")

    return req_ids


def scan_test_directory(test_dir: Path) -> dict[str, list[Path]]:
    """Scan test directory and build requirement -> test file mapping."""
    requirement_map = defaultdict(list)

    # Find all test files
    for test_file in test_dir.rglob("test_*.py"):
        # Extract requirement IDs
        req_ids = extract_validates_comments(test_file)

        # Add to mapping
        for req_id in req_ids:
            requirement_map[req_id].append(test_file)

    return requirement_map


def generate_markdown_report(requirement_map: dict[str, list[Path]], output_path: Path):
    """Generate markdown report of requirement-to-test mapping."""

    # Group by requirement category
    categories = defaultdict(list)

    for req_id in sorted(requirement_map.keys()):
        # Extract category (e.g., "SYS", "DH", "PM")
        category = req_id.split('-')[0] if '-' in req_id else "OTHER"
        categories[category].append(req_id)

    # Generate markdown
    lines = [
        "# Requirement to Test Mapping",
        "",
        "**Auto-generated** - Do not edit manually",
        f"**Generated**: {Path.cwd()}",
        "",
        "## Summary",
        "",
        f"- **Total Requirements Covered**: {len(requirement_map)}",
        f"- **Total Test Files**: {sum(len(files) for files in requirement_map.values())}",
        "",
        "## Coverage by Category",
        ""
    ]

    # Category summary
    category_order = ["SYS", "DH", "SE", "RMM", "PM", "REM", "BT", "EL", "AI", "RV", "JSON"]
    for category in category_order:
        if category in categories:
            count = len(categories[category])
            lines.append(f"- **{category}**: {count} requirements")

    lines.extend([
        "",
        "---",
        "",
        "## Detailed Mapping",
        ""
    ])

    # Detailed listing by category
    for category in category_order:
        if category not in categories:
            continue

        lines.extend([
            f"### {category} Requirements",
            ""
        ])

        for req_id in sorted(categories[category]):
            test_files = requirement_map[req_id]

            lines.append(f"#### {req_id}")
            lines.append("")

            # List all test files that validate this requirement
            for test_file in test_files:
                # Get relative path from project root
                try:
                    rel_path = test_file.relative_to(Path.cwd())
                except ValueError:
                    rel_path = test_file

                lines.append(f"- [`{rel_path}`]({rel_path})")

            lines.append("")

    # Write to file
    output_path.write_text("\n".join(lines))
    print(f"Generated requirement-to-test map: {output_path}")


def main():
    """Main entry point."""
    # Find project root (directory containing tests/)
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "tests"

    if not test_dir.exists():
        print(f"Error: Test directory not found at {test_dir}")
        return 1

    print(f"Scanning test directory: {test_dir}")

    # Build mapping
    requirement_map = scan_test_directory(test_dir)

    print(f"Found {len(requirement_map)} unique requirements")

    # Generate report
    output_path = project_root / "docs" / "requirement_to_test_map.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generate_markdown_report(requirement_map, output_path)

    # Print summary
    print("\n=== Summary ===")
    print(f"Requirements covered: {len(requirement_map)}")
    print(f"Test files scanned: {len(list(test_dir.rglob('test_*.py')))}")

    # Find requirements with most tests
    most_tested = sorted(
        requirement_map.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:5]

    print("\nTop 5 most-tested requirements:")
    for req_id, test_files in most_tested:
        print(f"  {req_id}: {len(test_files)} test files")

    return 0


if __name__ == "__main__":
    exit(main())
