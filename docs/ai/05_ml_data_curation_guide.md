# Guide: ML Data Curation Pipeline

This document is the single source of truth for generating and curating the
master trade dataset used for training the AI Lab's machine learning models.

## 1. Overview and Rationale

The goal of this pipeline is to produce a high-quality, reproducible dataset of
"rich trade" records. A disciplined approach ensures the training data remains
clean, consistent, and free from contamination by experimental or failed runs.

This process separates ad-hoc research from formal ML training, which is
critical for building robust and reliable predictive models.

## 2. ML Modeling Strategy: A Two-Pronged Approach

Instead of a single monolithic "uber-model", our strategy builds **multiple,
specialized models** and tools that fit into two categories: a
**Diagnostic Engine** and a **Predictive Engine**.

### 2.1 The Diagnostic Engine (Descriptive Analysis)

- **Purpose:** Analyze completed backtests to answer:
  *"Under what conditions did this strategy perform best or worst in the past?"*
- **Implementation:** Extend the rule-based `ai-diagnose` command with advanced
  analytical techniques (e.g., decision trees trained on curated data) to
  discover human-readable "optimal condition" rules automatically.
- **Output:** A JSON/Markdown report with insights and recommendations.

### 2.2 The Predictive Engine (Predictive Modeling)

- **Purpose:** Evaluate live market conditions to answer:
  *"What is the likely outcome if I take this trade?"*
- **Implementation:** Train complex models (e.g., XGBoost, LightGBM) to predict
  trade outcomes such as R-multiple. Models are specialized by **execution
  timeframe** and **strategy archetype**.
- **Output:** Trained artifacts (e.g., `models/15m_trend_following.pkl`) used
  for live trade filtering and for enriching backtest briefs with predictive
  scores.

### 2.3 Strategic Roadmap

1.  **Phase 1: Build the Data Pipeline (Current Task).** Create the
    `master_trade_log.parquet` dataset.
2.  **Phase 2: Enhance the Diagnostic Engine.** Implement advanced rule-discovery.
3.  **Phase 3: Implement the Predictive Engine.** Train and deploy predictive models.

## 3. Model Selection and Inference

Given a library of specialized models, the `ai-diagnose` tool must select the
correct artifact for any `brief.json`. A metadata-driven mechanism enables this.

1.  **Embed Metadata in the Brief:** During each run the Campaign Runner injects
    `strategy_archetype` and `execution_timeframe` into `brief.meta`.
2.  **Standardize Model Naming:** Trained models follow a strict convention
    (e.g., `models/15m_trend_following.pkl`) that mirrors the metadata.
3.  **Dynamic Model Loading:** `ai-diagnose` reads metadata, constructs the
    model path, and loads the correct artifact dynamically.

## 4. The "Rich Trade" Data Model

A "rich trade" is a self-contained record capturing both the outcome and full
context surrounding a trade.

### Core Data Structure

The schema for this model includes:

- **Trade ID & Provenance:** Identifiers linking the trade to its backtest run,
  strategy, and instrument. Includes `strategy_archetype` (e.g., trend,
  mean-reversion).
- **Entry Context:** Market conditions at entry time, including structured
  `trigger_condition` and the full feature set.
- **Exit Context:** Mirrors the entry context; also records the exit reason
  (`stop_loss`, `take_profit`, `strategy_signal`).
- **Sequential Context:** Relationship to the previous trade
  (`bars_since_last_exit`, `pnl_of_last_trade`).
- **Risk Management Context:** Intended risk data, such as initial stop-loss and
  take-profit levels.
- **Trade Outcomes:** Targets like PnL (currency and R-multiple), MFE/MAE, and
  duration.

### Feature Set Specification

(Feature set details remain the same as previous version)

## 5. The Curation Workflow: Manual vs. Automated

### 5.1 Governance Roles

- **Researcher:** Runs exploratory backtests. Their output **never** flows into the
  curated dataset until approved.
- **Curation Lead:** Reviews candidate runs, validates metadata, and signs off on
  inclusion in the master trade log.
- **Automation Engineer:** Maintains the orchestration scripts (Campaign Runner,
  validation jobs, DVC pipelines) and monitors scheduled executions.

### 5.2 Workflow Stages

1. **Candidate Run Submission**
   - Researcher uploads a `brief.json`, `run_config.json`, and supporting CSV
     exports to the `data/candidates/<campaign_id>/` folder.
   - Each submission must include:
     - `meta.strategy_archetype`
     - `meta.execution_timeframe`
     - A unique `campaign_id` (used for traceability and DVC tags).
