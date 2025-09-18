#!/usr/bin/env python
"""
A script to enforce architectural separation by ensuring that strategy definition
files do not contain risk-management-related keywords.
"""

import argparse
import re
import sys
from pathlib import Path

# Keywords related to risk and exit management that should NOT be in a strategy file.
FORBIDDEN_KEYWORDS = {
    "stop_loss",
    "take_profit",
    "sl",
    "tp",
    "trailing_stop",
    "risk",
    "exit_manager",
    "rem",
}


def find_forbidden_keywords(file_path: Path) -> list[str]:
    """Scans a file for forbidden keywords and returns any that are found."""
    found_keywords = []
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read().lower()
            for keyword in FORBIDDEN_KEYWORDS:
                # Check for whole word matches only
                if re.search(r"\b" + re.escape(keyword) + r"\b", content):
                    found_keywords.append(keyword)
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
    return sorted(list(set(found_keywords)))


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Check strategy files for forbidden risk management keywords."
    )
    parser.add_argument("files", nargs="*", help="Files to check.")
    args = parser.parse_args()

    exit_code = 0
    for file_path_str in args.files:
        file_path = Path(file_path_str)
        if file_path.is_file():
            found = find_forbidden_keywords(file_path)
            if found:
                print(
                    f"Error: Found forbidden risk-management keywords in strategy "
                    f"file '{file_path}': {', '.join(found)}",
                    file=sys.stderr,
                )
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
