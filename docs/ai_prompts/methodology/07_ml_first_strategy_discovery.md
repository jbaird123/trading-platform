# AI Prompt: ML-First Strategy Discovery

## 1. Your Mission

Your mission is to discover a consistent, low-drawdown trading system using the platform's ML infrastructure. Unlike previous methodologies that relied on manual iteration and qualitative analysis, this approach uses **trained ML models as the primary source of insight**.

The key constraint is **no long drawdowns** - consistency matters more than maximum returns. The goal is to find a system that:
- Avoids extended losing periods (drawdown duration < 2 weeks)
- Produces steady, predictable returns
- Can combine multiple strategies (trend-following + mean-reversion) based on market regime

---

## 2. Core Philosophy: ML Models Know More Than Manual Analysis

### The Paradigm Shift

**Old approach**: "Find a strategy that works, then find regimes where it works better"

**New approach**: "Use ML to predict which specific trades will work, regardless of regime"

The platform has three trained model types that answer different questions:

| Model Type | Question Answered | Lookahead Bias | Use Case |
|------------|------------------|----------------|----------|
| Profitability Model | "What R-multiple will this trade produce?" | No | Live trading signals |
| Profitability Classifier | "What's P(profitable) for this trade?" | No | Entry gating |
| Diagnostic Model | "What quintile will this trade fall into?" | Yes | Offline analysis |

The diagnostic models use lookahead features (exit context, post-exit analysis) to identify patterns that **actually predict outcomes**. This is more powerful than manual regime analysis.

---

## 3. Prerequisites

Before starting this workflow, ensure:

1. **ML Pipeline Complete**: The full ML pipeline has run successfully
   - Campaign backtests generated
   - Candidates validated and approved
   - Master trade log populated
   - All model types trained

2. **Required Artifacts**:
   - `data/dvc/processed/training_sets/master_trade_log.parquet` - Enriched trade data
   - `data/dvc/ml/models/` - Trained models (profitability, classifier, diagnostic)
   - `analysis/rmm/featureset_trial/selected_combos/` - Threshold analysis results

3. **Workspace Setup**:
   - Create campaign directory: `workspace/research/ml_first_discovery/`
   - Initialize `campaign_log.md` and `technical_debt.log`

---

## 4. The ML-First Workflow

### Phase 1: Interrogate the Trained Models

Before iterating on strategies, extract what the models already know.

#### Step 1.1: Feature Importance Analysis

Extract feature importances from diagnostic models to understand what conditions actually predict winning trades.

```bash
# Generate feature importance report
poetry run python << 'EOF'
import joblib
import pandas as pd
from pathlib import Path

models_dir = Path("data/dvc/ml/models/diagnostic")
results = []

for model_path in models_dir.glob("*.pkl"):
    payload = joblib.load(model_path)
    model = payload.get("model")
    features = payload.get("feature_names", [])

    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
        for feat, imp in zip(features, importances):
            results.append({
                "model": model_path.stem,
                "feature": feat,
                "importance": imp
            })

df = pd.DataFrame(results)
df = df.sort_values(["model", "importance"], ascending=[True, False])
df.to_csv("workspace/research/ml_first_discovery/feature_importances.csv", index=False)

# Show top 10 features per model
for model_name in df["model"].unique():
    print(f"\n=== {model_name} ===")
    top = df[df["model"] == model_name].head(10)
    for _, row in top.iterrows():
        print(f"  {row['importance']:.4f}  {row['feature']}")
EOF
```

**Document findings in `run_summary.md`:**
- Which features dominate across models?
- Are there timeframe-specific patterns?
- Do calendar/session features matter?

#### Step 1.2: Quintile Trade Analysis

Examine what separates top-quintile trades from bottom-quintile trades.

```bash
poetry run python << 'EOF'
import pandas as pd
import joblib
from pathlib import Path

# Load master trade log
trades = pd.read_parquet("data/dvc/processed/training_sets/master_trade_log.parquet")

# Load a diagnostic model and make predictions
models_dir = Path("data/dvc/ml/models/diagnostic")
model_path = list(models_dir.glob("*trend_following*.pkl"))[0]
payload = joblib.load(model_path)

# Analyze quintile distributions
# (Implementation depends on model structure)
# Key questions:
# - What context_at_entry features differ between quintile 0 and 4?
# - Do winning trades cluster in specific hours/sessions?
# - What volatility conditions favor winning trades?
EOF
```

