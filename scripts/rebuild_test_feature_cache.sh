#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SYMBOL="${1:-EURUSD}"
DATA_ROOT="${2:-data/dvc/golden/ohlcv/tradingview}"
CONFIG_PATH="${3:-data/dvc/golden/features/global.yaml}"
CACHE_ROOT="${4:-data/cache_test}"
TIMEFRAMES="${5:-"5min 15min 1H 4H 1D"}"

printf 'Rebuilding global feature cache for %s (data_root=%s, config=%s)\n' "$SYMBOL" "$DATA_ROOT" "$CONFIG_PATH"

poetry run python -m trading_platform.cli precompute-global-features \
  --symbol "$SYMBOL" \
  --data-root "$DATA_ROOT" \
  --config "$CONFIG_PATH" \
  --cache-root "$CACHE_ROOT" \
  --timeframes $TIMEFRAMES \
  --overwrite
