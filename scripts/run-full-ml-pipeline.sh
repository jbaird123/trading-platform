#!/bin/bash
# Complete ML Training Pipeline: Campaign Generation to Model Training
#
# This script executes the full end-to-end ML data curation and model training pipeline:
#   1. Generate campaign plans for all campaigns
#   2. Execute all campaign runs (backtests)
#   3. Validate all candidates
#   4. Generate review reports
#   5. Auto-approve all passing candidates
#   6. Enrich approved candidates
#   7. Publish to master trade log
#   8. Train diagnostic models
#   9. Train profitability models
#
# Usage:
#   ./scripts/run-full-ml-pipeline.sh [--skip-cleanup]
#
# Options:
#   --skip-cleanup    Skip initial cleanup of existing campaign data

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get the directory of this script and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Parse arguments
SKIP_CLEANUP=false
if [ "$1" == "--skip-cleanup" ]; then
    SKIP_CLEANUP=true
fi

# Campaign list
CAMPAIGNS=(
    "trend_following_model_generation_baseline_no_risk_15min"
    "trend_following_model_generation_baseline_no_risk_1H"
    "trend_following_model_generation_baseline_no_risk_4H"
    "trend_following_model_generation_baseline_no_risk_1D"
    "trend_following_model_generation_baseline_no_risk_5min"
    "trend_following_model_generation_trend_with_risk_15min"
    "trend_following_model_generation_trend_with_risk_1H"
    "trend_following_model_generation_trend_with_risk_4H"
    "trend_following_model_generation_trend_with_risk_1D"
    "trend_following_model_generation_trend_with_risk_5min"
)

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ML Training Pipeline${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Campaigns:       ${GREEN}${#CAMPAIGNS[@]}${NC}"
echo -e "Working dir:     $(pwd)"
echo -e "Skip cleanup:    $SKIP_CLEANUP"
echo -e "${BLUE}========================================${NC}"
echo ""

# Stage 0: Cleanup (optional)
if [ "$SKIP_CLEANUP" = false ]; then
    echo -e "${YELLOW}[0/9] Cleaning up old campaign data and ML artifacts...${NC}"
    rm -rf data/campaigns
    rm -rf data/dvc/ml
    echo -e "${GREEN}✓ Cleanup complete${NC}"
    echo ""
fi

# Stage 1: Generate Plans
echo -e "${YELLOW}[1/9] Generating campaign plans...${NC}"
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

# Stage 2: Execute All Campaigns
echo -e "${YELLOW}[2/9] Executing all campaign runs...${NC}"
RUN_COUNT=0
for campaign in "${CAMPAIGNS[@]}"; do
    echo -e "${CYAN}Running campaign: $campaign${NC}"
    poetry run tp campaign-run --campaign-id "$campaign" --fail-fast
    RUN_COUNT=$((RUN_COUNT + 1))
    echo -e "${GREEN}✓ $campaign completed ($RUN_COUNT/${#CAMPAIGNS[@]})${NC}"
done
echo -e "${GREEN}✓ All ${RUN_COUNT} campaigns executed successfully${NC}"
echo ""

# Stage 3: Validate All Campaigns
echo -e "${YELLOW}[3/9] Validating all campaigns...${NC}"
TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_WARNINGS=0
for campaign in "${CAMPAIGNS[@]}"; do
    echo "  Validating: $campaign"
    poetry run tp campaign-validate --campaign-id "$campaign"

    VALIDATION_REPORT="data/campaigns/$campaign/validation_report.json"
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

# Stage 4: Generate Review Reports
echo -e "${YELLOW}[4/9] Generating review reports...${NC}"
for campaign in "${CAMPAIGNS[@]}"; do
    echo "  Reviewing: $campaign"
    poetry run tp campaign-review --campaign-id "$campaign"
done
echo -e "${GREEN}✓ All review reports generated${NC}"
echo ""

# Stage 5: Auto-Approve All Passing Candidates
echo -e "${YELLOW}[5/9] Auto-approving all passing candidates...${NC}"
APPROVED_COUNT=0
for campaign in "${CAMPAIGNS[@]}"; do
    VALIDATION_REPORT="data/campaigns/$campaign/validation_report.json"

    if [ -f "$VALIDATION_REPORT" ]; then
        # Extract run_ids with overall_status: passed
        RUN_IDS=$(grep -B 2 '"overall_status": "passed"' "$VALIDATION_REPORT" | grep '"run_id"' | awk -F'"' '{print $4}')

        for RUN_ID in $RUN_IDS; do
            echo "  Approving: $RUN_ID"
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

# Stage 6: Enrich All Campaigns
echo -e "${YELLOW}[6/9] Enriching all approved campaigns...${NC}"
TOTAL_TRADES=0
for campaign in "${CAMPAIGNS[@]}"; do
    echo "  Enriching: $campaign"
    OUTPUT=$(poetry run tp campaign-enrich --campaign-id "$campaign" 2>&1)
    echo "$OUTPUT"

    # Extract trade count from output
    TRADES=$(echo "$OUTPUT" | grep -o 'Enriched [0-9]* trades' | grep -o '[0-9]*')
    if [ -n "$TRADES" ]; then
        TOTAL_TRADES=$((TOTAL_TRADES + TRADES))
    fi
done
echo -e "${GREEN}✓ Enriched ${TOTAL_TRADES} total trades${NC}"
echo ""

# Stage 7: Publish to Master Trade Log
echo -e "${YELLOW}[7/9] Publishing to master trade log...${NC}"
for campaign in "${CAMPAIGNS[@]}"; do
    echo "  Publishing: $campaign"
    poetry run tp campaign-publish --campaign-id "$campaign"
done
echo -e "${GREEN}✓ All campaigns published to master trade log${NC}"
echo ""

# Stage 8: Train Diagnostic Models
echo -e "${YELLOW}[8/9] Training diagnostic models...${NC}"
poetry run tp train-diagnostic-models
DIAGNOSTIC_COUNT=$(find data/dvc/ml/models/diagnostic -name "*.pkl" 2>/dev/null | wc -l | xargs)
echo -e "${GREEN}✓ Trained ${DIAGNOSTIC_COUNT} diagnostic models${NC}"
echo ""

# Stage 9: Train Profitability Models
echo -e "${YELLOW}[9/9] Training profitability models...${NC}"
poetry run tp train-profitability-models
PROFITABILITY_COUNT=$(find data/dvc/ml/models/profitability -name "*.pkl" 2>/dev/null | wc -l | xargs)
echo -e "${GREEN}✓ Trained ${PROFITABILITY_COUNT} profitability models${NC}"
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}ML Pipeline Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${CYAN}Summary:${NC}"
echo -e "  Campaigns executed:      ${GREEN}${RUN_COUNT}${NC}"
echo -e "  Candidates approved:     ${GREEN}${APPROVED_COUNT}${NC}"
echo -e "  Total trades enriched:   ${GREEN}${TOTAL_TRADES}${NC}"
echo -e "  Diagnostic models:       ${GREEN}${DIAGNOSTIC_COUNT}${NC}"
echo -e "  Profitability models:    ${GREEN}${PROFITABILITY_COUNT}${NC}"
echo ""
echo -e "${CYAN}Generated Artifacts:${NC}"
echo "  - Campaign plans:       data/campaigns/*/plan.json"
echo "  - Campaign briefs:      data/campaigns/*/runs/*/brief.json"
echo "  - Enriched data:        data/enriched/*/rich_trades.parquet"
echo "  - Master trade log:     data/dvc/ml/training/master_trade_log.parquet"
echo "  - Diagnostic models:    data/dvc/ml/models/diagnostic/"
echo "  - Profitability models: data/dvc/ml/models/profitability/"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo "  - Review audit log:     docs/ai/logs/campaign_audit.md"
echo "  - Check DVC status:     dvc status"
echo "  - Commit to git:        git add . && git commit -m 'feat: Complete ML pipeline'"
echo "  - Push to DVC:          dvc push"
echo ""
