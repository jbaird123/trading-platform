#!/bin/bash
#
# Run EMA Crossover with Validated Blackout Policy
# Includes AI qualitative analysis
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "EMA Crossover - Validated Blackout Policy"
echo "=========================================="
echo ""

# Run the backtest
echo "Running backtest..."
poetry run tp \
  --run-config "$SCRIPT_DIR/run_config.yaml" \
  --strategy "$SCRIPT_DIR/strategy.yaml" \
  --rem "$SCRIPT_DIR/rem.yaml"

# Get the most recent run directory
LATEST_RUN=$(ls -td workspace/runs/discovery_campaign/run_* | head -1)

if [ -z "$LATEST_RUN" ]; then
    echo "Error: No run directory found"
    exit 1
fi

echo ""
echo "Backtest complete. Run directory: $LATEST_RUN"
echo ""

# Run AI analysis
echo "Running AI qualitative analysis..."
echo "=========================================="

poetry run python -m trading_platform.ai.llm_analysis.llm_engine \
  --brief-path "$LATEST_RUN/brief.json"

echo ""
echo "=========================================="
echo "Analysis complete!"
echo ""
echo "Full results available at:"
echo "  Brief:  $LATEST_RUN/brief.json"
echo "  Report: $LATEST_RUN/report.html"
echo "  Chart:  $LATEST_RUN/chart.html"
echo "=========================================="
