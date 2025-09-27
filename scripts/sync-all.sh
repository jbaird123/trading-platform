#!/bin/bash
# Sync all instruments with default data directory
# This script assumes your data is stored in ./data relative to project root

set -e  # Exit on any error

# Get the directory of this script and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Check if data directory exists, create if not
DATA_DIR="$PROJECT_ROOT/data"
if [ ! -d "$DATA_DIR" ]; then
    echo "📁 Creating data directory at $DATA_DIR"
    mkdir -p "$DATA_DIR/full"
    mkdir -p "$DATA_DIR/incremental"
fi

echo "🔄 Synchronizing all instruments..."
echo "Data directory: $DATA_DIR"

# Run sync for all instruments
poetry run python -m trading_platform.data.sync --all --data-root "$DATA_DIR"

echo "✅ All instruments synchronized"