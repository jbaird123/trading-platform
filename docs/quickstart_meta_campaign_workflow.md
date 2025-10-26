# Quickstart: Meta-Campaign Workflow

This guide will walk you through the complete meta-campaign workflow from data validation through model deployment.

## Overview

The meta-campaign system automates the 6-phase ML research lifecycle:

0. **Phase 0**: Data Validation
1. **Phase 1**: Data Generation (campaign execution)
2. **Phase 2**: Model Training
3. **Phase 3**: Candidate Selection
4. **Phase 4**: Hyperparameter Optimization
5. **Phase 5**: Walk-Forward Validation
6. **Pre-Deployment**: Governance Checklist

## Prerequisites

- Trading platform installed with `poetry install`
- Historical price data in parquet format
- Git repository initialized

## Phase 0: Data Validation

Validate your historical data for gaps and consistency:

```bash
tp validate-data --data-dir data/historical/
```

**Expected Output:**
```
Validating data in: data/historical/
Instruments: EUR_USD, GBP_USD

Total files checked: 2
Files with issues: 0

No issues found!
```

If issues are found, fix data gaps before proceeding.

## Phase 1: Campaign Generation

### Step 1: Create Master Strategy Configs

Create versioned strategy and REM configs in `config/master_data_generation/`:

```bash
mkdir -p config/master_data_generation/strategies
mkdir -p config/master_data_generation/rem
```

Example strategy: `config/master_data_generation/strategies/ema_crossover_v1.yaml`

### Step 2: Create Meta-Campaign File

Create `config/meta_campaigns/my_first_campaign.yaml`:

```yaml
meta_campaign_id: my_first_campaign
description: "My first meta-campaign for trend-following model training"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2023-12-31" }
  instruments:
    - EUR_USD
    - GBP_USD
  execution_timeframes:
    - 1H
    - 4H

strategy_profiles:
  - name: trend_with_risk
    strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
    rem_path: config/master_data_generation/rem/chandelier_stop_v1.yaml
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10, slow_length: 20 }
        rem_params: { atr_length: 22, atr_multiplier: 2.0 }

  - name: baseline_no_risk
    strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 9, slow_length: 21 }
```

This generates: 2 instruments × 2 timeframes × 2 profiles = 8 campaigns

### Step 3: Generate Campaigns

```bash
tp meta-campaign-plan \
  --config config/meta_campaigns/my_first_campaign.yaml \
  --output-dir config/campaigns/generated/
```

**Expected Output:**
```
Generating campaigns from: config/meta_campaigns/my_first_campaign.yaml
Meta-campaign ID: my_first_campaign
Description: My first meta-campaign for trend-following model training

Calculated: 8 campaign configurations

Generated 8 campaign configurations
Output directory: config/campaigns/generated/

Next steps:
  1. Review generated configs in config/campaigns/generated/
  2. Run campaigns with: tp campaign-run <campaign_file>
  3. Review results with: tp campaign-review
```

### Step 4: Execute Campaigns

```bash
# Run each campaign (or use campaign-run for batch execution)
for config in config/campaigns/generated/*.yaml; do
  tp run-backtest --config "$config"
done
```

### Step 5: Publish Results

After running all campaigns, publish the results to the master trade log:

```bash
tp campaign-publish --campaign-id my_first_campaign
```

This creates `runs/my_first_campaign/master_trade_log.parquet` with all trades.

## Phase 2: Model Training

Train profitability and diagnostic models:

```bash
# Curate ML training data
tp ai-curate-data \
  --source-dir runs/my_first_campaign/ \
  --output-file runs/my_first_campaign/enriched_trade_data.parquet

# Train profitability models
tp train-profitability-models \
  --enriched-data runs/my_first_campaign/enriched_trade_data.parquet

# Train diagnostic models
tp train-diagnostic-models \
  --enriched-data runs/my_first_campaign/enriched_trade_data.parquet
```

## Phase 5: Walk-Forward Validation

Test model consistency across time periods:

```bash
tp walk-forward-validate \
  --strategy config/strategy/candidate_final.yaml \
  --data runs/my_first_campaign/master_trade_log.parquet \
  --periods year
```

