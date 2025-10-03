#!/usr/bin/env bash
#
# Run a single BB Mean Reversion backtest (no research features)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${SCRIPT_DIR}/backtest.yaml"

echo "Running BB Mean Reversion backtest..."
echo "Config: ${CONFIG}"
echo ""

poetry run python -m trading_platform.cli run-backtest --config "${CONFIG}"

echo ""
echo "Backtest complete. Check runs/ for results."
