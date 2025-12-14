# AI Prompt: ML-First Strategy Discovery

## 1. Your Mission

Your mission is to discover a consistent, low-drawdown trading system using the platform's ML infrastructure. Unlike previous methodologies that relied on manual iteration and qualitative analysis, this approach uses **trained ML models as the primary source of insight**.

The key constraint is **minimizing drawdown duration** - consistency matters more than maximum returns. The goal is to find a system that:
- Minimizes the length of losing periods (target: ~2 weeks, but this is a guideline, not a hard rule)
- Produces steady, predictable returns
- Can combine multiple strategies (trend-following + mean-reversion) based on market regime

**Important Note on Drawdown Duration Target**: The ~14 day target comes from general day trading guidance suggesting drawdowns shouldn't extend beyond 2 weeks. However, this is a soft target based on common advice, not a scientifically validated threshold. The real goal is to **minimize drawdown duration relative to what's achievable** with the strategy type and market conditions. A 15 or 20 day drawdown may be perfectly acceptable if that represents strong performance for the approach. During analysis, compare drawdown durations against:
- Historical norms for similar strategies
- What the data shows is realistically achievable
- Whether shorter drawdowns come at an unacceptable cost (e.g., drastically reduced returns)

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

#### Step 1.4: Classifier Calibration Analysis

Before using classifier probability for gating, verify the model is well-calibrated.

A calibrated model means: when it predicts 60% probability, the trade wins ~60% of the time.

```bash
poetry run python << 'EOF'
import pandas as pd
import numpy as np
import joblib
from pathlib import Path

def analyze_calibration(model_path: Path, trades: pd.DataFrame):
    """Analyze calibration of a profitability classifier."""
    payload = joblib.load(model_path)
    model = payload.get("model")
    feature_names = payload.get("feature_names", [])

    # Extract features from trades (adjust column names as needed)
    feature_cols = [c for c in trades.columns if c in feature_names]
    X = trades[feature_cols].dropna()
    y = (trades.loc[X.index, "r_multiple"] > 0).astype(int)

    # Get predicted probabilities
    probabilities = model.predict_proba(X)[:, 1]

    # Bin predictions and compare to actuals
    bins = [0.0, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 1.0]
    bin_labels = ["<45%", "45-50%", "50-55%", "55-60%", "60-65%", "65-70%", "70-75%", "75%+"]

    results = []
    for i in range(len(bins) - 1):
        mask = (probabilities >= bins[i]) & (probabilities < bins[i + 1])
        if mask.sum() > 0:
            mean_pred = probabilities[mask].mean()
            mean_actual = y[mask].mean()
            gap = mean_actual - mean_pred
            results.append({
                "bin": bin_labels[i],
                "n_trades": mask.sum(),
                "mean_predicted": mean_pred,
                "actual_win_rate": mean_actual,
                "calibration_gap": gap
            })

    return pd.DataFrame(results)

# Run calibration analysis
trades = pd.read_parquet("data/dvc/processed/training_sets/master_trade_log.parquet")
clf_path = Path("data/dvc/ml/models/profitability_classifier")

for model_file in clf_path.glob("*.pkl"):
    print(f"\n=== {model_file.stem} ===")
    try:
        df = analyze_calibration(model_file, trades)
        print(df.to_string(index=False))

        # Interpretation
        avg_gap = df["calibration_gap"].mean()
        if abs(avg_gap) < 0.03:
            print("\nCalibration: GOOD (gaps < 3%)")
        elif avg_gap > 0:
            print(f"\nCalibration: UNDER-CONFIDENT (actual > predicted by {avg_gap:.1%})")
        else:
            print(f"\nCalibration: OVER-CONFIDENT (predicted > actual by {-avg_gap:.1%})")
    except Exception as e:
        print(f"  Error: {e}")
EOF
```

**Interpretation guide:**
- **Well-calibrated**: `actual_win_rate ≈ mean_predicted` (gaps < 3%)
- **Under-confident**: `actual_win_rate > mean_predicted` (model undersells itself)
- **Over-confident**: `actual_win_rate < mean_predicted` (model oversells itself)

**Why this matters**: For threshold-based gating, calibration affects threshold selection. A poorly calibrated model with good discrimination still works for ranking trades, but the optimal threshold may not be where you expect.

#### Step 1.5: Trade Sequence Dependency Analysis (Markov Chain)

