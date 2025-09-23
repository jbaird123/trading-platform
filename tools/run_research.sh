#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  tools/run_research.sh \
    --strategy PATH \
    --symbol SYMBOL \
    --timeframe TF \
    --start YYYY-MM-DD \
    --end YYYY-MM-DD \
    --grid GRID_JSON \
    [--user USER] \
    [--out-config PATH] \
    [--compare-last N]

  OR run-only mode with an existing config:
  tools/run_research.sh --config PATH [--user USER] [--compare-last N]

Notes:
  - Generates a research config via tools/make_research_config.py
  - Runs the backtest via CLI and writes artifacts under runs/<user>/...
  - Optionally compares the last N runs for quick A/B review.
USAGE
}

# Resolve repo root relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."

# Defaults
USER_ID="researcher"
OUT_CONFIG=""
COMPARE_LAST="0"

STRAT=""; SYMBOL=""; TF=""; START=""; END=""; GRID=""
CONFIG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strategy) STRAT="$2"; shift 2;;
    --symbol) SYMBOL="$2"; shift 2;;
    --timeframe) TF="$2"; shift 2;;
    --start) START="$2"; shift 2;;
    --end) END="$2"; shift 2;;
    --grid) GRID="$2"; shift 2;;
    --config) CONFIG="$2"; shift 2;;
    --user) USER_ID="$2"; shift 2;;
    --out-config) OUT_CONFIG="$2"; shift 2;;
    --compare-last) COMPARE_LAST="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [[ -n "$CONFIG" ]]; then
  # Run-only mode: use provided config as OUT_CONFIG and skip generation.
  OUT_CONFIG="$CONFIG"
else
  [[ -n "$STRAT" && -n "$SYMBOL" && -n "$TF" && -n "$START" && -n "$END" \
     && -n "$GRID" ]] || { echo "Missing required args" >&2; usage; exit 2; }
fi

# Detect Python interpreter
if [[ -n "${PYTHON:-}" ]]; then
  PY_BIN="$PYTHON"
elif command -v python >/dev/null 2>&1; then
  PY_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PY_BIN="python3"
else
  echo "Missing required command: python (or set \$PYTHON)" >&2
  exit 1
fi

# Detect Poetry (optional; falls back to system Python if unavailable)
if command -v poetry >/dev/null 2>&1; then
  POETRY_BIN="poetry"
else
  POETRY_BIN=""
fi

if [[ -z "$OUT_CONFIG" ]]; then
  ts="${SYMBOL}_${TF}_$(date +%Y%m%d_%H%M%S)"
  OUT_CONFIG="configs/research_${ts}.yaml"
fi

if [[ -z "$CONFIG" ]]; then
  echo "[1/3] Generating config -> $OUT_CONFIG"
  if [[ -n "$POETRY_BIN" ]]; then
    $POETRY_BIN run python "${REPO_ROOT}/tools/make_research_config.py" \
      --strategy "$STRAT" \
      --symbol "$SYMBOL" \
      --timeframe "$TF" \
      --start "$START" \
      --end "$END" \
      --grid-json "$GRID" \
      --out "$OUT_CONFIG"
  else
    PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" \
      "$PY_BIN" "${REPO_ROOT}/tools/make_research_config.py" \
       --strategy "$STRAT" \
       --symbol "$SYMBOL" \
       --timeframe "$TF" \
       --start "$START" \
       --end "$END" \
       --grid-json "$GRID" \
       --out "$OUT_CONFIG"
  fi
else
  echo "[1/3] Using existing config -> $OUT_CONFIG"
fi

echo "[2/3] Running backtest (user=$USER_ID)"
if [[ -n "$POETRY_BIN" ]]; then
  $POETRY_BIN run python -m trading_platform.cli run-backtest \
    --config "$OUT_CONFIG" --user "$USER_ID"
else
  echo "Poetry not found; using system Python." >&2
  PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" \
    "$PY_BIN" -m trading_platform.cli run-backtest \
    --config "$OUT_CONFIG" --user "$USER_ID"
fi

if [[ "$COMPARE_LAST" != "0" ]]; then
  echo "[3/3] Comparing last $COMPARE_LAST runs"
  if [[ -n "$POETRY_BIN" ]]; then
    $POETRY_BIN run python -m trading_platform.cli compare \
      --last "$COMPARE_LAST" --runs-dir runs --user "$USER_ID"
  else
    PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" \
      "$PY_BIN" -m trading_platform.cli compare \
      --last "$COMPARE_LAST" --runs-dir runs --user "$USER_ID"
  fi
else
  echo "[3/3] Skipping compare (set --compare-last N to enable)"
fi

echo "Done."
# Ensure we run from repo root so relative paths (config/, runs/) resolve
cd "${REPO_ROOT}"
