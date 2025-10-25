# Campaign Runner Module

Automated backtest orchestration system for systematic ML training data generation.

## Overview

This module implements the complete Campaign Runner workflow from Section 6 of `docs/ai/05_ml_data_curation_guide.md`, providing end-to-end automation from campaign definition to master trade log publication.

## Components

- **models.py**: Pydantic models for campaign configuration, plans, provenance, and results
- **provenance.py**: Provenance metadata capture (git, dependencies, DVC data snapshots)
- **planner.py**: Campaign plan generation from YAML configuration
- **runner.py**: Batch backtest execution engine with failure handling
- **collector.py**: Artifact collection to `data/candidates/<campaign_id>/` structure
- **validator.py**: Complete quality gates (schema, drift monitoring, indicator registry, audit logging)
- **review.py**: Three-state manual review workflow (approved/rejected/needs-rework)
- **enrichment.py**: Intermediate dataset creation with campaign metadata
- **publisher.py**: Master trade log publishing with automated DVC tracking

## Key Features

### Full Provenance Tracking
Every campaign plan captures:
- Git commit hash
- poetry.lock SHA256
- Python version
- Platform
- DVC version
- **Data snapshot ID** (DVC data version hash)

### Complete Quality Gates
- Schema validation
- Data quality checks
- Minimum trades threshold
- Duplicate detection
- Max drawdown limit
- **Indicator registry validation**
- **Drift monitoring (KS-statistic)**
- **Audit log updates**

### Three-State Review Workflow
- `approved`: Ready for enrichment and publishing
- `rejected`: Not suitable for ML training
- `needs-rework`: Requires parameter adjustment

Campaign-level decision tracking in `data/candidates/<campaign_id>/decision.yaml`.

### Enrichment Stage
Creates intermediate `data/enriched/<campaign_id>/rich_trades.parquet` with:
- Campaign ID
- Run ID
- Strategy archetype
- Execution timeframe

### Automated DVC Tracking
Publishing automatically runs:
```bash
dvc add data/dvc/processed/training_sets/master_trade_log.parquet
dvc push
```

No manual DVC commands required.

## Usage

See [docs/ai/06_campaign_runner_guide.md](../../../../docs/ai/06_campaign_runner_guide.md) for complete usage guide and CLI reference.

### Quick Start

```python
from trading_platform.ai.campaigns import (
    CampaignConfig,
    generate_campaign_plan,
    execute_campaign_runs,
    validate_campaign_candidates,
    approve_candidate,
    enrich_campaign_dataset,
    publish_campaign_dataset,
)

# 1. Create campaign config
config = CampaignConfig.model_validate({
    "campaign_id": "my_campaign",
    "strategy_path": "config/strategy/ema_crossover.yaml",
    "execution_timeframe": "15m",
    "strategy_archetype": "trend_following",
    "run_matrix": [
        {
            "instrument": "EURUSD",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        }
    ],
})

# 2. Generate plan with provenance
plan = generate_campaign_plan(config, output_dir)

# 3. Execute runs
results = execute_campaign_runs(plan, runs_dir, campaign_dir)

# 4. Validate candidates
report = validate_campaign_candidates("my_campaign")

# 5. Approve candidates
approve_candidate("my_campaign", "run_001", notes="Good metrics")

# 6. Enrich approved candidates
enrich_result = enrich_campaign_dataset("my_campaign")

# 7. Publish to master trade log
publish_result = publish_campaign_dataset("my_campaign")
```

## CLI Commands

```bash
# Generate plan
tp campaign-plan --config config/campaigns/my_campaign.yaml

# Execute runs
tp campaign-run --campaign-id my_campaign

# Validate candidates
tp campaign-validate --campaign-id my_campaign

# Review and approve
tp campaign-review --campaign-id my_campaign
tp campaign-approve --campaign-id my_campaign --run-id run_001 --notes "notes"
tp campaign-reject --campaign-id my_campaign --run-id run_002 --reason "reason"
tp campaign-needs-rework --campaign-id my_campaign --run-id run_003 --reason "reason" --suggestions "suggestions"

# Enrich and publish
tp campaign-enrich --campaign-id my_campaign
tp campaign-publish --campaign-id my_campaign
```

## Testing

All modules have 100% test coverage:

```bash
poetry run pytest tests/ai/campaigns/ -v
```

## Architecture

```
Campaign YAML → Plan (w/ provenance) → Execution → Validation → Review → Enrichment → Publishing
                                                       ↓
                                            Quality Gates:
                                            - Schema
                                            - Data quality
                                            - Min trades
                                            - Duplicates
                                            - Max drawdown
                                            - Indicator registry
                                            - Drift monitoring
                                            - Audit logging
```

## Documentation

- [Campaign Runner Guide](../../../../docs/ai/06_campaign_runner_guide.md) - Complete usage guide
- [ML Data Curation Guide](../../../../docs/ai/05_ml_data_curation_guide.md) - Section 6 specification
- Example campaign: [config/campaigns/example_trend_following_15m.yaml](../../../../config/campaigns/example_trend_following_15m.yaml)