Winning and losing trades are NOT independent. Analyze trade sequences to understand streak patterns.

```bash
poetry run python << 'EOF'
import pandas as pd
import numpy as np
from pathlib import Path

trades = pd.read_parquet("data/dvc/processed/training_sets/master_trade_log.parquet")
trades = trades.sort_values("entry_time")

# Create win/loss sequence
trades["is_win"] = trades["r_multiple"] > 0

# Calculate transition probabilities
def markov_analysis(sequence):
    """Analyze Markov transition probabilities for trade outcomes."""
    transitions = {"WW": 0, "WL": 0, "LW": 0, "LL": 0}

    for i in range(len(sequence) - 1):
        curr = "W" if sequence.iloc[i] else "L"
        next_ = "W" if sequence.iloc[i + 1] else "L"
        transitions[curr + next_] += 1

    # Calculate conditional probabilities
    p_win_given_win = transitions["WW"] / (transitions["WW"] + transitions["WL"]) if (transitions["WW"] + transitions["WL"]) > 0 else 0
    p_win_given_loss = transitions["LW"] / (transitions["LW"] + transitions["LL"]) if (transitions["LW"] + transitions["LL"]) > 0 else 0

    return {
        "P(win|prev_win)": p_win_given_win,
        "P(win|prev_loss)": p_win_given_loss,
        "baseline_win_rate": sequence.mean(),
        "momentum_effect": p_win_given_win - p_win_given_loss
    }

# Analyze by strategy archetype
for archetype in trades["strategy_archetype"].unique():
    arch_trades = trades[trades["strategy_archetype"] == archetype]
    results = markov_analysis(arch_trades["is_win"])

    print(f"\n=== {archetype} ===")
    for key, val in results.items():
        print(f"  {key}: {val:.3f}")

# Key insights:
# - If P(win|prev_win) > P(win|prev_loss): positive momentum (stay aggressive after wins)
# - If P(win|prev_loss) > P(win|prev_win): mean reversion (stay aggressive after losses)
# - If equal: trades are independent (classic assumption holds)
EOF
```

**Implications:**
- If losing streaks cluster, consider pausing after N consecutive losses
- If winning streaks cluster, consider increasing size during winning periods
- Helps estimate realistic max drawdown durations

---

### Phase 1B: Data-Driven Regime Discovery (Before Strategy Selection)

**Critical**: Before defining regimes like "trending" (ADX > 25) or "ranging" (ADX < 20), let the data reveal natural market structure.

#### Step 1B.1: Unsupervised Regime Clustering

Use clustering algorithms to discover natural market regimes from the feature space.

```bash
poetry run python << 'EOF'
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
from pathlib import Path

trades = pd.read_parquet("data/dvc/processed/training_sets/master_trade_log.parquet")

# Extract numeric features from context_at_entry
# Focus on regime-relevant features
regime_features = []
for col in trades.columns:
    if any(x in col for x in ["atr_percentile", "adx", "volatility", "trend"]):
        if trades[col].dtype in [np.float64, np.int64]:
            regime_features.append(col)

X = trades[regime_features].dropna()
X_scaled = StandardScaler().fit_transform(X)

# Try different cluster counts
inertias = []
for k in range(2, 8):
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    kmeans.fit(X_scaled)
    inertias.append(kmeans.inertia_)
    print(f"K={k}: Inertia={kmeans.inertia_:.0f}")

# Elbow plot to find optimal K
plt.figure(figsize=(8, 5))
plt.plot(range(2, 8), inertias, 'bo-')
plt.xlabel('Number of Clusters')
plt.ylabel('Inertia')
plt.title('Elbow Method for Optimal K')
plt.savefig("workspace/research/ml_first_discovery/regime_clusters_elbow.png")

# Use optimal K (e.g., 4)
optimal_k = 4  # Adjust based on elbow
kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
trades_with_clusters = trades.loc[X.index].copy()
trades_with_clusters["cluster"] = kmeans.fit_predict(X_scaled)

# Analyze cluster characteristics
for cluster in range(optimal_k):
    cluster_trades = trades_with_clusters[trades_with_clusters["cluster"] == cluster]
    print(f"\n=== Cluster {cluster} ===")
    print(f"  N trades: {len(cluster_trades)}")
    print(f"  Win rate: {(cluster_trades['r_multiple'] > 0).mean():.1%}")
    print(f"  Avg R-multiple: {cluster_trades['r_multiple'].mean():.3f}")

    # Show mean values of key features
    for feat in regime_features[:5]:
        print(f"  Mean {feat}: {cluster_trades[feat].mean():.2f}")
EOF
```

