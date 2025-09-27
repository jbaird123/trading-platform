#!/bin/bash
# Data synchronization convenience script
# Usage: ./scripts/sync-data.sh --symbol EUR/USD --data-root ./data
#        ./scripts/sync-data.sh --all --data-root ./data

set -e  # Exit on any error

# Get the directory of this script and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🔄 Running data synchronization..."
echo "Working directory: $(pwd)"

# Pass all arguments to the sync module
poetry run python -m trading_platform.data.sync "$@"

echo "✅ Data synchronization completed"