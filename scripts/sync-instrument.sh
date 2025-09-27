#!/bin/bash
# Sync a single instrument by passing its name as an argument.
# Usage: ./scripts/sync-instrument.sh EUR/USD

set -e # Exit on any error

# Check if symbol is provided
if [ -z "$1" ]; then
    echo "❌ Error: No instrument symbol provided."
    echo "Usage: $0 <SYMBOL>"
    echo "Example: $0 EUR/USD"
    exit 1
fi

SYMBOL=$1

# Get the directory of this script and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

DATA_DIR="$PROJECT_ROOT/data"

echo "🔄 Synchronizing instrument: $SYMBOL..."
echo "Data directory: $DATA_DIR"

# Run sync for the specified instrument
poetry run python -m trading_platform.data.sync --symbol "$SYMBOL" --data-root "$DATA_DIR"

echo "✅ Instrument $SYMBOL synchronized."