2. **Automated Screening**
   - The `campaign_validate.py` script performs:
     - JSON schema validation for `brief.json` and `run_config.json`.
     - Indicator registry checks (ensures contextual features originate from the
       single source of truth in `indicators_registry.py`).
     - Basic performance sanity checks (non-empty trades, bounded drawdown).
   - Output written to `data/candidates/<campaign_id>/validation_report.json`.
3. **Manual Review**
   - Curation Lead audits the validation report, spot-checks trades using the
     “Top/Bottom 5” samples, and verifies narrative notes.
   - Decision recorded in `data/candidates/<campaign_id>/decision.yaml` with one
     of: `approved`, `needs-rework`, `rejected`.
4. **Enrichment and Feature Audit**
   - Approved runs feed into the enrichment job (Section 6) to derive
     multi-timeframe contextual features, regime labels, and diagnostic stats.
   - Derived dataset stored temporarily in
     `data/enriched/<campaign_id>/rich_trades.parquet`.
5. **Publishing to Master Trade Log**
   - Automation Engineer runs `poetry run python -m trading_platform.ai.data_curation`
     with `--campaign-id <campaign_id>`.
   - The job appends enriched rows to `data/master/master_trade_log.parquet` and
     updates the DVC tracking file
     `data/dvc/processed/training_sets/master_trade_log.parquet.dvc`.
   - Summary metrics and SHA256 checksum recorded in
     `docs/ai/data_curation_history.md`.

### 5.3 Quality Gates

- **Schema Validation:** Uses `pydantic` models mirroring Section 4 to reject
  invalid trades.
- **Duplicate Prevention:** `(campaign_id, trade_id)` must be unique. The loader
  enforces `drop_duplicates` and raises on conflicts.
- **Drift Monitoring:** Monthly job computes distribution deltas for key fields
  (`r_multiple`, `entry_context.rsi_14`, etc.) versus the previous snapshot. Any
  KS-statistic > 0.15 triggers a manual review ticket.
- **Audit Trail:** Each publish action appends an entry to
  `docs/ai/logs/campaign_audit.md` (timestamp, actor, commit hash, dataset size).

### 5.4 Manual Overrides

- Only the Curation Lead may mark trades with `override_reason`.
- Overrides must include: `reason_code` (enum), `notes`, and a link to a JIRA
  ticket.
- Overrides are stored in `data/overrides/<campaign_id>.yaml` and re-applied on
  every re-build to keep runs reproducible.

## 6. Automating Data Generation: The Campaign Runner

### 6.1 Responsibilities

The Campaign Runner orchestrates reproducible backtest batches and associated
data exports. Its responsibilities:

1. Expand high-level campaign definitions (YAML) into concrete RunConfig files.
2. Execute runs via `poetry run python -m trading_platform.core.run --config`.
3. Collect artifacts (`brief.json`, trade exports, contextual features).
4. Record provenance metadata (git commit, dependency hashes, data version).
5. Trigger enrichment jobs and push candidate bundles for review.

### 6.2 Configuration Anatomy

Campaign YAML files live in `config/campaigns/`. Required keys:

- `campaign_id`: unique identifier (matches folder naming).
- `strategy_path`: relative path to strategy YAML.
- `rem_path`: optional REM configuration.
- `run_matrix`: list of parameter overrides (e.g., start/end dates, instruments).
- `contextual_features`: multi-timeframe features to compute (uses the
  `timeframe` field introduced in the multi-timeframe implementation plan).

### 6.3 Execution Lifecycle

1. **Plan Generation**
   - `poetry run python -m trading_platform.ai.campaigns.generate_plan --campaign-id`
     emits a manifest JSON enumerating runs and metadata expectations.
2. **Run Execution**
   - The runner iterates over the manifest, executing each run and collecting
     outputs under `runs/<campaign_id>/<run_id>/`.
3. **Artifact Packaging**
   - After each run, `poetry run python -m trading_platform.ai.exporters.rich_trade`
     emits enriched trade rows into the candidate folder (Section 5).
4. **Completion Hook**
   - Once all runs succeed, the runner writes `campaign_complete.yaml` summarizing
     success/failure counts and generated dataset size.

### 6.4 Failure Handling

- Any run failure:
  - Stops the campaign by default (`--fail-fast`), unless `--continue-on-error`
    is specified (used only for exploratory campaigns).
  - Produces `runs/<campaign_id>/<run_id>/failure_report.json` capturing stack
    traces, config snapshot, and environment info.
  - Requires a manual retry or update to the campaign manifest.

### 6.5 Multi-Timeframe Contextual Features

The `contextual_features` field supports an optional `timeframe` parameter that
enables computing indicators on higher timeframes than the base execution
timeframe. This is critical for ML models that need broader market context.

**Example Campaign Configuration:**

