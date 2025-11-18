# PerformanceDiagnosticModel - Offline Regime Analysis

## Overview

`PerformanceDiagnosticModel` is a **quintile classifier** designed for offline regime analysis and strategy improvement. Each model is specialized for a specific timeframe/archetype combination to identify market regimes that produce better/worse performance.

### Key Characteristics

- **Multiple Models**: One model per timeframe/archetype context
- **All Features**: Uses ALL available data including lookahead (NOT production-safe)
- **Quintile Target**: Classifies trades into performance quintiles (0=worst 20%, 4=best 20%)
- **Purpose**: Understand "When does this strategy work best?"

## Architecture

### Context-Specific Regime Analysis

Unlike a single universal model, we train separate diagnostic models for each context:

```
models/diagnostic/
├── 5min_trend_following.pkl
├── 5min_mean_reversion.pkl
├── 15min_trend_following.pkl
├── 1h_trend_following.pkl
└── ...
```

**Why separate models?**
- Each timeframe/archetype has unique performance drivers
- What makes a 5min trend trade successful differs from a 1h trend trade
- Specialized models reveal context-specific regime patterns

### Feature Selection: All Available Features

PerformanceDiagnosticModel uses **all features including lookahead**:

✅ **Allowed Features** (everything):
- `context_at_entry_*` - Entry time context
- `context_at_exit_*` - Exit time context (lookahead)
- `post_exit_analysis_*` - Post-trade analysis (lookahead)
- `sim_hold_*` - Simulated hold analysis (lookahead)
  - `sim_hold_{N}_pnl` - "What-if" PnL if trade held for N additional bars
  - `sim_hold_{N}_exit_reason` - How the simulated hold would have exited
  - Critical for diagnosing exit strategy effectiveness
- `bars_held`, `mae_currency`, `mfe_currency`
- `pnl`, `pnl_movement`, `r_multiple`
- Trade metadata: `side`, `symbol`, `entry_time`, `exit_time`

**Important**: This model is NOT suitable for production use. It's designed for:
- Backtesting analysis
- Strategy improvement research
- Regime identification
- Understanding performance drivers
- Exit strategy optimization

### Quintile Classification

Instead of binary profitable/unprofitable, this model predicts **performance quintiles**:

- **Quintile 0**: Bottom 20% (worst performing trades)
- **Quintile 1**: 20-40% percentile
- **Quintile 2**: 40-60% percentile (median)
- **Quintile 3**: 60-80% percentile
- **Quintile 4**: Top 20% (best performing trades)

Target is based on `r_multiple` (risk-adjusted returns).

## Training

### From Enriched Campaign Data

```python
from trading_platform.ai.models import ModelRegistry
import pandas as pd

# Load enriched trades with all post-trade analysis
enriched_df = pd.read_parquet("data/enriched/campaign_id/rich_trades.parquet")

# Initialize registry
registry = ModelRegistry(model_dir="models")

# Train all diagnostic models (auto-discovers contexts)
trained_models = registry.train_all_diagnostic_models(
    enriched_df,
    n_estimators=100,
    random_state=42
)

print(f"Trained {len(trained_models)} diagnostic models:")
for key in trained_models.keys():
    print(f"  - {key}")

# Save to disk
registry.save()
```

### CLI Training

```bash
# Train from enriched campaign data
poetry run tp train-diagnostic-models \
  --enriched-path data/enriched/trend_following_15m_v1/rich_trades.parquet \
  --model-dir models \
  --n-estimators 100
```

### Minimum Data Requirements

- **Minimum 50 trades** per timeframe/archetype context
- Requires `r_multiple` column for target creation
- Raises `ValueError` if insufficient data

## Analysis Workflows

### Regime Identification

```python
# Load models
registry = ModelRegistry(model_dir="models")
registry.load()

# Get diagnostic model for specific context
model = registry.get_model("diagnostic", "5min_trend_following")

# Predict quintiles for all trades in backtest
quintiles = model.predict(enriched_df)

# Analyze top quintile (best trades)
top_quintile_trades = enriched_df[quintiles == 4]

# What conditions produced the best trades?
print(top_quintile_trades[["context_at_entry_rsi", "context_at_entry_1h_rsi"]].describe())
```

### Feature Importance Analysis

