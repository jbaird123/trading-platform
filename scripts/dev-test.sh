#!/bin/bash
# Development test suite - runs all quality checks
# This script runs the full development workflow: tests, linting, and type checking

set -e  # Exit on any error

# Get the directory of this script and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🧪 Running development test suite..."
echo "Working directory: $(pwd)"
echo

# Run tests
echo "📋 Running test suite..."
poetry run pytest -q
echo "✅ Tests passed"
echo

# Run linting
echo "🔍 Running code linting (ruff)..."
poetry run ruff check .
echo "✅ Linting passed"
echo

# Run type checking
echo "🔎 Running type checking (mypy)..."
poetry run mypy .
echo "✅ Type checking passed"
echo

echo "🎉 All development checks completed successfully!"