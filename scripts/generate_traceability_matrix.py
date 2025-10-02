#!/usr/bin/env python3
"""Generate comprehensive requirements traceability matrix from test registry."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def generate_traceability_matrix(db_path: Path, output_path: Path):
    """Generate requirements traceability matrix in Markdown format."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all requirements with test counts
    cursor.execute("""
        SELECT
            r.req_id,
            r.category,
            r.description,
            COUNT(DISTINCT tf.file_path) as file_count,
            COUNT(DISTINCT tc.test_id) as test_count
        FROM requirements r
        LEFT JOIN requirement_tests rt ON r.req_id = rt.req_id
        LEFT JOIN test_cases tc ON rt.test_id = tc.test_id
        LEFT JOIN test_files tf ON tc.file_id = tf.file_id
        GROUP BY r.req_id, r.category, r.description
        ORDER BY r.category, r.req_id
    """)

    requirements = cursor.fetchall()

    # Get summary statistics
    cursor.execute("SELECT COUNT(*) FROM requirements")
    total_reqs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT req_id) FROM requirement_tests")
    covered_reqs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM test_files")
    total_test_files = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM test_cases")
    total_test_cases = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM requirement_tests")
    total_mappings = cursor.fetchone()[0]

    # Generate markdown
    lines = [
        "# Requirements Traceability Matrix (RTM)",
        "",
        f"**Generated**: 2025-10-02",
        f"**Database**: {db_path.name}",
        "",
        "## Executive Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| **Total Requirements** | {total_reqs} |",
        f"| **Requirements with Tests** | {covered_reqs} ({covered_reqs/total_reqs*100:.1f}%) |",
        f"| **Total Test Files** | {total_test_files} |",
        f"| **Total Test Cases** | {total_test_cases} |",
        f"| **Requirement-Test Mappings** | {total_mappings} |",
        "",
        "## Traceability by Category",
        "",
    ]

    # Group by category
    current_category = None
    category_stats = {}

    for req_id, category, description, file_count, test_count in requirements:
        if category != current_category:
            if current_category:
                lines.append("")
            lines.append(f"### {category}")
            lines.append("")
            lines.append("| Requirement ID | Description | Test Files | Test Cases | Status |")
            lines.append("|----------------|-------------|------------|------------|--------|")
            current_category = category
            category_stats[category] = {'total': 0, 'covered': 0}

        category_stats[category]['total'] += 1
        if test_count > 0:
            category_stats[category]['covered'] += 1
            status = "✅"
        else:
            status = "❌"

        # Truncate long descriptions
        desc_short = description[:60] + "..." if description and len(description) > 60 else (description or "N/A")
        lines.append(f"| {req_id} | {desc_short} | {file_count} | {test_count} | {status} |")

    lines.append("")
    lines.append("## Category Coverage Summary")
    lines.append("")
    lines.append("| Category | Total Reqs | Covered | Coverage % | Status |")
    lines.append("|----------|------------|---------|------------|--------|")

    for category in sorted(category_stats.keys()):
        stats = category_stats[category]
        coverage = stats['covered'] / stats['total'] * 100 if stats['total'] > 0 else 0
        status = "✅" if coverage >= 90 else "🟡" if coverage >= 70 else "❌"
        lines.append(f"| {category} | {stats['total']} | {stats['covered']} | {coverage:.1f}% | {status} |")

    # Add detailed mappings section
    lines.extend([
        "",
        "## Detailed Requirement-Test Mappings",
        "",
        "This section provides complete traceability from each requirement to all test cases that validate it.",
        "",
    ])

    # Get detailed mappings for each requirement
    cursor.execute("""
        SELECT
            r.req_id,
            r.category,
            r.description,
            tf.file_path,
            tc.test_name
        FROM requirements r
        LEFT JOIN requirement_tests rt ON r.req_id = rt.req_id
        LEFT JOIN test_cases tc ON rt.test_id = tc.test_id
        LEFT JOIN test_files tf ON tc.file_id = tf.file_id
        ORDER BY r.category, r.req_id, tf.file_path, tc.test_name
    """)

    mappings = cursor.fetchall()
    current_req = None

    for req_id, category, description, test_file, test_case in mappings:
        if req_id != current_req:
            if current_req:
                lines.append("")
            lines.append(f"### {req_id}: {description or 'N/A'}")
            lines.append(f"**Category**: {category}")
            if test_file:
                lines.append("**Test Coverage**:")
            else:
                lines.append("**Test Coverage**: ❌ No tests found")
            current_req = req_id

        if test_file and test_case:
            # Format as markdown bullet with code
            lines.append(f"- `{test_file}::{test_case}`")

    # Add usage instructions
    lines.extend([
        "",
        "---",
        "",
        "## How to Use This Matrix",
        "",
        "### For Developers",
        "1. **Adding New Features**: Check which requirements apply to your feature",
        "2. **Writing Tests**: Use the requirement ID in test docstrings with `# Validates: [REQ-ID]`",
        "3. **Verifying Coverage**: Ensure all requirements have at least one test",
        "",
        "### For QA/Testing",
        "1. **Test Planning**: Identify requirements with low test coverage",
        "2. **Regression Testing**: Find all tests for a given requirement",
        "3. **Impact Analysis**: When requirements change, find affected tests",
        "",
        "### For Project Management",
        "1. **Progress Tracking**: Monitor requirements coverage percentage",
        "2. **Risk Assessment**: Identify high-priority requirements without tests",
        "3. **Compliance**: Demonstrate traceability for audits",
        "",
        "## Maintenance",
        "",
        "This matrix is automatically generated from the test registry database.",
        "",
        "**To regenerate**:",
        "```bash",
        "poetry run python scripts/create_test_registry.py",
        "poetry run python scripts/generate_traceability_matrix.py",
        "```",
        "",
        "**Update frequency**: Run after:",
        "- Adding new test files",
        "- Modifying test validation comments",
        "- Adding new requirements",
        "- Major refactoring",
        "",
        "## Query Examples",
        "",
        "### Find all tests for a requirement",
        "```sql",
        "SELECT test_file, test_case ",
        "FROM requirement_tests ",
        "WHERE req_id = 'PM-5.8.1';",
        "```",
        "",
        "### Find requirements without tests",
        "```sql",
        "SELECT req_id, category, description",
        "FROM requirements",
        "WHERE req_id NOT IN (SELECT DISTINCT req_id FROM requirement_tests);",
        "```",
        "",
        "### Find most tested requirements",
        "```sql",
        "SELECT req_id, COUNT(*) as test_count",
        "FROM requirement_tests",
        "GROUP BY req_id",
        "ORDER BY test_count DESC",
        "LIMIT 10;",
        "```",
        "",
        "## Related Documents",
        "",
        "- [Project Requirements](docs/project_requirements.md) - Full requirements specification",
        "- [Testing Guide](docs/testing_guide.md) - How to write tests with traceability",
        "- [Requirements Check Report](REQUIREMENTS_CHECK_REPORT_FINAL.md) - Coverage analysis",
        "- [Test Registry Database](test_registry.db) - Source data for this matrix",
    ])

    # Write to file
    output_path.write_text("\n".join(lines))
    print(f"✅ Generated traceability matrix: {output_path}")
    print(f"   - {total_reqs} requirements")
    print(f"   - {covered_reqs} with tests ({covered_reqs/total_reqs*100:.1f}%)")
    print(f"   - {total_mappings} requirement-test mappings")

    conn.close()


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    db_path = project_root / "test_registry.db"
    output_path = project_root / "REQUIREMENTS_TRACEABILITY_MATRIX.md"

    if not db_path.exists():
        print(f"❌ Test registry database not found: {db_path}")
        print("Run: poetry run python scripts/create_test_registry.py")
        exit(1)

    generate_traceability_matrix(db_path, output_path)
