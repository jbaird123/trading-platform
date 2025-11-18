# Campaign Runner Guide

## 1. Overview

The Campaign Runner is an automated backtest orchestration system for systematic ML training data generation. It implements the complete workflow described in Section 6 of [05_ml_data_curation_guide.md](05_ml_data_curation_guide.md), providing end-to-end automation from campaign definition to master trade log publication.

**Key Features:**
- Declarative YAML configuration with parameter matrices
- Full provenance tracking (git commit, dependencies, DVC data snapshots)
- Automated batch execution with comprehensive failure handling
- Complete quality gates (schema, data quality, drift monitoring, indicator registry)
- Three-state review workflow (approved, rejected, needs-rework)
- Enrichment stage creating intermediate rich trades dataset
- Publishing to master trade log with automated DVC tracking and full audit trail

## 2. Quick Start

### 5-Minute Example

```bash
# 1. Create campaign YAML
cat > config/campaigns/my_first_campaign.yaml <<EOF
campaign_id: my_first_campaign
strategy_path: config/strategy/ema_crossover.yaml
execution_timeframe: 15m
strategy_archetype: trend_following

run_matrix:
  - instrument: EURUSD
    start_date: "2023-01-01"
    end_date: "2023-03-31"
EOF

# 2. Generate execution plan
poetry run tp campaign-plan --config config/campaigns/my_first_campaign.yaml

# 3. Execute campaign
poetry run tp campaign-run --campaign-id my_first_campaign

# 4. Validate candidates
poetry run tp campaign-validate --campaign-id my_first_campaign

# 5. Review and approve
poetry run tp campaign-review --campaign-id my_first_campaign
poetry run tp campaign-approve --campaign-id my_first_campaign --run-id run_001 --notes "Good metrics"

# 6. Enrich approved candidates
poetry run tp campaign-enrich --campaign-id my_first_campaign

# 7. Publish to master trade log
poetry run tp campaign-publish --campaign-id my_first_campaign
```

## 3. Campaign YAML Anatomy

### Required Fields

```yaml
campaign_id: unique_identifier        # Used for folder naming and tracking
strategy_path: path/to/strategy.yaml  # Base strategy configuration
execution_timeframe: 15m              # Base timeframe for execution
strategy_archetype: trend_following   # REQUIRED for model selection
```

### Run Matrix

The `run_matrix` defines parameter sweep combinations:

```yaml
run_matrix:
  - instrument: EURUSD
    start_date: "2023-01-01"
    end_date: "2023-12-31"
    param_overrides:
      fast_length: 10
      slow_length: 20

  - instrument: GBPUSD
    start_date: "2023-01-01"
    end_date: "2023-12-31"
    param_overrides:
      fast_length: 12
      slow_length: 25
```

Each entry generates one backtest run. The runner creates unique `run_id` values automatically.

### Contextual Features

Multi-timeframe features for ML model context:

```yaml
contextual_features:
  - name: 1h_rsi
    type: RSI
    params:
      length: 14
    timeframe: 1h  # Higher timeframe context

  - name: 1d_atr
    type: ATR
    params:
      length: 14
    timeframe: 1D
```

Features without `timeframe` use the base `execution_timeframe`.

### Optional Fields

```yaml
rem_path: config/rem/my_rem.yaml      # Risk event management config
rmm_path: config/rmm/my_rmm.yaml      # Risk/money management config
description: "Campaign description"   # Human-readable notes
```

## 4. Workflow

### Complete End-to-End Flow

1. **Plan Generation** (`campaign-plan`)
   - Loads campaign YAML
   - Captures full provenance:
     - Git commit hash
     - poetry.lock SHA256
     - Python version
     - Platform
     - DVC version
     - **Data snapshot ID** (DVC data version hash)
   - Expands run matrix into individual RunConfig files
   - Saves `plan.json` with provenance metadata

2. **Batch Execution** (`campaign-run`)
   - Reads plan.json
   - Executes each run via `tp run-backtest`
   - Tracks progress in `execution.log`
   - On failure:
     - Creates `failure_report.json` with stack trace, config snapshot, environment info
     - Stops if `--fail-fast` (default)
     - Continues if `--continue-on-error`
   - Generates `campaign_complete.yaml` summary

3. **Artifact Collection** (automatic during run)
   - Copies brief.json to `data/candidates/<campaign_id>/<run_id>/`
   - Extracts metadata (PnL, Sharpe, win rate, strategy_archetype, execution_timeframe)
   - Creates `index.json` for candidate catalog

