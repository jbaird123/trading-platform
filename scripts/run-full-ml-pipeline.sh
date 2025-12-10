#!/bin/bash
# Complete ML Training Pipeline: Campaign Generation to Model Training
#
# This script executes the full end-to-end ML data curation and model training pipeline:
#   1. Generate individual campaign configs from meta-campaign definitions
#   2. Generate campaign plans for all campaigns
#   3. Execute all campaign runs (backtests)
#   4. Validate all candidates
#   5. Generate review reports
#   6. Auto-approve all passing candidates
#   7. Enrich approved candidates
#   8. Publish to master trade log
#   9. Train diagnostic models
#  10. Train profitability models
#
# Usage:
#   ./scripts/run-full-ml-pipeline.sh [--skip-cleanup] [--start-from <stage>] \
#       [--train-start YYYY-MM-DD] [--train-end YYYY-MM-DD]
#
# Options:
#   --skip-cleanup    Skip initial cleanup of existing campaign data
#   --start-from      Start execution from a specific stage.
#                     Stages: cleanup, meta_campaign, planning, execution,
#                             validation, review, approve, enrich, publish,
#                             train_diagnostic, train_profitability
#   --train-start     Optional inclusive start date for profitability training
#   --train-end       Optional inclusive end date for profitability training

set -e  # Exit on any error

# --- Configuration ---ƒ
# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

TOTAL_STAGES=10

META_CAMPAIGN_CONFIGS=(
    "config/meta_campaigns/trend_following_data_gen.yaml"
)

# Profitability training date overrides (set env vars to enable)
TRAIN_PROFITABILITY_START=${TRAIN_PROFITABILITY_START:-}
TRAIN_PROFITABILITY_END=${TRAIN_PROFITABILITY_END:-}

# Get the directory of this script and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"


# --- Argument Parsing ---
SKIP_CLEANUP=false
START_STAGE="cleanup"

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --skip-cleanup)
        SKIP_CLEANUP=true
        shift # past argument
        ;;
        --start-from)
        START_STAGE="$2"
        shift # past argument
        shift # past value
        ;;
        --train-start)
        TRAIN_PROFITABILITY_START="$2"
        shift
        shift
        ;;
        --train-end)
        TRAIN_PROFITABILITY_END="$2"
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

