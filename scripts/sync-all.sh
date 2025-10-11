#!/bin/bash
# Sync all instruments with default data directory
# This script assumes your data is stored in ./data relative to project root

set -e  # Exit on any error

# Get the directory of this script and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Check if data directory exists, create if not
DATA_DIR="$PROJECT_ROOT/data/dvc/raw"
if [ ! -d "$DATA_DIR" ]; then
    echo "📁 Creating data directory at $DATA_DIR"
    mkdir -p "$DATA_DIR"
fi

echo "🔄 Synchronizing all instruments..."
echo "Data directory: $DATA_DIR"

# Define the instruments to sync (same as in instrument.py)
INSTRUMENTS=("EUR/USD" "GBP/USD" "AUD/USD" "USD/JPY" "USD/CHF" "USD/CAD" "NZD/USD" "EUR/GBP" "EUR/JPY" "GBP/JPY")

# Run sync for each instrument individually (like running sync-instrument.sh multiple times)
for symbol in "${INSTRUMENTS[@]}"; do
    echo "🔄 Synchronizing instrument: $symbol..."
    if poetry run python -m trading_platform.data.sync --symbol "$symbol" --data-root "$DATA_DIR"; then
        echo "✅ $symbol synchronized successfully"
    else
        echo "❌ Failed to synchronize $symbol"
        # Continue with other instruments instead of failing completely
    fi
done

echo "✅ All instrument synchronization attempts completed"
