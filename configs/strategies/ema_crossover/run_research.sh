#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/../../.."

CONFIG="${SCRIPT_DIR}/research.yaml"
USER_ID="${USER_ID:-researcher}"
COMPARE_LAST="${COMPARE_LAST:-3}"

cd "${REPO_ROOT}"

"${REPO_ROOT}/tools/run_research.sh" \
  --config "$CONFIG" \
  --user "$USER_ID" \
  --compare-last "$COMPARE_LAST"