```yaml
campaign_id: trend_following_15m_v1
strategy_path: config/strategies/ema_crossover.yaml
execution_timeframe: 15m
run_matrix:
  - instrument: EURUSD
    start_date: 2023-01-01
    end_date: 2023-12-31

contextual_features:
  # Base timeframe features (15m)
  - name: rsi_14
    type: RSI
    params:
      length: 14

  # Higher timeframe features (1H)
  - name: h1_rsi
    type: RSI
    params:
      length: 14
    timeframe: 1h

  - name: h1_ema_trend
    type: EMA
    params:
      length: 50
    timeframe: 1h

  # Daily context
  - name: d1_atr
    type: ATR
    params:
      length: 14
    timeframe: 1D
```

**How It Works:**

1. The feature engine resamples base timeframe data (e.g., 15m) to the specified
   higher timeframe (e.g., 1h) using OHLC aggregation.
2. Indicators are computed on the resampled data.
3. Results are forward-filled back to the base timeframe index, so every 15m bar
   has access to the current 1H indicator value.
4. At trade entry and exit, both base and higher-timeframe features are captured
   in `context_at_entry` and `context_at_exit`.

**Performance Considerations:**

- The feature engine caches resampled DataFrames per timeframe within each
  `compute_features()` call, so multiple features sharing the same timeframe
  incur only one resampling operation.
- Memory usage scales linearly with the number of unique timeframes.
- Computation time increases with the number of features and timeframes, but
  remains efficient for typical use cases (5-10 features across 2-3 timeframes).

**Validation:**

- The `timeframe` field accepts any valid pandas offset alias (e.g., `1h`, `4h`,
  `1D`, `1W`).
- Invalid timeframe strings raise a `ValueError` during feature computation.
- The JSON schema for `FeatureConfig` validates this field (see
  `docs/schemas/feature_config.schema.json`).

### 6.6 Migration Guide: Adding Multi-Timeframe Features

**For Existing Campaigns:**

1. **Identify Higher-Timeframe Context Needs:** Review your ML model features and
   determine which indicators would benefit from broader market context. Common
   examples: trend filters (EMA 50/200 on 1H/4H), volatility (ATR on 1D), momentum
   (RSI on 4H).

2. **Update Campaign YAML:** Add the `timeframe` field to relevant features in
   `contextual_features`. Features without `timeframe` continue to use the base
   timeframe (backwards compatible).

3. **Regenerate Golden Files (if applicable):** If your campaign uses golden file
   testing for validation, regenerate them after adding multi-timeframe features:
   ```bash
   poetry run python scripts/generate_golden_trades.py --campaign-id <campaign_id>
   ```

4. **Verify Rich Trade Exports:** Run a test backtest and inspect
   `runs/<campaign_id>/<run_id>/rich_trades.csv` to confirm the new
   higher-timeframe features appear in both `entry_features` and `exit_features`
   columns.

5. **Update Feature Documentation:** Add descriptions for new features to your
   campaign's feature specification document.

**For New Campaigns:**

- Include multi-timeframe features from the start in your campaign YAML.
- Follow the naming convention: `<timeframe>_<indicator>` (e.g., `h1_rsi`,
  `d1_atr`) to make the timeframe explicit in feature names.
- Document the rationale for each higher-timeframe feature in campaign notes.

## 7. Key Concepts

- **Rich Trade:** Trade record with full entry, exit, sequential, and risk
  context (Section 4). Stored in Parquet with schema enforced via Pydantic.
- **Campaign:** Reproducible backtest set designed to generate training data,
  identified by `campaign_id` and orchestrated by the Campaign Runner.
- **Master Trade Log:** Append-only Parquet dataset feeding ML training.
  Versioned with DVC; checksum recorded after every publish.
- **Diagnostic Engine:** Descriptive analytics pipeline (`ai-diagnose`) that
  consumes curated data to produce human-readable insights.
- **Predictive Engine:** Predictive models that score future trades. Artifacts
  are selected via `strategy_archetype` and timeframe metadata.
- **Quality Gate:** Automated validation enforcing schema, dedupe, and drift
  checks prior to master trade log updates.
- **Override:** Manual inclusion or exclusion of trades with justification. Every
  override is logged in the overrides YAML and replayed during rebuilds.

### 7.1 Checklists

- **Pre-Publish Checklist:**
  1. Validation report status `passed`.
  2. Manual review notes linked in decision file.
  3. Overrides (if any) documented with ticket reference.
  4. Checksums for new data recorded in `data_curation_history.md`.
- **Post-Publish Checklist:**
  1. Run DVC push for updated artifacts.
  2. Notify ML team on Slack with campaign summary template.
  3. Archive candidate folder to `data/archive/<campaign_id>/` for reproducibility.

This expanded guide is the authoritative reference for data curation. Updates
must be reviewed by the Curation Lead and Automation Engineer to keep the
pipeline aligned with ML governance requirements.