```python
# Get feature importances
importances = model.model.feature_importances_
feature_names = model.feature_names_

# Sort by importance
importance_df = pd.DataFrame({
    "feature": feature_names,
    "importance": importances
}).sort_values("importance", ascending=False)

print("Top 10 performance drivers:")
print(importance_df.head(10))
```

### Performance Distribution by Quintile

```python
# Predict quintiles
quintiles = model.predict(enriched_df)

# Analyze actual r_multiple by predicted quintile
for q in range(5):
    q_trades = enriched_df[quintiles == q]
    avg_r = q_trades["r_multiple"].mean()
    print(f"Quintile {q}: {len(q_trades)} trades, avg R-multiple = {avg_r:.2f}")
```

### Regime-Based Filtering

```python
# Identify high-performance regimes
quintiles = model.predict(enriched_df)

# Extract characteristics of top-quintile trades
top_trades = enriched_df[quintiles == 4]

# Build regime rules (example)
avg_rsi_entry = top_trades["context_at_entry_rsi"].mean()
avg_1h_rsi = top_trades["context_at_entry_1h_rsi"].mean()

print(f"High-performance regime characteristics:")
print(f"  Entry RSI: {avg_rsi_entry:.1f}")
print(f"  H1 RSI: {avg_1h_rsi:.1f}")

# These insights can inform strategy improvements
```

## Use Cases

### 1. Strategy Improvement

**Question**: "What market conditions produce the best trades?"

```python
# Analyze top quintile
best_trades = enriched_df[model.predict(enriched_df) == 4]

# Compare to worst quintile
worst_trades = enriched_df[model.predict(enriched_df) == 0]

# Statistical comparison
for feature in ["context_at_entry_rsi", "context_at_entry_1h_rsi", "context_at_entry_1d_atr"]:
    best_avg = best_trades[feature].mean()
    worst_avg = worst_trades[feature].mean()
    print(f"{feature}: best={best_avg:.2f}, worst={worst_avg:.2f}")
```

### 2. Regime Detection

**Question**: "When should I trade this strategy?"

```python
# Predict probabilities for each quintile
proba = model.predict_proba(current_conditions_df)

# Probability of top quintile (best trades)
p_best = proba[:, 4]

# Only trade when high probability of top-quintile performance
should_trade = p_best > 0.4  # Threshold tuned via analysis
```

### 3. Post-Campaign Analysis

**Question**: "Why did this campaign underperform?"

```python
# Analyze campaign results
campaign_df = pd.read_parquet("data/enriched/underperforming_campaign/rich_trades.parquet")

quintiles = model.predict(campaign_df)

# Distribution of trades across quintiles
print(pd.Series(quintiles).value_counts().sort_index())

# If most trades are in quintiles 0-1:
# → Strategy was trading in poor regimes
# → Need to add regime filters or improve entry rules
```

### 4. Feature Engineering Validation

**Question**: "Did my new features help?"

```python
# Train model on old feature set
model_old = PerformanceDiagnosticModel(...)
model_old.fit(df_old_features)

# Train model on new feature set
model_new = PerformanceDiagnosticModel(...)
model_new.fit(df_new_features)

# Compare feature importances
# If new features rank high → they're useful
# If new features rank low → they're not informative
```

### 5. Exit Strategy Optimization

**Question**: "Am I exiting trades too early?"

The `sim_hold_*` features provide critical insights into exit strategy effectiveness:

```python
# Load enriched trades with simulated hold analysis
enriched_df = pd.read_parquet("data/enriched/campaign/rich_trades.parquet")

# Train diagnostic model (includes sim_hold features)
registry = ModelRegistry()
models = registry.train_all_diagnostic_from_enriched(enriched_df)
model = models["5min_trend_following"]

# Analyze feature importance
importances = pd.DataFrame({
    "feature": model.feature_names_,
    "importance": model.model.feature_importances_
}).sort_values("importance", ascending=False)

# Check if simulated hold features are important
sim_hold_importance = importances[importances["feature"].str.startswith("sim_hold_")]
print("Simulated Hold Feature Importance:")
print(sim_hold_importance)

# If sim_hold_10_pnl ranks high:
# → Holding 10 bars longer would significantly improve results
# → Current exit strategy is too aggressive

# Compare actual PnL vs simulated hold PnL
actual_pnl = enriched_df["pnl"].mean()
sim_10_pnl = enriched_df["sim_hold_10_pnl"].mean()
sim_20_pnl = enriched_df["sim_hold_20_pnl"].mean()

print(f"Actual PnL: {actual_pnl:.2f}")
print(f"If held 10 bars longer: {sim_10_pnl:.2f} ({sim_10_pnl - actual_pnl:+.2f})")
print(f"If held 20 bars longer: {sim_20_pnl:.2f} ({sim_20_pnl - actual_pnl:+.2f})")

# Analyze exit reasons for simulated holds
from collections import Counter
exit_reasons_sim_10 = Counter(enriched_df["sim_hold_10_exit_reason"])
print(f"\nSimulated 10-bar hold exit reasons:")
for reason, count in exit_reasons_sim_10.most_common():
    print(f"  {reason}: {count} ({count/len(enriched_df)*100:.1f}%)")
```