# --- Campaign List ---
# Dynamically populated after meta-campaign generation
CAMPAIGNS=()

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ML Training Pipeline${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Working dir:     $(pwd)"
echo -e "Skip cleanup:    $SKIP_CLEANUP"
echo -e "Start from:      $START_STAGE (Stage $START_STAGE_NUM)"
echo -e "${BLUE}========================================${NC}"
echo ""

# --- Pipeline Stages ---

# Stage 0: Cleanup
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    if [ "$SKIP_CLEANUP" = false ]; then
        echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Cleaning up old campaign data and ML artifacts...${NC}"
        rm -rf data/candidates
        rm -rf data/enriched
        rm -rf data/campaigns
        rm -rf workspace/runs/campaign_runner
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

# Stage 1: Generate campaigns from meta-campaign definitions
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Generating campaign configs from meta-campaigns...${NC}"
    META_COUNT=0
    for meta_config in "${META_CAMPAIGN_CONFIGS[@]}"; do
        if [ ! -f "$meta_config" ]; then
            echo -e "${RED}Error: Meta-campaign config not found: $meta_config${NC}"
            exit 1
        fi
        echo "  Meta-campaign: $meta_config"
        poetry run tp meta-campaign-plan \
            --config "$meta_config" \
            --output-dir "config/campaigns/generated" \
            --force
        META_COUNT=$((META_COUNT + 1))
    done
    echo -e "${GREEN}✓ Generated configs from ${META_COUNT} meta-campaign(s)${NC}"
    echo ""

    # Dynamically discover generated campaign configs
    for config_file in config/campaigns/generated/*.yaml; do
        if [ -f "$config_file" ]; then
            campaign_name=$(basename "$config_file" .yaml)
            CAMPAIGNS+=("$campaign_name")
        fi
    done
    echo -e "  Discovered ${#CAMPAIGNS[@]} campaign(s): ${CAMPAIGNS[*]}"
fi
((CURRENT_STAGE++))

# Stage 2: Generate Plans
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Generating campaign plans...${NC}"
    PLAN_COUNT=0
    for campaign in "${CAMPAIGNS[@]}"; do
        CONFIG_FILE="config/campaigns/generated/${campaign}.yaml"
        if [ ! -f "$CONFIG_FILE" ]; then
            echo -e "${RED}Error: Config file not found: $CONFIG_FILE${NC}"
            exit 1
        fi
        echo "  Planning: $campaign"
        poetry run tp campaign-plan --config "$CONFIG_FILE"
        PLAN_COUNT=$((PLAN_COUNT + 1))
    done
    echo -e "${GREEN}✓ Generated ${PLAN_COUNT} campaign plans${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 3: Execute All Campaigns
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Executing all campaign runs...${NC}"
    RUN_COUNT=0
    for campaign in "${CAMPAIGNS[@]}"; do
        echo -e "${CYAN}Running campaign: $campaign${NC}"
        if ! poetry run tp campaign-run --campaign-id "$campaign" --fail-fast; then
            echo -e "${RED}Campaign run failed for $campaign. Check logs under data/campaigns/$campaign for details.${NC}"
            exit 1
        fi
        RUN_COUNT=$((RUN_COUNT + 1))
        echo -e "${GREEN}✓ $campaign completed ($RUN_COUNT/${#CAMPAIGNS[@]})${NC}"
    done
    echo -e "${GREEN}✓ All ${RUN_COUNT} campaigns executed successfully${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 4: Validate All Campaigns
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Validating all campaigns...${NC}"
    TOTAL_PASSED=0
    TOTAL_FAILED=0
    TOTAL_WARNINGS=0
    for campaign in "${CAMPAIGNS[@]}"; do
        echo "  Validating: $campaign"
        poetry run tp campaign-validate --campaign-id "$campaign"

        VALIDATION_REPORT="data/candidates/$campaign/validation_report.json"
        if [ -f "$VALIDATION_REPORT" ]; then
            PASSED=$(grep -o '"passed": [0-9]*' "$VALIDATION_REPORT" | awk '{print $2}')
            FAILED=$(grep -o '"failed": [0-9]*' "$VALIDATION_REPORT" | awk '{print $2}')
            WARNINGS=$(grep -o '"warnings": [0-9]*' "$VALIDATION_REPORT" | awk '{print $2}')

            TOTAL_PASSED=$((TOTAL_PASSED + PASSED))
            TOTAL_FAILED=$((TOTAL_FAILED + FAILED))
            TOTAL_WARNINGS=$((TOTAL_WARNINGS + WARNINGS))
        fi
    done
    echo -e "${GREEN}✓ Validation complete${NC}"
    echo -e "  Total passed:   ${GREEN}${TOTAL_PASSED}${NC}"
    echo -e "  Total failed:   ${RED}${TOTAL_FAILED}${NC}"
    echo -e "  Total warnings: ${YELLOW}${TOTAL_WARNINGS}${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 5: Generate Review Reports
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Generating review reports...${NC}"
    for campaign in "${CAMPAIGNS[@]}"; do
        echo "  Reviewing: $campaign"
        poetry run tp campaign-review --campaign-id "$campaign"
    done
    echo -e "${GREEN}✓ All review reports generated${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 6: Auto-Approve All Passing Candidates
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Auto-approving all passing candidates...${NC}"
    APPROVED_COUNT=0
    for campaign in "${CAMPAIGNS[@]}"; do
        VALIDATION_REPORT="data/candidates/$campaign/validation_report.json"

        if [ -f "$VALIDATION_REPORT" ]; then
            # Extract run_ids with overall_status: passed
            RUN_IDS=$(grep -B 2 '"overall_status": "passed"' "$VALIDATION_REPORT" | grep '"run_id"' | awk -F'"' '{print $4}')

            for RUN_ID in $RUN_IDS; do
                echo "  Approving: $RUN_ID in campaign $campaign"
                poetry run tp campaign-approve \
                    --campaign-id "$campaign" \
                    --run-id "$RUN_ID" \
                    --notes "Auto-approved by run-full-ml-pipeline.sh"
                APPROVED_COUNT=$((APPROVED_COUNT + 1))
            done
        fi
    done
    echo -e "${GREEN}✓ Approved ${APPROVED_COUNT} candidates${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 7: Enrich All Campaigns
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Enriching all approved campaigns...${NC}"
    TOTAL_TRADES=0
    for campaign in "${CAMPAIGNS[@]}"; do
        echo "  Enriching: $campaign"
        OUTPUT=$(poetry run tp campaign-enrich --campaign-id "$campaign" 2>&1)
        echo "$OUTPUT"

        # Extract trade count from output
        TRADES=$(echo "$OUTPUT" | grep -o 'Enriched [0-9]* trades' | grep -o '[0-9]*' || echo "0")
        if [ -n "$TRADES" ]; then
            TOTAL_TRADES=$((TOTAL_TRADES + TRADES))
        fi
    done
    echo -e "${GREEN}✓ Enriched ${TOTAL_TRADES} total trades${NC}"
    echo ""
fi
((CURRENT_STAGE++))

# Stage 8: Publish to Master Trade Log
if [ $CURRENT_STAGE -ge $START_STAGE_NUM ]; then
    echo -e "${YELLOW}[${CURRENT_STAGE}/${TOTAL_STAGES}] Publishing to master trade log...${NC}"
    for campaign in "${CAMPAIGNS[@]}"; do
        echo "  Publishing: $campaign"
        poetry run tp campaign-publish --campaign-id "$campaign"
    done
    echo -e "${GREEN}✓ All campaigns published to master trade log${NC}"
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
    if [ -n "$TRAIN_PROFITABILITY_START" ]; then
        PROF_CMD+=(--train-start "$TRAIN_PROFITABILITY_START")
    fi
    if [ -n "$TRAIN_PROFITABILITY_END" ]; then
        PROF_CMD+=(--train-end "$TRAIN_PROFITABILITY_END")
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
        analysis/rmm/featureset_trial/selected_combos
        --context-model
        5min_trend_following=gb_weighted
        --context-model
        15min_trend_following=gb_weighted
        --context-gate
        5min_trend_following=alignment_full
        --context-gate
        15min_trend_following=alignment_full
        --context-output
        15min_trend_following=structure+momentum:gb_weighted:0.53
    )
    if [ -n "$TRAIN_PROFITABILITY_START" ]; then
        THRESH_CMD+=(--train-start "$TRAIN_PROFITABILITY_START")
    fi
    if [ -n "$TRAIN_PROFITABILITY_END" ]; then
        THRESH_CMD+=(--train-end "$TRAIN_PROFITABILITY_END")
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
echo -e "${GREEN}ML Pipeline Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${CYAN}Summary:${NC}"
echo -e "  Campaigns executed:      ${GREEN}${RUN_COUNT:-0}${NC}"
echo -e "  Candidates approved:     ${GREEN}${APPROVED_COUNT:-0}${NC}"
echo -e "  Total trades enriched:   ${GREEN}${TOTAL_TRADES:-0}${NC}"
echo -e "  Diagnostic models:       ${GREEN}${DIAGNOSTIC_COUNT:-0}${NC}"
echo -e "  Profitability models:    ${GREEN}${PROFITABILITY_COUNT:-0}${NC}"
echo -e "  Profitability classifiers: ${GREEN}${CLASSIFIER_COUNT:-0}${NC}"
echo ""
echo -e "${CYAN}Generated Artifacts:${NC}"
echo "  - Campaign plans:       data/candidates/*/plan.json"
echo "  - Campaign briefs:      data/candidates/*/runs/*/brief.json"
echo "  - Enriched data:        data/enriched/*/rich_trades.parquet"
echo "  - Master trade log:"
echo "      data/dvc/processed/training_sets/master_trade_log.parquet"
echo "  - Diagnostic models:    data/dvc/ml/models/diagnostic/"
echo "  - Profitability models: data/dvc/ml/models/profitability/"
echo "  - Profitability classifiers:"
echo "      data/dvc/ml/models/profitability_classifier/"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo "  - Review audit log:     docs/ai/logs/campaign_audit.md"
echo "  - Check DVC status:     dvc status"
echo "  - Commit to git:        git add . && git commit -m 'feat: Complete ML pipeline'"
echo "  - Push to DVC:          dvc push"
echo ""