4. **Validation** (`campaign-validate`)
   - Runs complete quality gates:
     - **Schema validation**: Required fields present
     - **Data quality**: No NaNs or data issues
     - **Min trades**: At least 5 trades
     - **Duplicate detection**: No duplicate trade IDs
     - **Max drawdown**: Not exceeding -50%
     - **Indicator registry**: All features registered in `indicators_registry.py`
     - **Drift monitoring**: KS-statistic check vs baseline (threshold 0.15)
   - Saves `validation_report.json`
   - **Updates audit log** (`docs/ai/logs/campaign_audit.md`)

5. **Review & Approval** (`campaign-review`, `campaign-approve`)
   - Generates review report with top/bottom performers
   - Curation Lead makes decision for each run:
     - `approved`: Ready for enrichment
     - `rejected`: Not suitable
     - `needs-rework`: Requires parameter adjustment
   - Decisions stored in **campaign-level** `decision.yaml`

6. **Enrichment** (`campaign-enrich`)
   - Reads only approved candidates
   - Calls `tp ai-curate-data` to create rich trades dataset
   - Adds campaign metadata columns:
     - `campaign_id`
     - `run_id`
     - `strategy_archetype`
     - `execution_timeframe`
   - Saves to `data/enriched/<campaign_id>/rich_trades.parquet`

7. **Publishing** (`campaign-publish`)
   - Reads from enriched dataset
   - Appends to `data/dvc/processed/training_sets/master_trade_log.parquet`
   - Calculates SHA256 checksum
   - **Automated DVC tracking**:
     - Runs `dvc add master_trade_log.parquet`
     - Runs `dvc push`
   - Updates `docs/ai/data_curation_history.md`
   - Updates audit log

## 5. Quality Gates

All validation checks (task 56 requirements):

| Check | Purpose | Failure Condition |
|-------|---------|-------------------|
| **schema_validation** | Required fields present | Missing meta, trades, or backtest_metrics |
| **data_quality** | No data corruption | has_nans=true or high duplicate_bars_count |
| **min_trades** | Sufficient sample size | Less than 5 trades |
| **duplicate_detection** | No duplicate trade IDs | Duplicate trade_id values |
| **max_drawdown** | Risk bounds | Drawdown < -50% |
| **indicator_registry** | All features registered | Unregistered indicators in contextual_features |
| **drift_monitoring** | Distribution stability | KS-statistic > 0.15 vs baseline |

The **drift monitoring** check computes the Kolmogorov-Smirnov statistic between candidate `r_multiple` distribution and the baseline master trade log. If KS > 0.15, it triggers a **warning** (not failure) alerting to potential distribution shift.

The **indicator registry** check ensures all indicators in `contextual_features` exist in `src/trading_platform/strategy/indicators_registry.py`. This prevents undefined features from entering the ML pipeline.

## 6. Review & Approval

### Three Decision States

The review workflow supports three states stored in a **campaign-level** `decision.yaml`:

```yaml
campaign_id: my_campaign
reviewed_by: curator_name
reviewed_at: 2025-10-24T12:00:00Z

decisions:
  - run_id: run_001
    status: approved
    notes: "Excellent Sharpe ratio"

  - run_id: run_002
    status: rejected
    reason: "Excessive drawdown"

  - run_id: run_003
    status: needs-rework
    reason: "Winrate too low"
    suggestions: "Widen stop loss to 30 pips"
```

### Decision Commands

```bash
# Approve for publication
tp campaign-approve --campaign-id ID --run-id RUN --notes "text"

# Reject permanently
tp campaign-reject --campaign-id ID --run-id RUN --reason "text"

# Mark for rework
tp campaign-needs-rework --campaign-id ID --run-id RUN --reason "text" --suggestions "text"
```

### Filtering

Only **approved** candidates flow into enrichment and publishing. The `get_approved_candidates()` function reads the campaign-level decision.yaml and filters by `status: approved`.

## 7. Enrichment Stage

The enrichment stage bridges validation and publishing:

### Process

1. **Filter approved candidates**: Reads `decision.yaml` to get approved run_ids
2. **Invoke ai-curate-data**: Calls existing data curation tool
   ```bash
   poetry run tp ai-curate-data --source-dir approved_briefs/ --output-file rich_trades.parquet
   ```
