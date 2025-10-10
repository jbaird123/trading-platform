#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/../../.."

# Use the baseline config for a single backtest (no research sections)
CONFIG_BASELINE="${SCRIPT_DIR}/backtest.yaml"
USER_ID="${USER_ID:-researcher}"

cd "${REPO_ROOT}"

if command -v poetry >/dev/null 2>&1; then
  poetry run python -m trading_platform.cli run-backtest \
    --config "$CONFIG_BASELINE" --user "$USER_ID"
else
  PY_BIN="${PYTHON:-python}"
  if ! command -v "$PY_BIN" >/dev/null 2>&1; then
    if command -v python3 >/dev/null 2>&1; then PY_BIN="python3"; else
      echo "Missing python; set \$PYTHON or install python." >&2; exit 1; fi
  fi
  PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" \
    "$PY_BIN" -m trading_platform.cli run-backtest \
    --config "$CONFIG_BASELINE" --user "$USER_ID"
fi
