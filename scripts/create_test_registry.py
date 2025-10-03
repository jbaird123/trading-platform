#!/usr/bin/env python3
"""Create SQLite test registry database.

This script creates a database to track:
- Test files and their requirements
- Coverage statistics
- Test execution history
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path


def create_database(db_path: Path):
    """Create test registry database with schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Requirements table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requirements (
            req_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Test files table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            module_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Test cases table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_cases (
            test_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            test_name TEXT NOT NULL,
            line_number INTEGER,
            FOREIGN KEY (file_id) REFERENCES test_files(file_id),
            UNIQUE(file_id, test_name)
        )
    """)

    # Requirement-Test mapping table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requirement_tests (
            mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            req_id TEXT NOT NULL,
            test_id INTEGER NOT NULL,
            FOREIGN KEY (req_id) REFERENCES requirements(req_id),
            FOREIGN KEY (test_id) REFERENCES test_cases(test_id),
            UNIQUE(req_id, test_id)
        )
    """)

    # Test execution history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_executions (
            execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            status TEXT NOT NULL, -- 'passed', 'failed', 'skipped'
            duration_ms REAL,
            error_message TEXT,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (test_id) REFERENCES test_cases(test_id)
        )
    """)

    # Coverage statistics
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coverage_stats (
            stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            lines_covered INTEGER,
            lines_total INTEGER,
            coverage_pct REAL,
            measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for better query performance
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_req_category ON requirements(category)"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_file ON test_cases(file_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_req_test_req ON requirement_tests(req_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_req_test_test ON requirement_tests(test_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_exec_test ON test_executions(test_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_exec_time ON test_executions(executed_at)"
    )

    conn.commit()
    conn.close()

    print(f"✅ Created test registry database: {db_path}")


def populate_from_test_files(db_path: Path, test_dir: Path):
    """Populate database from existing test files."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    req_pattern = r"#\s*Validates:\s*\[([^\]]+)\]"

    for test_file in test_dir.rglob("test_*.py"):
        rel_path = test_file.relative_to(test_dir.parent)

        # Insert test file
        cursor.execute(
            """
            INSERT OR IGNORE INTO test_files (file_path, module_name)
            VALUES (?, ?)
        """,
            (str(rel_path), test_file.stem),
        )

        file_id = cursor.execute(
            "SELECT file_id FROM test_files WHERE file_path = ?", (str(rel_path),)
        ).fetchone()[0]

        # Parse file for requirements and test functions
        try:
            content = test_file.read_text()

            # Extract requirements
            req_matches = re.findall(req_pattern, content)
            requirements = set()
            for match in req_matches:
                for req_id in match.split(","):
                    req_id = req_id.strip()
                    requirements.add(req_id)

                    # Insert requirement
                    category = req_id.split("-")[0] if "-" in req_id else "OTHER"
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO requirements (req_id, category)
                        VALUES (?, ?)
                    """,
                        (req_id, category),
                    )

            # Extract test functions
            test_func_pattern = r"^def (test_\w+)\("
            for line_num, line in enumerate(content.split("\n"), 1):
                match = re.match(test_func_pattern, line)
                if match:
                    test_name = match.group(1)

                    # Insert test case
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO test_cases
                        (file_id, test_name, line_number)
                        VALUES (?, ?, ?)
                    """,
                        (file_id, test_name, line_num),
                    )

                    # Get test_id
                    test_id = cursor.execute(
                        """
                        SELECT test_id FROM test_cases
                        WHERE file_id = ? AND test_name = ?
                    """,
                        (file_id, test_name),
                    ).fetchone()[0]

                    # Link to requirements (associate with all reqs in file)
                    for req_id in requirements:
                        cursor.execute(
                            """
                            INSERT OR IGNORE INTO requirement_tests (req_id, test_id)
                            VALUES (?, ?)
                        """,
                            (req_id, test_id),
                        )

        except Exception as e:
            print(f"Warning: Could not parse {test_file}: {e}")

    conn.commit()

    # Print statistics
    stats = cursor.execute("""
        SELECT
            (SELECT COUNT(*) FROM requirements) as total_reqs,
            (SELECT COUNT(*) FROM test_files) as total_files,
            (SELECT COUNT(*) FROM test_cases) as total_tests,
            (SELECT COUNT(*) FROM requirement_tests) as total_mappings
    """).fetchone()

    print("✅ Populated database:")
    print(f"   - Requirements: {stats[0]}")
    print(f"   - Test files: {stats[1]}")
    print(f"   - Test cases: {stats[2]}")
    print(f"   - Requirement-test mappings: {stats[3]}")

    conn.close()


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    db_path = project_root / "test_registry.db"
    test_dir = project_root / "tests"

    print("Creating test registry database...")
    create_database(db_path)

    print("\nPopulating from test files...")
    populate_from_test_files(db_path, test_dir)

    print(f"\n✅ Test registry ready at: {db_path}")
    print("\nQuery examples:")
    query = (
        "SELECT req_id, COUNT(*) as test_count FROM requirement_tests "
        "GROUP BY req_id ORDER BY test_count DESC LIMIT 10"
    )
    print(f'  sqlite3 {db_path} "{query}"')

    return 0


if __name__ == "__main__":
    exit(main())
