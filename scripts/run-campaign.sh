#!/bin/bash
# Execute a complete campaign workflow from plan to publish
#
# Usage:
#   ./scripts/run-campaign.sh <campaign_config.yaml>
#   ./scripts/run-campaign.sh --help
#
# Example:
#   ./scripts/run-campaign.sh config/campaigns/example_trend_following_15m.yaml
#
# This script executes the full campaign workflow:
#   1. Generate execution plan with provenance
#   2. Execute all campaign runs
#   3. Validate candidates with quality gates
#   4. Generate review report
#   5. Optionally auto-approve candidates
#   6. Enrich approved candidates
#   7. Publish to master trade log

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory of this script and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Display help
show_help() {
    cat << EOF
Campaign Runner Script

Execute a complete campaign workflow from plan to publish.

USAGE:
    ./scripts/run-campaign.sh <campaign_config.yaml> [OPTIONS]

ARGUMENTS:
    campaign_config.yaml    Path to campaign YAML config

OPTIONS:
    --auto-approve          Auto-approve all passing candidates
    --fail-fast             Stop on first run failure (default)
    --continue-on-error     Continue even if some runs fail
    --skip-publish          Skip publishing to master trade log
    --help                  Show this help message

EXAMPLES:
    # Run campaign with manual approval
    ./scripts/run-campaign.sh config/campaigns/example_trend_following_15m.yaml

    # Run and auto-approve passing candidates
    ./scripts/run-campaign.sh config/campaigns/example_trend_following_15m.yaml --auto-approve

    # Continue on errors, skip publish
    ./scripts/run-campaign.sh config/campaigns/example.yaml --continue-on-error --skip-publish

WORKFLOW STAGES:
    1. Plan Generation      - Create execution plan with provenance
    2. Batch Execution      - Run all backtests in campaign
    3. Validation           - Run quality gates on candidates
    4. Review               - Generate review report
    5. Approval             - Approve/reject candidates (manual or auto)
    6. Enrichment           - Create rich trades dataset
    7. Publishing           - Publish to master trade log with DVC

OUTPUT:
    - Plan:             data/campaigns/<campaign_id>/plan.json
    - Execution logs:   runs/campaigns/<campaign_id>/execution.log
    - Validation:       data/candidates/<campaign_id>/validation_report.json
    - Review:           data/candidates/<campaign_id>/review_report.md
    - Enriched data:    data/enriched/<campaign_id>/rich_trades.parquet
    - Master log:       data/dvc/processed/training_sets/master_trade_log.parquet

EOF
}

# Parse arguments
if [ $# -eq 0 ] || [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    show_help
    exit 0
fi

CAMPAIGN_CONFIG="$1"
AUTO_APPROVE=false
FAIL_FAST="--fail-fast"
SKIP_PUBLISH=false

shift
while [ $# -gt 0 ]; do
    case "$1" in
        --auto-approve)
            AUTO_APPROVE=true
            ;;
        --fail-fast)
            FAIL_FAST="--fail-fast"
            ;;
        --continue-on-error)
            FAIL_FAST="--continue-on-error"
            ;;
        --skip-publish)
            SKIP_PUBLISH=true
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
    shift
done

# Validate campaign config exists
if [ ! -f "$CAMPAIGN_CONFIG" ]; then
    echo -e "${RED}Error: Campaign config not found: $CAMPAIGN_CONFIG${NC}"
    exit 1
fi

# Extract campaign_id from YAML
CAMPAIGN_ID=$(grep "^campaign_id:" "$CAMPAIGN_CONFIG" | awk '{print $2}' | tr -d '"')

if [ -z "$CAMPAIGN_ID" ]; then
    echo -e "${RED}Error: Could not extract campaign_id from $CAMPAIGN_CONFIG${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Campaign Runner${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Campaign ID:     ${GREEN}$CAMPAIGN_ID${NC}"
echo -e "Config:          $CAMPAIGN_CONFIG"
echo -e "Auto-approve:    $AUTO_APPROVE"
echo -e "Fail mode:       $FAIL_FAST"
echo -e "Skip publish:    $SKIP_PUBLISH"
echo -e "Working dir:     $(pwd)"
echo ""

# Stage 1: Generate Plan
echo -e "${YELLOW}[1/7] Generating execution plan...${NC}"
poetry run tp campaign-plan --config "$CAMPAIGN_CONFIG"
echo -e "${GREEN}✓ Plan generated${NC}"
echo ""

# Stage 2: Execute Campaign
echo -e "${YELLOW}[2/7] Executing campaign runs...${NC}"
poetry run tp campaign-run --campaign-id "$CAMPAIGN_ID" $FAIL_FAST
echo -e "${GREEN}✓ Campaign execution completed${NC}"
echo ""

# Stage 3: Validate Candidates
echo -e "${YELLOW}[3/7] Validating candidates...${NC}"
poetry run tp campaign-validate --campaign-id "$CAMPAIGN_ID"
VALIDATION_REPORT="data/candidates/$CAMPAIGN_ID/validation_report.json"