#### Step 1B.2: Map Strategy Performance to Discovered Clusters

```bash
poetry run python << 'EOF'
import pandas as pd

# Assuming clusters were saved from previous step
trades = pd.read_parquet("workspace/research/ml_first_discovery/trades_with_clusters.parquet")

# Cross-tabulate strategy performance by cluster
print("\n=== Strategy Performance by Cluster ===\n")

for archetype in trades["strategy_archetype"].unique():
    print(f"\n--- {archetype} ---")
    arch_trades = trades[trades["strategy_archetype"] == archetype]

    for cluster in sorted(arch_trades["cluster"].unique()):
        cluster_trades = arch_trades[arch_trades["cluster"] == cluster]
        if len(cluster_trades) < 10:
            continue

        win_rate = (cluster_trades["r_multiple"] > 0).mean()
        avg_r = cluster_trades["r_multiple"].mean()
        n = len(cluster_trades)

        print(f"  Cluster {cluster}: N={n:4d}, WR={win_rate:.1%}, Avg R={avg_r:+.3f}")
EOF
```

**Why this matters**: ADX > 25 is an arbitrary threshold. The market may naturally segment into 4 distinct states, and the optimal strategy routing may differ from naive "trend/range" assumptions.

---

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

#### Step 2.3: Consider Probabilistic Sizing (Alternative to Binary Gating)

Instead of binary take/skip decisions, consider **continuous position sizing based on classifier confidence**:

```python
# Traditional binary gating:
if classifier_probability > threshold:
    take_trade(full_size)

# Probabilistic sizing alternative:
def calculate_position_size(classifier_probability: float, base_size: float) -> float:
    """Scale position size by classifier confidence."""
    if classifier_probability <= 0.5:
        return 0  # No trade below 50%

    # Linear scaling: 50% confidence = 0%, 100% confidence = 100% of base
    confidence_scaling = (classifier_probability - 0.5) * 2
    return base_size * confidence_scaling

# Examples:
# 50% -> 0% of base (no trade)
# 60% -> 20% of base
# 75% -> 50% of base
# 100% -> 100% of base
```

**Advantages of probabilistic sizing:**
- Avoids hard cutoffs that create "cliff effects" at threshold boundaries
- Naturally reduces exposure in uncertain conditions
- Provides smoother equity curves
- No need to optimize a single threshold

**Trade-off**: More complex position management, smaller positions on average.

#### Step 2.4: Backtest with Classifier Gating

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

  # Optional: probabilistic sizing
  # sizing_mode: probabilistic  # or "binary"
  # min_probability: 0.5

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

#### Step 3.2: Choose Ensemble Architecture

There are two main approaches to combining strategies:

**Option A: Regime Router (Rule-Based)**
Route to different strategies based on market conditions.

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

**Option B: Meta-Model Ensemble (ML-Based)**
Train a single model that takes all strategy signals + regime features and learns when to trust which signal.

```python
# Conceptual meta-model approach
class MetaModelEnsemble:
    """
    Instead of hard regime routing, train a meta-model that learns
    which strategy signal to trust based on current market conditions.
    """

    def __init__(self, strategies: list, features: list):
        self.strategies = strategies
        self.meta_model = None  # Trained on historical data

    def predict(self, market_state: dict, strategy_signals: dict) -> dict:
        """
        Inputs:
        - market_state: current feature values (ATR, ADX, etc.)
        - strategy_signals: {strategy_name: signal} from each strategy

        Output:
        - Combined position: weighted average of strategy signals
        """
        # Meta-model outputs weights for each strategy
        features = self._extract_features(market_state, strategy_signals)
        weights = self.meta_model.predict(features)

        # Weighted combination of signals
        combined_signal = sum(
            weights[i] * strategy_signals[s.name]
            for i, s in enumerate(self.strategies)
        )
        return combined_signal
```

**Advantages of Meta-Model:**
- No hard boundaries between regimes (avoids cliff effects)
- Learns complex interactions automatically
- Can adapt to market changes through retraining