3. **Add metadata columns**: Enriches with campaign context
   - `campaign_id`: Campaign identifier
   - `run_id`: Backtest run ID
   - `strategy_archetype`: From brief.meta.strategy_archetype
   - `execution_timeframe`: From brief.meta.execution_timeframe
4. **Save intermediate dataset**: `data/enriched/<campaign_id>/rich_trades.parquet`

### Why Enrichment?

- **Separation of concerns**: Approved != published
- **Metadata enrichment**: Adds campaign tracking fields
- **Audit trail**: Intermediate checkpoint before master log
- **Reversibility**: Can re-enrich without re-running backtests

## 8. Publishing

### Publishing Flow

```bash
tp campaign-publish --campaign-id my_campaign
```

1. Reads `data/enriched/<campaign_id>/rich_trades.parquet`
2. Appends to `data/dvc/processed/training_sets/master_trade_log.parquet`
3. Computes SHA256 checksum
4. **Automated DVC tracking** (no manual steps required):
   ```bash
   dvc add data/dvc/processed/training_sets/master_trade_log.parquet
   dvc push
   ```
5. Updates curation history:
   ```markdown
   ## 2025-10-24T12:00:00Z

   - **Campaign ID**: my_campaign
   - **Trades Added**: 150
   - **Checksum**: abc123...
   - **Actor**: campaign-runner
   ```
6. Updates audit log with publish action

### Audit Trail

All publishing actions are logged in `docs/ai/logs/campaign_audit.md`:

```markdown
## 2025-10-24T12:05:00Z

- **Action**: Publish
- **Campaign ID**: my_campaign
- **Trades Published**: 150
- **Master Log Path**: data/dvc/processed/training_sets/master_trade_log.parquet
- **Checksum**: abc123def456...
```

## 9. Folder Structure

Prescribed directory layout (per guide Section 5.2):

```
data/
├── candidates/
│   └── <campaign_id>/
│       ├── decision.yaml           # CAMPAIGN-LEVEL decisions
│       ├── index.json              # Candidate catalog
│       ├── validation_report.json  # Quality gate results
│       ├── review_report.md        # Top/bottom performers
│       ├── run_001/
│       │   ├── brief.json
│       │   └── metadata.json
│       └── run_002/
│           └── ...
├── enriched/
│   └── <campaign_id>/
│       └── rich_trades.parquet     # Intermediate enriched dataset
└── dvc/
    └── processed/
        └── training_sets/
            └── master_trade_log.parquet  # Final published dataset

docs/
└── ai/
    ├── data_curation_history.md    # Publishing log
    └── logs/
        └── campaign_audit.md       # All campaign actions

runs/
└── campaigns/
    └── <campaign_id>/
        ├── execution.log
        ├── campaign_complete.yaml
        ├── failures/
        │   └── <run_id>_failure_report.json
        └── <run_id>/
            └── brief.json
```

## 10. CLI Reference

### campaign-plan

Generate execution plan from campaign YAML.

```bash
tp campaign-plan --config config/campaigns/my_campaign.yaml
```

**Output:**
- `data/campaigns/<campaign_id>/plan.json`

### campaign-run

Execute all runs in a campaign plan.

```bash
tp campaign-run --campaign-id my_campaign [--fail-fast | --continue-on-error]
```

**Options:**
- `--fail-fast` (default): Stop on first failure
- `--continue-on-error`: Run all even if some fail

**Output:**
- `runs/campaigns/<campaign_id>/execution.log`
- `runs/campaigns/<campaign_id>/campaign_complete.yaml`
- `runs/campaigns/<campaign_id>/failures/<run_id>_failure_report.json` (on failure)

### campaign-validate

Run quality gates on all candidates.

```bash
tp campaign-validate --campaign-id my_campaign
```

**Output:**
- `data/candidates/<campaign_id>/validation_report.json`
- Updates `docs/ai/logs/campaign_audit.md`

### campaign-review

Generate review report for manual review.

```bash
tp campaign-review --campaign-id my_campaign
```

**Output:**
- `data/candidates/<campaign_id>/review_report.md`

### campaign-approve

Approve a candidate for publication.

```bash
tp campaign-approve --campaign-id ID --run-id RUN --notes "notes"
```

**Updates:**
- `data/candidates/<campaign_id>/decision.yaml`

### campaign-reject