if [ -f "$VALIDATION_REPORT" ]; then
    PASSED=$(grep -o '"passed": [0-9]*' "$VALIDATION_REPORT" | awk '{print $2}')
    FAILED=$(grep -o '"failed": [0-9]*' "$VALIDATION_REPORT" | awk '{print $2}')
    WARNINGS=$(grep -o '"warnings": [0-9]*' "$VALIDATION_REPORT" | awk '{print $2}')

    echo -e "Validation results:"
    echo -e "  Passed:   ${GREEN}$PASSED${NC}"
    echo -e "  Failed:   ${RED}$FAILED${NC}"
    echo -e "  Warnings: ${YELLOW}$WARNINGS${NC}"
else
    echo -e "${RED}Warning: Validation report not found${NC}"
fi
echo -e "${GREEN}✓ Validation completed${NC}"
echo ""

# Stage 4: Generate Review Report
echo -e "${YELLOW}[4/7] Generating review report...${NC}"
poetry run tp campaign-review --campaign-id "$CAMPAIGN_ID"
REVIEW_REPORT="data/candidates/$CAMPAIGN_ID/review_report.md"

if [ -f "$REVIEW_REPORT" ]; then
    echo -e "${GREEN}✓ Review report generated: $REVIEW_REPORT${NC}"
else
    echo -e "${YELLOW}Warning: Review report not found${NC}"
fi
echo ""

# Stage 5: Approval
echo -e "${YELLOW}[5/7] Approving candidates...${NC}"

if [ "$AUTO_APPROVE" = true ]; then
    echo "Auto-approving all passing candidates..."

    # Parse validation report to get passing run_ids
    if [ -f "$VALIDATION_REPORT" ]; then
        # Extract run_ids with overall_status: passed
        RUN_IDS=$(grep -B 2 '"overall_status": "passed"' "$VALIDATION_REPORT" | grep '"run_id"' | awk -F'"' '{print $4}')

        if [ -z "$RUN_IDS" ]; then
            echo -e "${YELLOW}No passing candidates to approve${NC}"
        else
            for RUN_ID in $RUN_IDS; do
                echo "  Approving: $RUN_ID"
                poetry run tp campaign-approve \
                    --campaign-id "$CAMPAIGN_ID" \
                    --run-id "$RUN_ID" \
                    --notes "Auto-approved by run-campaign.sh"
            done
            echo -e "${GREEN}✓ Auto-approval completed${NC}"
        fi
    else
        echo -e "${RED}Error: Cannot auto-approve without validation report${NC}"
        exit 1
    fi
else
    echo -e "${BLUE}Manual approval required.${NC}"
    echo ""
    echo "Review the report at: $REVIEW_REPORT"
    echo ""
    echo "To approve candidates, run:"
    echo "  poetry run tp campaign-approve --campaign-id $CAMPAIGN_ID --run-id <run_id> --notes \"<notes>\""
    echo ""
    echo -e "${YELLOW}Press Enter to continue after approving, or Ctrl+C to exit${NC}"
    read -r
fi
echo ""

# Stage 6: Enrichment
echo -e "${YELLOW}[6/7] Enriching approved candidates...${NC}"
poetry run tp campaign-enrich --campaign-id "$CAMPAIGN_ID"

ENRICHED_PATH="data/enriched/$CAMPAIGN_ID/rich_trades.parquet"
if [ -f "$ENRICHED_PATH" ]; then
    echo -e "${GREEN}✓ Enrichment completed: $ENRICHED_PATH${NC}"
else
    echo -e "${RED}Error: Enriched dataset not found${NC}"
    exit 1
fi
echo ""

# Stage 7: Publishing
if [ "$SKIP_PUBLISH" = false ]; then
    echo -e "${YELLOW}[7/7] Publishing to master trade log...${NC}"
    poetry run tp campaign-publish --campaign-id "$CAMPAIGN_ID"
    echo -e "${GREEN}✓ Published to master trade log${NC}"
else
    echo -e "${YELLOW}[7/7] Skipping publish (--skip-publish flag)${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Campaign completed successfully!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Campaign ID: $CAMPAIGN_ID"
echo ""
echo "Generated artifacts:"
echo "  - Plan:              data/campaigns/$CAMPAIGN_ID/plan.json"
echo "  - Execution log:     runs/campaigns/$CAMPAIGN_ID/execution.log"
echo "  - Validation:        $VALIDATION_REPORT"
echo "  - Review report:     $REVIEW_REPORT"
echo "  - Enriched data:     $ENRICHED_PATH"

if [ "$SKIP_PUBLISH" = false ]; then
    echo "  - Master trade log:  data/dvc/processed/training_sets/master_trade_log.parquet"
fi

echo ""
echo "Next steps:"

if [ "$SKIP_PUBLISH" = true ]; then
    echo "  - Review enriched dataset and run publish manually if approved"
fi

echo "  - Check audit log:   docs/ai/logs/campaign_audit.md"
echo "  - Review DVC status: dvc status"
echo ""