This analysis reveals:
- Whether you're exiting profitable trends too early
- Optimal holding periods for this strategy/regime
- How exit criteria (stop loss, take profit, trailing stop) would perform with different horizons

## CLI Usage

### Training

```bash
# Train all diagnostic models from enriched data
poetry run tp train-diagnostic-models \
  --enriched-path data/enriched/campaign/rich_trades.parquet \
  --model-dir models

# Specify hyperparameters
poetry run tp train-diagnostic-models \
  --enriched-path data/enriched/campaign/rich_trades.parquet \
  --model-dir models \
  --n-estimators 200 \
  --random-state 42
```

### Analysis

```bash
# Analyze performance regimes
poetry run tp analyze-performance \
  --model-dir models \
  --enriched-path data/enriched/campaign/rich_trades.parquet \
  --timeframe 5min \
  --archetype trend_following
```

## Model Persistence

Models are saved using joblib:

```
models/
└── diagnostic/
    ├── 5min_trend_following.pkl
    ├── 15min_trend_following.pkl
    └── ...
```

Each model file contains:
- Trained RandomForestClassifier (quintile classifier)
- SimpleImputer (fitted)
- Feature names (for validation)
- Metadata (timeframe, archetype)

## Comparison: Diagnostic vs Profitability

| Aspect | ProfitabilityModel | PerformanceDiagnosticModel |
|--------|-------------------|---------------------------|
| **Purpose** | Real-time signal filtering | Offline regime analysis |
| **Features** | Entry-time only | All (including lookahead) |
| **Target** | Binary (profitable/not) | Quintiles (0-4) |
| **Production Use** | ✅ Yes (no lookahead) | ❌ No (has lookahead) |
| **Use Case** | "Should I take this trade?" | "When does this work best?" |
| **Timeframe** | Real-time | Post-campaign analysis |

## Best Practices

### 1. Use After Campaigns

Train diagnostic models AFTER running a campaign to understand what worked:

```python
# 1. Run campaign → generates enriched data
# 2. Train diagnostic models
# 3. Analyze regime patterns
# 4. Improve strategy based on findings
# 5. Run new campaign with improvements
```

### 2. Combine with Profitability Models

```python
# Profitability model: "Will this trade be profitable?"
prob_pred = prof_model.predict_proba(entry_features)[0][1]

# Diagnostic model: "Is this a high-performance regime?"
diag_pred = diag_model.predict(all_features)[0]

# Combined decision
should_trade = (prob_pred > 0.6) and (diag_pred >= 3)
```

### 3. Regular Retraining

As market conditions evolve, retrain diagnostic models:

```python
# Combine data from multiple recent campaigns
recent_campaigns = [
    "data/enriched/campaign_1/rich_trades.parquet",
    "data/enriched/campaign_2/rich_trades.parquet",
    "data/enriched/campaign_3/rich_trades.parquet",
]

combined_df = pd.concat([pd.read_parquet(p) for p in recent_campaigns])

# Retrain with latest data
registry.train_all_diagnostic_models(combined_df)
registry.save()
```

## See Also

- [PerformanceDiagnosticModel API](../src/trading_platform/ai/models/performance_diagnostic.py)
- [ProfitabilityModel Documentation](02_profitability_model.md)
- [ModelRegistry Documentation](03_model_registry.md)
- [ML Data Curation Guide](05_ml_data_curation_guide.md)
- [Campaign Runner Guide](06_campaign_runner_guide.md)
