#!/bin/bash
# Run backtesting demo
# This script runs the demo backtest that's built into the platform

set -e  # Exit on any error

# Get the directory of this script and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🚀 Running backtesting demo..."
echo "Working directory: $(pwd)"

# Run the demo backtest
poetry run python -m trading_platform.core.demo

echo "✅ Demo backtest completed"
echo "📊 Check the generated files for results"