#!/bin/bash
# 5min-only ML Pipeline: Targeted training for profitable 5min configs
#
# This script runs a focused ML pipeline using only the profitable 5min
# configurations (4x ATR stop + slow EMAs).
#
# Usage:
#   ./scripts/run-5min-ml-pipeline.sh [--skip-cleanup] [--start-from <stage>] \
#       [--train-start YYYY-MM-DD] [--train-end YYYY-MM-DD]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

TOTAL_STAGES=10

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# --- Argument Parsing ---
SKIP_CLEANUP=false
START_STAGE="cleanup"
TRAIN_START=""
TRAIN_END=""

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --skip-cleanup)
        SKIP_CLEANUP=true
        shift
        ;;
        --start-from)
        START_STAGE="$2"
        shift
        shift
        ;;
        --train-start)
        TRAIN_START="$2"
        shift
        shift
        ;;
        --train-end)
        TRAIN_END="$2"
        shift
        shift
        ;;
        *)
        echo "Unknown option: $1"
        exit 1
        ;;
    esac
done

# --- Stage Definitions ---
get_stage_num() {
    case "$1" in
        "cleanup") echo 0 ;;
        "meta_campaign") echo 1 ;;
        "planning") echo 2 ;;
        "execution") echo 3 ;;
        "validation") echo 4 ;;
        "review") echo 5 ;;
        "approve") echo 6 ;;
        "enrich") echo 7 ;;
        "publish") echo 8 ;;
        "train_diagnostic") echo 9 ;;
        "train_profitability") echo 10 ;;
        *) echo "invalid" ;;
    esac
}

START_STAGE_NUM=$(get_stage_num "$START_STAGE")
if [ "$START_STAGE_NUM" == "invalid" ]; then
    echo -e "${RED}Error: Invalid start stage '$START_STAGE'${NC}"
    exit 1
fi
CURRENT_STAGE=0