**Expected Output:**
```
================================================================================
WALK-FORWARD VALIDATION RESULTS
================================================================================
Period                         Sharpe     Max DD     Return     Win Rate
--------------------------------------------------------------------------------
2021-01 to 2021-12            1.50       -15.00%    25.00%     55.00%
2022-01 to 2022-12            1.60       -12.00%    28.00%     57.00%
--------------------------------------------------------------------------------

Consistency Check (Sharpe Ratio): PASS
✓ Performance is consistent across periods
```

## Pre-Deployment: Governance Checklist

Before deploying to production, validate all governance criteria:

```bash
tp pre-deployment-checklist \
  --model-metrics runs/model_metrics.json \
  --walk-forward-results runs/walk_forward_results.json \
  --phase4-results runs/phase4_optimization.json \
  --strategy-config config/strategy/candidate_final.yaml
```

**Expected Output:**
```
================================================================================
PRE-DEPLOYMENT CHECKLIST
================================================================================

☑ [PASS] Model performance meets minimum baselines
         R² >= 0.2, F1 >= 0.6

☑ [PASS] Walk-forward validation shows consistent positive performance
         All test periods have positive Sharpe ratio

☑ [PASS] Predictive filter threshold is justified
         Filter threshold 0.5 shows 50.0% improvement in Sharpe ratio

☑ [PASS] Git commit hash recorded for reproducibility
         abc123def

================================================================================
✓ READY FOR DEPLOYMENT

All pre-deployment criteria have been met.
```

## Managing Computational Cost

Start small and scale up:

1. **Pilot Campaign** (1-2 hours):
   - 1-2 years of data
   - 2-3 instruments
   - 2 timeframes
   - 2-3 parameter sets
   - ~24 campaigns

2. **Full Campaign** (days):
   - 5+ years of data
   - 5-10 instruments
   - 6 timeframes
   - 10+ parameter sets
   - 1000+ campaigns

## Troubleshooting

### Campaign Generation Issues

**Problem**: `Error: Config file not found`
**Solution**: Check that the meta-campaign YAML path is correct

**Problem**: `Error: Strategy file not found`
**Solution**: Ensure `strategy_path` and `rem_path` exist in meta-campaign config

### Data Validation Issues

**Problem**: Large gaps in time series
**Solution**: Download missing data or adjust campaign date ranges to avoid gaps

### Walk-Forward Validation Issues

**Problem**: "Need at least 2 periods"
**Solution**: Use longer data range or change `--periods` to quarterly/monthly

## Next Steps

- See [Meta-Campaign System Guide](user_guides/meta_campaign_system.md) for detailed documentation
- See [Research Workflow Plan](working/campaign_config_refactor_plan.md) for full lifecycle details
- Review example configs in `config/meta_campaigns/`

## Full Example Command Sequence

```bash
# Phase 0: Validate data
tp validate-data --data-dir data/historical/

# Phase 1: Generate and run campaigns
tp meta-campaign-plan \
  --config config/meta_campaigns/trend_following_data_gen.yaml

# (Run all generated campaigns...)

tp campaign-publish --campaign-id trend_following_model_generation

# Phase 2: Train models
tp ai-curate-data \
  --source-dir runs/trend_following_model_generation/ \
  --output-file runs/enriched_data.parquet

tp train-profitability-models --enriched-data runs/enriched_data.parquet
tp train-diagnostic-models --enriched-data runs/enriched_data.parquet

# Phase 5: Validate
tp walk-forward-validate \
  --strategy config/strategy/final.yaml \
  --data runs/trend_following_model_generation/master_trade_log.parquet

# Pre-deployment
tp pre-deployment-checklist \
  --model-metrics runs/model_metrics.json \
  --walk-forward-results runs/walk_forward_results.json \
  --phase4-results runs/phase4_optimization.json \
  --strategy-config config/strategy/final.yaml
```

## Reproducibility

All generated campaigns include:
- Original meta-campaign ID
- Profile name
- Complete parameter sets
- Git commit hash (when available)

This ensures you can always trace back from deployed models to the exact configuration that generated the training data.
