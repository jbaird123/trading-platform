#!/usr/bin/env bash
# Wrapper to run the golden_compare utility via Poetry
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 --new path/to/new.csv --golden path/to/golden.csv [additional args...]" >&2
  exit 1
fi

poetry run python scripts/golden_compare.py "$@"