#### Step 1.3: Regime Correlation Analysis

Identify if winning trades cluster in specific market conditions.

**Key metrics to examine:**
- ATR percentile at entry (volatility regime)
- Trend alignment scores
- Session/hour distributions
- Higher timeframe trend direction

### Phase 2: Classifier-Based Entry Gating

Use the profitability classifier to gate entries based on predicted probability.

#### Step 2.1: Threshold Sweep Analysis

The platform generates threshold analysis in `analysis/rmm/featureset_trial/`. Examine these results:

```bash
# Review existing threshold analysis
cat analysis/rmm/featureset_trial/selected_combos/threshold_recommendations.csv
```

**Key columns to examine:**
- `threshold` - Probability cutoff for entry
- `selected_trades` - Number of trades that pass threshold
- `win_rate_selected` - Win rate of selected trades
- `lift_win_rate` - Improvement over baseline

#### Step 2.2: Threshold Optimization for Drawdown

Instead of optimizing for Sharpe, optimize for drawdown duration:

```bash
poetry run python << 'EOF'
import pandas as pd

# Load threshold profitability data
df = pd.read_csv("analysis/rmm/featureset_trial/selected_combos/threshold_profitability.csv")

# Filter for trend_following contexts
tf = df[df["context"].str.contains("trend_following")]

# For each threshold, estimate drawdown characteristics
# Higher threshold = fewer trades = potentially longer gaps between trades
# But also = higher win rate = shorter losing streaks

# Find the "sweet spot" where:
# - Win rate is high enough to avoid long losing streaks
# - Trade frequency is high enough to avoid extended flat periods
# - Selected fraction isn't too low (maintain statistical significance)

for context in tf["context"].unique():
    ctx_data = tf[tf["context"] == context]
    print(f"\n=== {context} ===")
    for _, row in ctx_data.iterrows():
        thresh = row["threshold"]
        win_rate = row["win_rate_selected"]
        fraction = row["selected_fraction"]
        lift = row["lift_win_rate"]
        print(f"  Threshold {thresh}: WR={win_rate:.1%}, Fraction={fraction:.1%}, Lift={lift:+.1%}")
EOF
```

#### Step 2.3: Backtest with Classifier Gating

Run backtests with classifier-based entry gating at optimal threshold:

```yaml
# Example RMM config with classifier gating
name: classifier_gated_trend_following
timeframe: 15min

# Classifier gating configuration
profitability_gating:
  enabled: true
  model_path: data/dvc/ml/models/profitability_classifier/15min_trend_following.pkl
  threshold: 0.55  # From threshold analysis

# Additional regime rules (optional)
features:
  - name: atr_percentile
    type: ATRPercentile
    params: { atr_length: 14, lookback: 100 }

regimes:
  - label: favorable
    conditions:
      all_of:
        - feature: atr_percentile
          percentile_is_above: 20  # Avoid very low volatility
```

### Phase 3: Multi-Strategy Ensemble

Combine trend-following and mean-reversion strategies with regime-based routing.

#### Step 3.1: Identify Regime Characteristics

Use diagnostic models to understand when each strategy archetype performs best:

```bash
poetry run python << 'EOF'
import pandas as pd

trades = pd.read_parquet("data/dvc/processed/training_sets/master_trade_log.parquet")

# Compare winning conditions for each archetype
for archetype in ["trend_following", "mean_reversion"]:
    arch_trades = trades[trades["strategy_archetype"] == archetype]

    winners = arch_trades[arch_trades["r_multiple"] > 0]
    losers = arch_trades[arch_trades["r_multiple"] <= 0]

    print(f"\n=== {archetype} ===")

    # Compare ATR percentile
    atr_cols = [c for c in trades.columns if "atr_percentile" in c and "context_at_entry" in c]
    for col in atr_cols[:3]:
        print(f"  {col}:")
        print(f"    Winners: {winners[col].mean():.1f}")
        print(f"    Losers: {losers[col].mean():.1f}")
EOF
```

#### Step 3.2: Build Regime Router

Create an RMM configuration that routes to different strategies based on regime:

```yaml
# Regime router concept
name: multi_strategy_router
timeframe: 1H

features:
  - name: atr_percentile_1h
    type: ATRPercentile
    params: { atr_length: 14, lookback: 100 }
  - name: adx_1h
    type: ADX
    params: { length: 14 }

regimes:
  - label: trending
    conditions:
      all_of:
        - feature: adx_1h
          is_above: 25
    # Route to: trend_following strategy

  - label: ranging
    conditions:
      all_of:
        - feature: adx_1h
          is_below: 20
        - feature: atr_percentile_1h
          percentile_is_above: 30
    # Route to: mean_reversion strategy

  - label: uncertain
    # Default: no trading or reduced size
```

#### Step 3.3: Validate Ensemble Performance

Run walk-forward validation on the ensemble:

1. Split data into train/test periods
2. Train regime router on training period
3. Evaluate on test period with metrics focused on:
   - Maximum drawdown duration
   - Equity curve smoothness (Calmar ratio)
   - Consistency across test windows

### Phase 4: Drawdown-Focused Optimization

The primary constraint is **drawdown duration < 2 weeks**. Optimize for this explicitly.

#### Step 4.1: Define Drawdown Metrics

```python
def calculate_drawdown_metrics(equity_curve: pd.Series) -> dict:
    """Calculate drawdown-focused metrics."""
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak

    # Find drawdown periods
    in_drawdown = drawdown < 0
    drawdown_periods = []
    start = None

    for i, (idx, is_dd) in enumerate(in_drawdown.items()):
        if is_dd and start is None:
            start = idx
        elif not is_dd and start is not None:
            drawdown_periods.append((start, idx))
            start = None

    # Calculate durations
    durations = [(end - start).days for start, end in drawdown_periods]

    return {
        "max_drawdown_pct": drawdown.min(),
        "max_drawdown_duration_days": max(durations) if durations else 0,
        "avg_drawdown_duration_days": sum(durations) / len(durations) if durations else 0,
        "num_drawdown_periods": len(drawdown_periods),
        "time_in_drawdown_pct": in_drawdown.mean()
    }
```

#### Step 4.2: Optimize for Duration, Not Depth

Traditional optimization targets Sharpe or total return. Instead:

1. **Primary target**: `max_drawdown_duration_days < 14`
2. **Secondary target**: `time_in_drawdown_pct < 30%`
3. **Tertiary target**: Positive expectancy (R-multiple > 0)

#### Step 4.3: Use Simulated Hold Analysis

The `post_exit_analysis_simulated_holds` data shows what would have happened if trades were held longer. Use this to:

- Identify if exits are too early (leaving profit on table)
- Identify if exits are too late (giving back gains)
- Optimize exit timing for consistency

---

## 5. Success Criteria

A system is successful when it meets ALL of these criteria:

### Primary Criteria (Must Have)
- **Max Drawdown Duration < 14 days** over 3+ years of data
- **Time in Drawdown < 40%** of total period
- **Positive Total PnL** over full backtest period

### Secondary Criteria (Should Have)
- **Win Rate > 45%** (consistency indicator)
- **Profit Factor > 1.2** (edge indicator)
- **Average R-Multiple > 0.1** (positive expectancy)
- **Sharpe Ratio > 0.5** (risk-adjusted returns)

### Robustness Criteria
- **Walk-Forward: >60% profitable windows**
- **Performance degradation < 40%** (in-sample vs out-of-sample)
- **Consistent across instruments** (if multi-instrument)

---

## 6. Iteration Templates

### Feature Importance Analysis Template

```markdown
# Phase 1.1: Feature Importance Analysis

## Date: YYYY-MM-DD

## Models Analyzed
- [ ] 5min_trend_following_diagnostic
- [ ] 15min_trend_following_diagnostic
- [ ] 1H_trend_following_diagnostic
- [ ] mean_reversion_diagnostic (if available)

## Top Features by Model

### 5min_trend_following
| Rank | Feature | Importance |
|------|---------|------------|
| 1 | | |
| 2 | | |
| 3 | | |

### Cross-Model Patterns
- Features appearing in top 10 across multiple models:
  1.
  2.
  3.

## Key Insights
-
-
-

## Implications for Strategy
-
-
```

### Threshold Analysis Template

