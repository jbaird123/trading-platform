#!/bin/bash
# Execute HF Scalper Backtest for AUDUSD
# This script must be run from the project root or scripts/hf_scalper_execution/

# Ensure we are in the project root
if [ -d "scripts/hf_scalper_execution" ]; then
    : # We are already in the root
elif [ -f "run_audusd.sh" ]; then
    cd ../.. # Move up two levels from scripts/hf_scalper_execution
fi

echo "Running HF Scalper Backtest for AUDUSD..."
poetry run tp run-backtest --config scripts/hf_scalper_execution/hf_scalper_audusd.yaml