CAMPAIGN="5min_profitable_profitable_5min_5min"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}5min Profitable Config ML Pipeline${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Campaign:        ${GREEN}$CAMPAIGN${NC}"
echo -e "Working dir:     $(pwd)"
echo -e "Skip cleanup:    $SKIP_CLEANUP"
echo -e "Start from:      $START_STAGE (Stage $START_STAGE_NUM)"
if [ -n "$TRAIN_START" ]; then
    echo -e "Train start:     $TRAIN_START"
fi
if [ -n "$TRAIN_END" ]; then
    echo -e "Train end:       $TRAIN_END"
fi
echo -e "${BLUE}========================================${NC}"
echo ""

# Stage 0: Cleanup
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    if [ "$SKIP_CLEANUP" = false ]; then
        echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Cleaning up old campaign data and ML artifacts...${NC}"
        rm -rf data/candidates/$CAMPAIGN
        rm -rf data/enriched/$CAMPAIGN
        rm -rf data/campaigns/$CAMPAIGN
        rm -rf data/dvc/ml
        rm -f data/dvc/processed/training_sets/master_trade_log.parquet
        echo -e "${GREEN}✓ Cleanup complete${NC}"
        echo ""
    else
        echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Skipping cleanup.${NC}"
        echo ""
    fi
fi
((CURRENT_STAGE++))

# Stage 1: Generate campaign from meta-campaign
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Generating campaign config from meta-campaign...${NC}"
    poetry run tp meta-campaign-plan \
        --config "config/meta_campaigns/5min_profitable_only.yaml" \
        --output-dir "config/campaigns/generated" \
        --force
    echo -e "${GREEN}✓ Campaign config generated${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 2: Generate plan
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Generating campaign plan...${NC}"
    poetry run tp campaign-plan --config "config/campaigns/generated/${CAMPAIGN}.yaml"
    echo -e "${GREEN}✓ Plan generated${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 3: Execute campaign
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Executing campaign runs...${NC}"
    poetry run tp campaign-run --campaign-id "$CAMPAIGN" --fail-fast
    echo -e "${GREEN}✓ Campaign executed${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 4: Validate
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Validating campaign...${NC}"
    poetry run tp campaign-validate --campaign-id "$CAMPAIGN"
    echo -e "${GREEN}✓ Validation complete${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 5: Review
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Generating review report...${NC}"
    poetry run tp campaign-review --campaign-id "$CAMPAIGN"
    echo -e "${GREEN}✓ Review report generated${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 6: Auto-approve
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Auto-approving passing candidates...${NC}"
    APPROVED_COUNT=0
    VALIDATION_REPORT="data/candidates/$CAMPAIGN/validation_report.json"
    if [ -f "$VALIDATION_REPORT" ]; then
        RUN_IDS=$(grep -B 2 '"overall_status": "passed"' "$VALIDATION_REPORT" | grep '"run_id"' | awk -F'"' '{print $4}')
        for RUN_ID in $RUN_IDS; do
            echo "  Approving: $RUN_ID"
            poetry run tp campaign-approve \
                --campaign-id "$CAMPAIGN" \
                --run-id "$RUN_ID" \
                --notes "Auto-approved by 5min pipeline"
            APPROVED_COUNT=$((APPROVED_COUNT + 1))
        done
    fi
    echo -e "${GREEN}✓ Approved ${APPROVED_COUNT} candidates${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 7: Enrich
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Enriching approved campaigns...${NC}"
    poetry run tp campaign-enrich --campaign-id "$CAMPAIGN"
    echo -e "${GREEN}✓ Enrichment complete${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 8: Publish to Master Trade Log
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Publishing to master trade log...${NC}"
    poetry run tp campaign-publish --campaign-id "$CAMPAIGN"
    echo -e "${GREEN}✓ Published to master trade log${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 9: Train Diagnostic Models
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Training diagnostic models...${NC}"
    poetry run tp train-diagnostic-models \
        --enriched-data data/dvc/processed/training_sets/master_trade_log.parquet \
        --model-dir data/dvc/ml/models
    DIAGNOSTIC_COUNT=$(find data/dvc/ml/models/diagnostic -name "*.pkl" 2>/dev/null | wc -l | xargs)
    echo -e "${GREEN}✓ Trained ${DIAGNOSTIC_COUNT} diagnostic models${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 10: Train Profitability Models
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Training profitability models...${NC}"
    PROF_CMD=(
        poetry
        run
        tp
        train-profitability-models
        --enriched-data
        data/dvc/processed/training_sets/master_trade_log.parquet
        --model-dir
        data/dvc/ml/models
    )
    if [ -n "$TRAIN_START" ]; then
        PROF_CMD+=(--train-start "$TRAIN_START")
    fi
    if [ -n "$TRAIN_END" ]; then
        PROF_CMD+=(--train-end "$TRAIN_END")
    fi
    "${PROF_CMD[@]}"

    echo "  → Generating threshold recommendations..."
    THRESH_CMD=(
        poetry
        run
        python
        scripts/rmm_analysis/generate_threshold_recommendations.py
        --enriched-data
        data/dvc/processed/training_sets/master_trade_log.parquet
        --output-dir
        analysis/rmm/5min_profitable
        --context-model
        5min_trend_following=gb_weighted
        --context-gate
        5min_trend_following=alignment_full
    )
    if [ -n "$TRAIN_START" ]; then
        THRESH_CMD+=(--train-start "$TRAIN_START")
    fi
    if [ -n "$TRAIN_END" ]; then
        THRESH_CMD+=(--train-end "$TRAIN_END")
    fi
    "${THRESH_CMD[@]}"

    PROFITABILITY_COUNT=$(
        find data/dvc/ml/models/profitability -name "*.pkl" 2>/dev/null \
            | wc -l | xargs
    )
    CLASSIFIER_COUNT=$(
        find data/dvc/ml/models/profitability_classifier -name "*.pkl" 2>/dev/null \
            | wc -l | xargs
    )
    echo -e "${GREEN}✓ Trained ${PROFITABILITY_COUNT} profitability models${NC}"
    echo -e "${GREEN}✓ Trained ${CLASSIFIER_COUNT} profitability classifiers${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# --- Summary ---
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}5min ML Pipeline Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${CYAN}Summary:${NC}"
echo -e "  Candidates approved:     ${GREEN}${APPROVED_COUNT:-0}${NC}"
echo -e "  Diagnostic models:       ${GREEN}${DIAGNOSTIC_COUNT:-0}${NC}"
echo -e "  Profitability models:    ${GREEN}${PROFITABILITY_COUNT:-0}${NC}"
echo -e "  Profitability classifiers: ${GREEN}${CLASSIFIER_COUNT:-0}${NC}"
echo ""
echo -e "${CYAN}Generated Artifacts:${NC}"
echo "  - Campaign plan:        data/candidates/$CAMPAIGN/plan.json"
echo "  - Enriched data:        data/enriched/$CAMPAIGN/rich_trades.parquet"
echo "  - Master trade log:"
echo "      data/dvc/processed/training_sets/master_trade_log.parquet"
echo "  - Diagnostic models:    data/dvc/ml/models/diagnostic/"
echo "  - Profitability models: data/dvc/ml/models/profitability/"
echo "  - Threshold analysis:   analysis/rmm/5min_profitable/"
echo ""
