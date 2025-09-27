#!/bin/bash

# ---
#
# 🚀 Strategy Improvement Cycle Runner 🚀
#
# Description:
#   This script automates one full cycle of the strategy improvement plan.
#   It takes a strategy backtest configuration file, runs a full suite of
#   analyses (backtest, parameter search, WFE, Monte Carlo), and then
#   generates both quantitative and qualitative AI diagnostic reports.
#
# Usage:
#   ./scripts/run-improvement-cycle.sh <path_to_backtest_config.yaml>
#
# Example:
#   ./scripts/run-improvement-cycle.sh configs/strategies/ema_crossover/backtest.yaml
#
# ---

set -e # Exit immediately if a command exits with a non-zero status.

# Navigate to the project root directory
cd "$(dirname "$0")/.."

# --- Configuration ---
# Check if a config file was provided
if [ -z "$1" ]; then
  echo "❌ Error: No configuration file provided."
  echo "Usage: $0 <path_to_backtest_config.yaml>"
  exit 1
fi

CONFIG_FILE=$1
STRATEGY_NAME=$(basename -s .yaml "$(dirname "$CONFIG_FILE")")

echo "🚀 Starting Strategy Improvement Cycle for: $STRATEGY_NAME"
echo ""

# --- Step 1: Run Backtest with Full Analysis ---
echo "📊 [1/3] Running full backtest and analysis..."
# Capture the output of the run command to find the run path
RUN_OUTPUT=$(poetry run tp run-backtest --config "$CONFIG_FILE")
echo "$RUN_OUTPUT" # Print the output for the user to see

# Parse the run path from the output
RUN_DIR=$(echo "$RUN_OUTPUT" | grep "Run created at:" | awk '{print $4}')

if [ -z "$RUN_DIR" ]; then
    echo "❌ ERROR: Could not determine run directory from backtest output."
    exit 1
fi
echo "✅ Backtest complete. Results are in: $RUN_DIR"
echo ""

# Find the generated brief.json
BRIEF_PATH="$RUN_DIR/brief.json"
if [ ! -f "$BRIEF_PATH" ]; then
    echo "❌ ERROR: brief.json not found in $RUN_DIR"
    exit 1
fi

# --- Step 2: Run Quantitative AI Diagnosis ---
echo "🤖 [2/3] Running Quantitative AI Diagnosis..."
# The ai-diagnose command saves reports in the same dir as the brief
poetry run tp ai-diagnose --brief "$BRIEF_PATH"
QUANT_REPORT_PATH="${RUN_DIR}/ai_diagnostic_report.json"
echo "✅ Quantitative diagnosis complete. Report at: $QUANT_REPORT_PATH"
echo ""

# --- Step 3: Run Qualitative AI Diagnosis ---
echo "🧠 [3/3] Running Qualitative AI Diagnosis (LLM-based)..."
poetry run tp ai-diagnose --brief "$BRIEF_PATH" --qualitative-report
QUAL_REPORT_PATH="${RUN_DIR}/ai_qualitative_report.md"
echo "✅ Qualitative diagnosis complete. Report at: $QUAL_REPORT_PATH"
echo ""

# --- Step 4: Next Steps ---
echo "🎉 --- Cycle Complete --- 🎉"
echo "All automated analysis for this cycle is finished."
echo ""
echo "👉 NEXT ACTIONS:"
echo "1. Review the results in the '$RUN_DIR' directory."
echo "2. Analyze the reports:"
echo "   - Quantitative: $QUANT_REPORT_PATH"
echo "   - Qualitative:  $QUAL_REPORT_PATH"
echo "3. Based on the analysis, create a new version of your strategy YAML file."
echo "4. Run this script again with the path to your new config file to start the next iteration."
echo "   e.g., ./scripts/run-improvement-cycle.sh configs/strategies/ema_crossover_v2/backtest.yaml"