**Trade-off**: Requires more data to train well, less interpretable.

#### Step 3.3: Validate Ensemble Performance

Run walk-forward validation on the ensemble:

1. Split data into train/test periods
2. Train regime router on training period
3. Evaluate on test period with metrics focused on:
   - Maximum drawdown duration
   - Equity curve smoothness (Calmar ratio)
   - Consistency across test windows

### Phase 4: Holding Period and Exit Optimization

The document has focused on entry selection. But **exit timing** is equally important for drawdown control.

#### Step 4.1: Analyze Simulated Hold Data

The `post_exit_analysis_simulated_holds` data shows what would have happened if trades were held longer:

```bash
poetry run python << 'EOF'
import pandas as pd
import numpy as np

trades = pd.read_parquet("data/dvc/processed/training_sets/master_trade_log.parquet")

# Examine post-exit analysis columns
pea_cols = [c for c in trades.columns if "post_exit" in c or "simulated_hold" in c]
print("Available post-exit columns:")
for col in pea_cols:
    print(f"  {col}")

# Key questions:
# 1. On winning trades: how much more could we have made?
# 2. On losing trades: did they recover, or get worse?
# 3. What's the optimal holding period?

# Example analysis for stop-loss exits
sl_trades = trades[trades["exit_reason"] == "stop_loss"]
if len(sl_trades) > 0:
    # How many would have recovered if held longer?
    # (Requires simulation data in specific columns)
    pass

# Example analysis for take-profit exits
tp_trades = trades[trades["exit_reason"] == "take_profit"]
if len(tp_trades) > 0:
    # How much profit was left on the table?
    pass
EOF
```

#### Step 4.2: Exit Strategy Optimization

Based on hold analysis, consider:
- **Trailing stops**: Lock in profits as trade moves in favor
- **Time-based exits**: Exit after N bars regardless of price (if analysis shows decay)
- **Partial exits**: Take profit on 50% at first target, trail the rest
- **Behavior-based exits**: Exit when trade isn't behaving as expected (e.g., should be moving but isn't)

### Phase 5: Drawdown-Focused Optimization

The primary constraint is **drawdown duration < 2 weeks**. Optimize for this explicitly.

#### Step 5.1: Define Drawdown Metrics

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

#### Step 5.2: Optimize for Duration, Not Depth

Traditional optimization targets Sharpe or total return. Instead, prioritize:

1. **Primary focus**: Minimize `max_drawdown_duration_days` (target ~14 days, but evaluate in context)
2. **Secondary focus**: Minimize `time_in_drawdown_pct` (target < 40%)
3. **Constraint**: Positive expectancy (R-multiple > 0)

Remember: The goal isn't hitting arbitrary thresholds - it's finding the best achievable balance between drawdown duration and returns.

---

## 5. Success Criteria

A system is successful when it demonstrates strong performance across these dimensions. These are **guidelines for evaluation**, not hard pass/fail thresholds.

### Primary Goal: Minimize Drawdown Duration
The core objective is minimizing how long the strategy stays in drawdown. Evaluate against:
- **Target**: ~2 weeks (14 days) max drawdown duration
- **Acceptable**: Up to 3-4 weeks if returns justify it
- **Context matters**: Compare against baseline strategy without ML filtering

**Key insight**: A strategy with 20-day max drawdown but 2x the returns of a 14-day max drawdown strategy may be the better choice. The goal is optimal risk/reward, not arbitrary thresholds.

### Profitability Criteria
- **Positive Total PnL** over full backtest period (required)
- **Time in Drawdown < 50%** of total period (guideline)
- **Profit Factor > 1.1** (indicates edge exists)

### Consistency Indicators
- **Win Rate > 40%** (varies by strategy type - trend following often lower)
- **Average R-Multiple > 0** (positive expectancy)
- **Sharpe Ratio > 0.3** (basic risk-adjusted returns)

