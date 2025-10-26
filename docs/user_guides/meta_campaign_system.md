# Meta-Campaign System User Guide

## Overview

The meta-campaign system automates the creation of campaign configurations for training ML models. Instead of manually creating dozens of individual campaign files, you define a single high-level `meta-campaign.yaml` that specifies the full parameter grid.

## Two-Stage Workflow

1. **Stage 1: Generation (`tp meta-campaign-plan`)**: Reads a meta-campaign YAML file, calculates the cartesian product of all parameters, and generates individual campaign config files.

2. **Stage 2: Execution & Review (Manual)**: Use existing CLI commands (`tp campaign-run`, `tp campaign-review`) to run and verify campaigns before publishing.

## Directory Structure

```
config/
├── master_data_generation/      # Stable, versioned configs for reproducibility
│   ├── strategies/
│   │   └── ema_crossover_v1.yaml
│   └── rem/
│       └── chandelier_stop_v1.yaml
├── meta_campaigns/               # High-level meta-campaign definitions
│   └── trend_following_data_gen.yaml
└── campaigns/
    └── generated/                # Auto-generated campaign configs
```

## Meta-Campaign Configuration Format

```yaml
meta_campaign_id: trend_following_model_generation
description: "Generates all campaign configs needed to train trend-following models"

run_grid:
  date_ranges:
    - { start: "2018-01-01", end: "2023-12-31" }
  instruments:
    - EUR_USD
    - GBP_USD
  execution_timeframes:
    - 1min
    - 5min
    - 15min
    - 1H
    - 4H
    - 1D

strategy_profiles:
  # Profile for data WITH defined risk
  - name: trend_with_risk
    strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
    rem_path: config/master_data_generation/rem/chandelier_stop_v1.yaml
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10, slow_length: 20 }
        rem_params: { atr_length: 22, atr_multiplier: 2.0 }
      - strategy_params: { fast_length: 10, slow_length: 20 }
        rem_params: { atr_length: 22, atr_multiplier: 3.0 }

  # Profile for data WITHOUT defined risk
  - name: baseline_no_risk
    strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 9, slow_length: 21 }
      - strategy_params: { fast_length: 15, slow_length: 45 }
```

## Usage Instructions

### 1. Create a Meta-Campaign File

Create `config/meta_campaigns/my_campaign.yaml` following the format above.

### 2. Generate Campaign Configs

```bash
tp meta-campaign-plan --config config/meta_campaigns/my_campaign.yaml
```

This generates individual campaign files in `config/campaigns/generated/`.

**Optional arguments:**
- `--output-dir DIR`: Custom output directory (default: `config/campaigns/generated/`)
- `--force`: Overwrite existing files in output directory

### 3. Review Generated Configs

```bash
ls config/campaigns/generated/
```

Each file is named: `{meta_campaign_id}_{profile_name}_{instrument}_{timeframe}_{index:02d}.yaml`

### 4. Execute Campaigns

```bash
tp campaign-run --campaign-id <campaign_file>
```

### 5. Review Results

```bash
tp campaign-review --campaign-id <campaign_id>
```

## Strategy Profiles

### "With Risk" Profile

Use when you want to train models on data that includes risk/exit management parameters (stops, take-profits). The `rem_path` is specified, and each param_set includes `rem_params`.

### "No Risk" Profile

Use when you want to train models on "no stop" strategies to analyze entry signal quality. Set `rem_path: null` and omit `rem_params`.

## Managing Computational Cost

**Start small!** The cartesian product can explode quickly:

- 1 date_range × 2 instruments × 6 timeframes × 5 param_sets = **60 campaigns**

Recommendations:
- Start with 1-2 years of data
- Use 2-3 instruments
- Test with 2 timeframes first (`15min`, `1H`)
- Gradually expand the grid

## Reproducibility

The `config/master_data_generation/` directory ensures reproducibility by:
1. **Versioning**: Files are named with versions (e.g., `ema_crossover_v1.yaml`)
2. **Stability**: These files are never modified, only copied with new versions
3. **Independence**: Separate from `config/strategy/` which may change frequently

## Troubleshooting

### Error: "Output directory contains existing files"

**Solution**: Use `--force` flag to overwrite, or manually clear the directory.

### Error: "Config file not found"

**Solution**: Verify the path to your meta-campaign YAML file exists.

### Error: "Invalid execution_timeframe"

**Solution**: Ensure all timeframes are in the valid set: `1min`, `5min`, `15min`, `1H`, `4H`, `1D`.

### No campaigns generated

**Solution**: Check that:
1. Your `run_grid` has at least one entry in each list
2. Each `strategy_profile` has at least one `param_grid` entry

## Example Workflow

```bash
# 1. Create meta-campaign config
vi config/meta_campaigns/my_research.yaml

# 2. Generate campaigns
tp meta-campaign-plan --config config/meta_campaigns/my_research.yaml

# 3. Review what was generated
ls -l config/campaigns/generated/

# 4. Run one campaign as a test
tp campaign-run --campaign-id config/campaigns/generated/my_research_baseline_no_risk_EUR_USD_15min_00.yaml

# 5. If successful, run all campaigns (loop or parallel)
for f in config/campaigns/generated/my_research_*.yaml; do
    tp campaign-run --campaign-id "$f"
done

# 6. Review and publish results
tp campaign-review --campaign-id my_research
tp campaign-publish --campaign-id my_research
```

## Best Practices

1. **Version Your Configs**: Always use versioned files in `master_data_generation/`
2. **Document Your Grid**: Add descriptive `description` fields to meta-campaigns
3. **Test Small First**: Generate 2-4 campaigns to verify your setup
4. **Use Git**: Commit meta-campaign files to track your research iterations
5. **Record Metadata**: The system automatically includes `git_commit` hash in each campaign