Reject a candidate permanently.

```bash
tp campaign-reject --campaign-id ID --run-id RUN --reason "reason"
```

**Updates:**
- `data/candidates/<campaign_id>/decision.yaml`

### campaign-needs-rework

Mark candidate for rework.

```bash
tp campaign-needs-rework --campaign-id ID --run-id RUN --reason "reason" --suggestions "suggestions"
```

**Updates:**
- `data/candidates/<campaign_id>/decision.yaml`

### campaign-enrich

Create enriched dataset from approved candidates.

```bash
tp campaign-enrich --campaign-id my_campaign
```

**Output:**
- `data/enriched/<campaign_id>/rich_trades.parquet`

### campaign-publish

Publish enriched dataset to master trade log.

```bash
tp campaign-publish --campaign-id my_campaign
```

**Output:**
- Updates `data/dvc/processed/training_sets/master_trade_log.parquet`
- Updates `docs/ai/data_curation_history.md`
- Updates `docs/ai/logs/campaign_audit.md`
- Runs `dvc add` and `dvc push` automatically

## 11. Provenance & Reproducibility

Every campaign plan captures full provenance metadata:

```json
{
  "provenance": {
    "git_commit": "abc1234",
    "poetry_lock_sha256": "deadbeef...",
    "python_version": "3.12.0",
    "platform": "darwin",
    "dvc_version": "3.63.0",
    "data_snapshot_id": "a1b2c3d4",  // DVC data version hash
    "captured_at": "2025-10-24T12:00:00Z"
  }
}
```

### Data Snapshot ID

The `data_snapshot_id` captures the exact state of DVC-tracked data at plan generation time. It's computed as a hash of `dvc status data/dvc/raw/ --json`.

This ensures:
- **Exact reproducibility**: Same data version = same results
- **Audit trail**: Know which data version produced which results
- **Debugging**: Trace issues to specific data snapshots

## 12. Troubleshooting

### Common Issues

**Issue**: Validation fails with "unregistered indicators"

**Solution**: Add missing indicators to `src/trading_platform/strategy/indicators_registry.py`

---

**Issue**: Drift warning (KS > 0.15)

**Solution**: This is a warning, not a failure. Review candidate distribution:
- Is the strategy fundamentally different?
- Is the market regime different?
- Consider creating a new campaign for different strategy types

---

**Issue**: Enrichment fails with "no approved candidates"

**Solution**: Use `campaign-approve` to approve at least one candidate first

---

**Issue**: Publishing fails with "enriched dataset not found"

**Solution**: Run `campaign-enrich` before `campaign-publish`

---

**Issue**: DVC push fails

**Solution**:
- Verify DVC remote is configured: `dvc remote list`
- Check S3 credentials: `aws s3 ls`
- Ensure you have write access to the DVC remote

---

**Issue**: Failure report generated but no stack trace

**Solution**: Check `runs/campaigns/<campaign_id>/failures/<run_id>_failure_report.json` for stderr field with error details

## 13. Best Practices

1. **Small batches first**: Test with 1-2 runs before large campaigns
2. **Review validation reports**: Don't skip quality gates
3. **Document decisions**: Use descriptive notes in approve/reject
4. **Archive campaigns**: Move completed campaigns to `data/archive/`
5. **Monitor drift**: Address drift warnings promptly
6. **Version campaigns**: Use semantic versioning in campaign_id (e.g., `trend_v1`, `trend_v2`)
7. **Test locally**: Run small campaigns locally before production
8. **Check provenance**: Verify git commit is clean before planning

## 14. Integration with ML Pipeline

The Campaign Runner integrates with the broader ML workflow:

```
Campaign Definition (YAML)
  ↓
Plan Generation (provenance capture)
  ↓
Batch Execution (automated backtesting)
  ↓
Validation (quality gates)
  ↓
Manual Review (approve/reject/rework)
  ↓
Enrichment (rich trades dataset)
  ↓
Publishing (master trade log)
  ↓
Model Training (XGBoost, LightGBM)
  ↓
Model Selection (via strategy_archetype metadata)
  ↓
Live Trading (ai-diagnose uses trained models)
```

The `strategy_archetype` field enables model specialization:
- `trend_following` → `models/15m_trend_following.pkl`
- `mean_reversion` → `models/15m_mean_reversion.pkl`

This allows the diagnostic engine to select the correct model based on strategy type and execution timeframe.