### Robustness Criteria
- **Walk-Forward: >50% profitable windows** (shows generalization)
- **Performance degradation < 50%** (in-sample vs out-of-sample)
- **No catastrophic losing periods** (single window shouldn't wipe out gains)

### Reality Check
Before finalizing, ask:
1. Are these results realistic given transaction costs and slippage?
2. Would I actually trade this with real money?
3. How does this compare to simply holding the instrument?

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

### Calibration Analysis Template

```markdown
# Phase 1.4: Classifier Calibration Analysis

## Date: YYYY-MM-DD

## Classifier Analyzed: [e.g., 15min_trend_following]

## Reliability Diagram Results

| Predicted Probability Bin | Actual Win Rate | N Trades | Calibration Gap |
|---------------------------|-----------------|----------|-----------------|
| 0.50-0.55 | | | |
| 0.55-0.60 | | | |
| 0.60-0.65 | | | |
| 0.65-0.70 | | | |
| 0.70-0.75 | | | |
| 0.75+ | | | |

## Calibration Assessment
- [ ] Well-calibrated (predicted ≈ actual)
- [ ] Under-confident (actual > predicted)
- [ ] Over-confident (actual < predicted)

## Implications for Threshold Selection
-
-
```

### Trade Dependency Analysis Template

```markdown
# Phase 1.5: Trade Sequence Analysis

## Date: YYYY-MM-DD

## Markov Transition Probabilities

| Archetype | P(win\|prev_win) | P(win\|prev_loss) | Baseline WR | Momentum Effect |
|-----------|------------------|-------------------|-------------|-----------------|
| trend_following | | | | |
| mean_reversion | | | | |

## Interpretation
- [ ] Trades are independent (momentum ≈ 0)
- [ ] Positive momentum (stay aggressive after wins)
- [ ] Negative momentum (consider pausing after losses)

## Implications for Risk Management
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

## Selected Approach
- [ ] Binary gating at threshold X.XX
- [ ] Probabilistic sizing (50% → 0%, scaled to 100%)

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

## Ensemble Architecture
- [ ] Regime Router (rule-based)
- [ ] Meta-Model Ensemble (ML-based)

## Regime Router Configuration (if applicable)
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
- [ ] Ensemble outperforms single strategies on risk-adjusted basis
- [ ] Max DD duration is acceptable (target ~14 days, evaluate in context)
- [ ] Robust across walk-forward windows
- [ ] Returns justify the drawdown characteristics
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

### Pitfall 6: Treating Trades as Independent
The Markov analysis in Phase 1.5 may reveal that trades cluster. Ignoring this can lead to:
- Underestimating worst-case losing streaks
- Missing opportunities to pause during adverse sequences
- Incorrect position sizing assumptions

### Pitfall 7: Hard Regime Boundaries
ADX > 25 vs ADX < 25 creates a boundary where a tiny change flips the entire strategy. Consider:
- Unsupervised clustering to find natural boundaries
- Probabilistic sizing instead of binary decisions
- Meta-model ensembles that blend strategies smoothly

### Pitfall 8: Ignoring Calibration
If your classifier says 70% and actual win rate is 55%, your threshold selection is based on wrong assumptions. Always check calibration before threshold optimization.

---

## 8. Future Considerations

### Survivorship Bias in Feature Analysis
Currently, the trained models were fit on trades that were taken on all signals, so there's no survivorship bias. However, if future iterations introduce additional filtering logic before trade execution, be aware that:
- Feature importance will only reflect what mattered *for trades that happened*
- Signals that were filtered out won't inform the model
- Consider re-training on *all signals* (not just executed trades) if filtering is added

---

## 9. Next Steps After Discovery

Once a successful system is found:

1. **Paper Trade**: Run in simulation for 2-4 weeks minimum
2. **Monitor Predictions**: Track classifier accuracy on live data
3. **Gradual Deployment**: Start with small position sizes
4. **Continuous Learning**: Retrain models monthly with new data
5. **Regime Monitoring**: Track if market regimes have shifted

---

## 10. Key Commands Reference

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

## 11. Summary

This ML-first approach differs from previous methodologies by:

1. **Starting with model insights** instead of manual analysis
2. **Discovering regimes via clustering** before defining them manually
3. **Analyzing classifier calibration** before threshold selection
4. **Understanding trade dependencies** (Markov analysis) for realistic drawdown estimates
5. **Using classifier probability** for entry gating (binary or probabilistic sizing)
6. **Optimizing for drawdown duration** instead of Sharpe/returns
7. **Combining strategies** via regime routing or meta-model ensembles
8. **Analyzing exit timing** using simulated hold data
9. **Leveraging lookahead analysis** (diagnostic models) for offline insights

The infrastructure exists. The models are trained. The task is to extract their knowledge and translate it into actionable trading rules.
