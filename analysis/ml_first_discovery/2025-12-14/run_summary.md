# ML-First Strategy Discovery Analysis
## Date: 2025-12-14

---

## CRITICAL UPDATE: Analysis Corrections

The initial analysis contained **three critical flaws** that produced misleading results:

| Flaw | What We Did Wrong | Impact |
|------|-------------------|--------|
| **Diagnostic Models** | Used models with 509 features including `context_at_exit_*`, `sim_hold_*`, `bars_held` | Indirect lookahead - these features aren't available at entry time |
| **In-Sample Evaluation** | Evaluated on 2018-2021 data (model training period) | Measured memorization, not predictive ability |
| **Outcome Selection** | Selected trades by actual r_multiple quintile | Pure lookahead - "D4+ gating" selected winners by definition |

**Result of flaws**: Reported "100% win rate, zero drawdown, 11x improvement" - IMPOSSIBLE in reality.

**Corrected analysis** (Script: `12_corrected_classifier_evaluation.py`):
- Uses `profitability_classifier` models (46 entry-time features only)
- Evaluates ONLY on out-of-sample data (2022-2023)
- Uses actual classifier predictions, not outcomes

---

## Executive Summary (CORRECTED)

After correcting for lookahead bias and in-sample evaluation:

1. **Classifiers have near-zero predictive power** on out-of-sample data
2. **Regressors show ~0 correlation** between predicted and actual R-multiples
3. **Mean Reversion base strategy** remains modestly profitable (61.5% WR, 0.075 avg R)
4. **Trend Following base strategy** is near break-even (31.5% WR, 0.002 avg R)
5. **ML gating provides minimal lift** (~0.01 R improvement at best)

---

## Corrected Results (Out-of-Sample: 2022-2023)

### Script: `12_corrected_classifier_evaluation.py`
### Output: `artifacts/corrected_classifier_evaluation.csv`

### Classifier Performance

| Model | Baseline WR | Baseline Avg R | Best Gated Avg R | Lift |
|-------|-------------|----------------|------------------|------|
| 5min_trend_following | 31.5% | 0.0019 | 0.0025 | **+0.0006** |
| 15min_trend_following | 31.5% | 0.0019 | 0.0115 | **+0.0096** |

**Note**: Only 2 classifier models exist (both trend_following). No mean_reversion classifiers.

### Regressor Predictive Power

| Model | Pred vs Actual Correlation |
|-------|----------------------------|
| 15min_mean_reversion | -0.005 |
| 1D_mean_reversion | -0.008 |
| 5min_trend_following | 0.015 |
| 15min_trend_following | -0.012 |
| 4H_trend_following | 0.018 |

**Interpretation**: Correlations near zero mean models have **no predictive power** on new data.

### Base Strategy Performance (Out-of-Sample)

| Archetype | N Trades | Win Rate | Avg R | Max DD |
|-----------|----------|----------|-------|--------|
| Mean Reversion | 88,926 | 61.5% | 0.0753 | -470 R |
| Trend Following | 66,600 | 31.5% | 0.0019 | -935 R |

---

## What Happened to the "Amazing" Results?

### Previous Claims vs Reality

| Metric | Previous (WRONG) | Corrected (REAL) |
|--------|------------------|------------------|
| MR D4+ Win Rate | 100% | N/A (no classifier) |
| TF D8+ Win Rate | 100% | 31.4% |
| Combined Total R | 217,893 | ~6,700 (MR) + ~125 (TF) |
| Max Drawdown | 0.00 R | -470 R (MR), -935 R (TF) |
| Improvement | "11x baseline" | **<5% improvement** |

### Why Previous Results Were Wrong

1. **Outcome-based selection is circular**:
   ```python
   # WRONG: This selects trades that ENDED UP as winners
   good_trades = trades[trades["r_multiple_decile"] >= 4]
   # Of course win rate is 100% - you selected by outcome!
   ```

2. **Diagnostic models leak future info**:
   - `context_at_exit_*` = market state when trade closed
   - `bars_held` = how long trade lasted
   - `exit_reason` = why trade closed
   - These aren't knowable at entry time!

3. **In-sample evaluation measures memorization**:
   - Model trained on 2018-2021
   - Evaluating on same data shows what model "remembers"
   - NOT what it can predict on new data

---

## Valid Findings (Still Useful)

Despite the classifier issues, some analysis remains valid:

### 1. Base Strategy Comparison
**Script**: `08_ensemble_strategy_analysis.py` (baseline numbers only)

| Strategy | Trades | Win Rate | Avg R |
|----------|--------|----------|-------|
| Mean Reversion | 268,733 | 61.8% | 0.0795 |
| Trend Following | 202,156 | 31.3% | -0.0087 |

