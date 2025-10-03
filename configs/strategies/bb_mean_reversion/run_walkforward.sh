#!/usr/bin/env bash
#
# Run BB Mean Reversion walk-forward validation
# This validates the strategy with 520 windows (60 trade train, 30 trade test)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${SCRIPT_DIR}/walkforward.yaml"

echo "Running BB Mean Reversion walk-forward validation..."
echo "Config: ${CONFIG}"
echo "Windows: 520 (60 trade train, 30 trade test)"
echo ""

poetry run python -m trading_platform.cli run-backtest --config "${CONFIG}"

echo ""
echo "Walk-forward validation complete. Check runs/ for results."
echo "Expected: Mean OOS PnL ~$6,214.76, Median OOS PnL ~$5,175.00"