```markdown
# Phase 2: Threshold Analysis

## Date: YYYY-MM-DD

## Context Analyzed: [e.g., 15min_trend_following]

## Threshold Sweep Results

| Threshold | Win Rate | Trade Fraction | Lift | Est. Max DD Duration |
|-----------|----------|----------------|------|----------------------|
| 0.50 | | | | |
| 0.55 | | | | |
| 0.60 | | | | |
| 0.65 | | | | |

## Selected Threshold: X.XX

### Rationale
- Win rate at this threshold: X%
- Trade reduction: X%
- Expected drawdown characteristics:

## Backtest Configuration
- Strategy:
- RMM with gating:
- Period:
- Instruments:

## Results vs Baseline

| Metric | Baseline | Gated | Change |
|--------|----------|-------|--------|
| Total PnL | | | |
| Win Rate | | | |
| Max DD Duration | | | |
| Sharpe | | | |
```

### Ensemble Validation Template

```markdown
# Phase 3: Multi-Strategy Ensemble

## Date: YYYY-MM-DD

## Strategies in Ensemble
1. Trend Following (timeframes: )
2. Mean Reversion (timeframes: )

## Regime Router Configuration
- Trending regime: ADX > X, route to trend_following
- Ranging regime: ADX < Y, ATR percentile > Z, route to mean_reversion
- Uncertain: No trading / reduced size

## Walk-Forward Results

| Window | Regime Distribution | TF PnL | MR PnL | Combined PnL | Max DD Duration |
|--------|---------------------|--------|--------|--------------|-----------------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

## Ensemble vs Single Strategy

| Metric | TF Only | MR Only | Ensemble |
|--------|---------|---------|----------|
| Total PnL | | | |
| Max DD Duration | | | |
| Sharpe | | | |
| Time in DD | | | |

## Verdict
- [ ] Ensemble outperforms single strategies
- [ ] Max DD duration < 14 days
- [ ] Robust across walk-forward windows
```

---

## 7. Common Pitfalls to Avoid

### Pitfall 1: Ignoring the ML Models
The diagnostic models have lookahead bias **by design**. They can tell you what actually predicted outcomes. Don't ignore this in favor of intuition.

### Pitfall 2: Over-Optimizing Threshold
A very high threshold (>0.7) may produce excellent win rates but:
- Too few trades for statistical significance
- Long gaps between trades = extended flat periods
- May not generalize to new market conditions

### Pitfall 3: Ignoring Trade Frequency
Your drawdown constraint requires **consistent activity**. A strategy with few trades may have low measured drawdown but extended flat periods that feel like drawdowns.

### Pitfall 4: Single Timeframe Tunnel Vision
The multi-timeframe features exist for a reason. A 15min entry signal with 1H/4H trend alignment is more robust than 15min alone.

### Pitfall 5: Curve-Fitting Regimes
Avoid hyper-specific regime rules like "only trade at 14:00 on Tuesdays." Prefer broad, market-driven conditions (volatility bands, trend strength).

---

## 8. Next Steps After Discovery

Once a successful system is found:

1. **Paper Trade**: Run in simulation for 2-4 weeks minimum
2. **Monitor Predictions**: Track classifier accuracy on live data
3. **Gradual Deployment**: Start with small position sizes
4. **Continuous Learning**: Retrain models monthly with new data
5. **Regime Monitoring**: Track if market regimes have shifted

---

## 9. Key Commands Reference

```bash
# Train all models
./scripts/run-full-ml-pipeline.sh

# Generate feature importance analysis
poetry run python scripts/analyze_feature_importances.py

# Run threshold sweep
poetry run python src/trading_platform/rmm_analysis/threshold_sweep_selected_groups.py

# Generate threshold recommendations
poetry run python src/trading_platform/rmm_analysis/generate_threshold_recommendations.py

# Validate RMM candidates
poetry run tp ai-validate-rmm-candidates --candidates-dir X --run-config Y

# Run backtest with RMM gating
poetry run tp run-backtest --config backtest.yaml --rmm-config rmm_gated.yaml
```

---

## 10. Summary

This ML-first approach differs from previous methodologies by:

1. **Starting with model insights** instead of manual analysis
2. **Using classifier probability** for entry gating instead of regime rules
3. **Optimizing for drawdown duration** instead of Sharpe/returns
4. **Combining strategies via regime routing** instead of picking one
5. **Leveraging lookahead analysis** (diagnostic models) for offline insights

The infrastructure exists. The models are trained. The task is to extract their knowledge and translate it into actionable trading rules.