**Mean Reversion is clearly superior** - this finding stands.

### 2. Volatility Regime Patterns
**Script**: `03_regime_correlation_analysis.py`

Mean Reversion performance by ATR percentile:

| Regime | Win Rate | Avg R |
|--------|----------|-------|
| Very Low (0-25) | 62.4% | 0.088 |
| Low (25-50) | **63.4%** | **0.120** |
| High (50-75) | 62.1% | 0.079 |
| Very High (75-100) | 59.5% | 0.041 |

**MR performs best in low-medium volatility** - this pattern is real.

### 3. Holding Period Patterns
**Script**: `09_holding_period_exit_analysis.py`

| Archetype | Winners Avg Hold | Losers Avg Hold | Difference |
|-----------|------------------|-----------------|------------|
| Mean Reversion | 7.9 bars | 12.9 bars | -5.0 bars |
| Trend Following | 27.5 bars | 7.8 bars | +19.6 bars |

**Exit timing matters differently by strategy type** - valid insight.

### 4. Trade Independence (Markov Analysis)
**Script**: `05_markov_sequence_analysis.py`

| Metric | Mean Reversion | Trend Following |
|--------|----------------|-----------------|
| P(Win\|Win) | 60.8% | 34.0% |
| P(Win\|Loss) | 61.4% | 30.3% |
| Momentum Effect | -0.6% | +3.7% |

**Trades are roughly independent** - no strong clustering.

---

## Recommendations

### 1. Don't Rely on Current ML Models for Gating
The profitability classifiers show no predictive power on out-of-sample data. Either:
- Retrain with different features/architecture
- Investigate why models don't generalize
- Use simpler rule-based filters instead

### 2. Focus on Mean Reversion
Mean Reversion has genuine edge (61.5% WR, 0.075 avg R) without ML gating. Trend Following is near break-even.

### 3. Consider Regime-Based Position Sizing
Instead of binary gating, scale position size based on volatility regime:
- Low ATR (25-50): Full size (best MR performance)
- Very High ATR (75-100): Reduced size (weakest MR performance)

### 4. Investigate Model Generalization Failure
Questions to explore:
- Is training data too different from test period (2022-2023)?
- Are features not predictive, or is model architecture wrong?
- Would simpler models (logistic regression) perform better?

---

## Scripts Reference

| Script | Purpose | Status |
|--------|---------|--------|
| 01_feature_importance_analysis.py | Diagnostic model feature importance | **FLAWED** - uses lookahead model |
| 01b_entry_feature_importance.py | Entry-time feature importance | **FLAWED** - uses lookahead model |
| 02_quintile_trade_analysis.py | Q0 vs Q4 comparison | **PARTIALLY VALID** - patterns may be real but based on lookahead data |
| 03_regime_correlation_analysis.py | ATR regime analysis | **VALID** - no ML involved |
| 04_classifier_calibration_analysis.py | Classifier metrics | **FLAWED** - in-sample evaluation |
| 05_markov_sequence_analysis.py | Trade sequence analysis | **VALID** - no ML involved |
| 06_regime_discovery_clustering.py | K-means regime discovery | **VALID** - unsupervised, no lookahead |
| 07_classifier_gating_simulation.py | Gating simulation | **FLAWED** - outcome-based selection |
| 08_ensemble_strategy_analysis.py | Strategy comparison | **FLAWED** - outcome-based selection |
| 09_holding_period_exit_analysis.py | Holding period analysis | **VALID** - no lookahead |
| 10_drawdown_optimization.py | Drawdown analysis | **FLAWED** - outcome-based selection |
| 11_realistic_gating_simulation.py | Imperfect classifier sim | **INFORMATIVE** - shows theoretical bounds |
| 12_corrected_classifier_evaluation.py | **CORRECT** out-of-sample eval | **VALID** - proper methodology |

---

## Lessons Learned

1. **Always check for lookahead bias** - any feature derived from trade outcome is suspect
2. **Always use out-of-sample evaluation** - in-sample results are meaningless for prediction
3. **Verify model features** - diagnostic models have different features than production models
4. **Question "too good" results** - 100% win rate and zero drawdown should trigger skepticism
5. **Document model training periods** - essential for proper train/test splits

---

## Methodology Updates

The methodology document (`docs/ai_prompts/methodology/07_ml_first_strategy_discovery.md`) has been updated with:
- **Section 2**: Clarified model types and lookahead risks
- **Pitfall 11**: In-sample evaluation warning
- **Pitfall 12**: Outcome-based selection warning

These updates will prevent future analyses from making the same mistakes.
