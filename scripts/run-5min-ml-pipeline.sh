#!/bin/bash
# 5min-only ML Pipeline: Targeted training for profitable 5min configs
#
# This script runs a focused ML pipeline using only the profitable 5min
# configurations (4x ATR stop + slow EMAs).

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Parse args
TRAIN_START=${1:-"2018-01-01"}
TRAIN_END=${2:-"2021-12-31"}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}5min Profitable Config ML Pipeline${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Train period: $TRAIN_START to $TRAIN_END"
echo ""

# Stage 1: Generate campaign from meta-campaign
echo -e "${YELLOW}[1/8] Generating campaign config...${NC}"
poetry run tp meta-campaign-plan \
    --config "config/meta_campaigns/5min_profitable_only.yaml" \
    --output-dir "config/campaigns/generated" \
    --force
echo -e "${GREEN}✓ Campaign config generated${NC}"
echo ""

CAMPAIGN="5min_profitable_profitable_5min_5min"

# Stage 2: Generate plan
echo -e "${YELLOW}[2/8] Generating campaign plan...${NC}"
poetry run tp campaign-plan --config "config/campaigns/generated/${CAMPAIGN}.yaml"
echo -e "${GREEN}✓ Plan generated${NC}"
echo ""

# Stage 3: Execute campaign
echo -e "${YELLOW}[3/8] Executing campaign runs...${NC}"
poetry run tp campaign-run --campaign-id "$CAMPAIGN" --fail-fast
echo -e "${GREEN}✓ Campaign executed${NC}"
echo ""

# Stage 4: Validate
echo -e "${YELLOW}[4/8] Validating campaign...${NC}"
poetry run tp campaign-validate --campaign-id "$CAMPAIGN"
echo -e "${GREEN}✓ Validation complete${NC}"
echo ""

# Stage 5: Review
echo -e "${YELLOW}[5/8] Generating review report...${NC}"
poetry run tp campaign-review --campaign-id "$CAMPAIGN"
echo -e "${GREEN}✓ Review report generated${NC}"
echo ""

# Stage 6: Auto-approve
echo -e "${YELLOW}[6/8] Auto-approving passing candidates...${NC}"
VALIDATION_REPORT="data/candidates/$CAMPAIGN/validation_report.json"
if [ -f "$VALIDATION_REPORT" ]; then
    RUN_IDS=$(grep -B 2 '"overall_status": "passed"' "$VALIDATION_REPORT" | grep '"run_id"' | awk -F'"' '{print $4}')
    for RUN_ID in $RUN_IDS; do
        echo "  Approving: $RUN_ID"
        poetry run tp campaign-approve \
            --campaign-id "$CAMPAIGN" \
            --run-id "$RUN_ID" \
            --notes "Auto-approved by 5min pipeline"
    done
fi
echo -e "${GREEN}✓ Candidates approved${NC}"
echo ""

# Stage 7: Enrich
echo -e "${YELLOW}[7/8] Enriching approved campaigns...${NC}"
poetry run tp campaign-enrich --campaign-id "$CAMPAIGN"
echo -e "${GREEN}✓ Enrichment complete${NC}"
echo ""

# Stage 8: Train profitability models (5min context only)
echo -e "${YELLOW}[8/8] Training profitability models...${NC}"

# First, we need to publish to a separate trade log for 5min only
ENRICHED_DIR="data/enriched/$CAMPAIGN"
TRADE_LOG="$ENRICHED_DIR/rich_trades.parquet"

if [ -f "$TRADE_LOG" ]; then
    echo "  Training on: $TRADE_LOG"

    # Train profitability models
    poetry run tp train-profitability-models \
        --enriched-data "$TRADE_LOG" \
        --model-dir "data/dvc/ml/models_5min_profitable" \
        --train-start "$TRAIN_START" \
        --train-end "$TRAIN_END"

    # Generate threshold recommendations
    poetry run python scripts/rmm_analysis/generate_threshold_recommendations.py \
        --enriched-data "$TRADE_LOG" \
        --output-dir "analysis/rmm/5min_profitable" \
        --context-model "5min_trend_following=gb_weighted" \
        --context-gate "5min_trend_following=alignment_full" \
        --train-start "$TRAIN_START" \
        --train-end "$TRAIN_END"

    echo -e "${GREEN}✓ Models trained${NC}"
else
    echo -e "${RED}Error: Trade log not found at $TRADE_LOG${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}5min Pipeline Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${CYAN}Results:${NC}"
echo "  - Models: data/dvc/ml/models_5min_profitable/"
echo "  - Analysis: analysis/rmm/5min_profitable/"
echo ""
