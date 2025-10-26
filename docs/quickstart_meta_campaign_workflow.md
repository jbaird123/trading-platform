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

This generates: 2 instruments × 2 timeframes × 2 profiles = 8 total runs across 4 campaign config files

### Step 3: Generate Campaign Configs

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

✓ Generated 4 campaign config file(s)
✓ Output directory: config/campaigns/generated/

Next steps:
  1. Review generated configs in config/campaigns/generated
  2. Create campaign plan: tp campaign-plan --config <config_file>
  3. Execute campaign: tp campaign-run --campaign-id <campaign_id>
  4. Review results: tp campaign-review --campaign-id <campaign_id>
```

**What was generated:**

The meta-campaign generator creates **one campaign config file per (profile, timeframe) combination**. Each file contains a `run_matrix` with all instrument/parameter variations for that combination.

In this example:
- `my_first_campaign_trend_with_risk_1H.yaml` - 2 runs (2 instruments)
- `my_first_campaign_trend_with_risk_4H.yaml` - 2 runs (2 instruments)
- `my_first_campaign_baseline_no_risk_1H.yaml` - 2 runs (2 instruments)
- `my_first_campaign_baseline_no_risk_4H.yaml` - 2 runs (2 instruments)
- **Total: 4 campaign files representing 8 backtest runs**

### Step 4: Create Campaign Plans

For each generated campaign config file, create an execution plan:

```bash
# Create plan for each campaign
for config in config/campaigns/generated/*.yaml; do
  tp campaign-plan --config "$config"
done
```

This creates a `plan.json` file in `data/campaigns/<campaign_id>/` for each campaign.

**Expected Output:**
```
Campaign plan created: data/campaigns/my_first_campaign_trend_with_risk_1H/plan.json
Campaign plan created: data/campaigns/my_first_campaign_trend_with_risk_4H/plan.json
...
```

### Step 5: Execute Campaigns

Now execute all campaigns using their campaign IDs:

```bash
# Run each campaign by ID
tp campaign-run --campaign-id my_first_campaign_trend_with_risk_1H
tp campaign-run --campaign-id my_first_campaign_trend_with_risk_4H
tp campaign-run --campaign-id my_first_campaign_baseline_no_risk_1H
tp campaign-run --campaign-id my_first_campaign_baseline_no_risk_4H
```

**Or run all at once:**
```bash
# Extract campaign IDs from generated configs and run them
for config in config/campaigns/generated/*.yaml; do
  campaign_id=$(grep "^campaign_id:" "$config" | cut -d' ' -f2)
  tp campaign-run --campaign-id "$campaign_id"
done
```

**Expected Output:**
```
Execution complete: 2/2 successful
```

### Step 6: Publish Results

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

### Campaign Grouping Strategy

The meta-campaign generator creates **one campaign config per (profile, timeframe) combination**. This grouping strategy balances:

- **Efficiency**: Each campaign shares the same execution timeframe, so data loading is consistent
- **Organization**: Results are grouped by strategy profile and timeframe for easier analysis
- **Parallelization**: Different campaigns can be run in parallel if needed

**Example:** With 2 profiles × 6 timeframes = 12 campaign files, each campaign file contains multiple runs (different instruments/parameters on the same timeframe).

### Data Loading Performance

**Important Note**: The campaign runner spawns a separate subprocess for each backtest run, which means:
- Price data is loaded from CSV **once per run** (not cached across runs)
- For 30 runs testing EUR_USD, the EUR_USD CSV is loaded 30 times
- Each CSV load takes ~0.5 seconds
- Total overhead: ~15-30 seconds across all runs

This is acceptable for typical campaign sizes but something to be aware of for very large campaigns.

### Scaling Recommendations

Start small and scale up:

1. **Pilot Campaign** (1-2 hours):
   - 1-2 years of data
   - 1-2 instruments
   - 2 timeframes
   - 2-3 parameter sets
   - ~8-12 runs across 4-6 campaign files

2. **Full Campaign** (hours to days):
   - 5+ years of data
   - 5-10 instruments
   - 6 timeframes
   - 10+ parameter sets
   - 300+ runs across 60+ campaign files

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
# Phase 0: Validate data (optional - only needed for raw price data validation)
tp validate-data --data-dir data/historical/

# Phase 1: Generate campaign configs from meta-campaign
tp meta-campaign-plan \
  --config config/meta_campaigns/trend_following_data_gen.yaml \
  --output-dir config/campaigns/generated/

# Phase 1: Create campaign plans for each generated config
for config in config/campaigns/generated/*.yaml; do
  tp campaign-plan --config "$config"
done

# Phase 1: Execute all campaigns
for config in config/campaigns/generated/*.yaml; do
  campaign_id=$(grep "^campaign_id:" "$config" | cut -d' ' -f2)
  tp campaign-run --campaign-id "$campaign_id"
done

# Phase 1: Publish results to master trade log
# Note: Publish by meta-campaign ID, not individual campaign IDs
tp campaign-publish --campaign-id trend_following_model_generation

# Phase 2: Curate and train models
tp ai-curate-data \
  --source-dir runs/trend_following_model_generation/ \
  --output-file runs/enriched_data.parquet

tp train-profitability-models --enriched-data runs/enriched_data.parquet
tp train-diagnostic-models --enriched-data runs/enriched_data.parquet

# Phase 5: Walk-forward validation
tp walk-forward-validate \
  --strategy config/strategy/final.yaml \
  --data runs/trend_following_model_generation/master_trade_log.parquet

# Pre-deployment checklist
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
