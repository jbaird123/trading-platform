# ML-First Strategy Discovery - Run Summary

**Branch**: 2025-12-14-ml-first-strategy-discovery
**Started**: 2025-12-14
**Status**: ✅ COMPLETE

---

## Executive Summary

This research followed the ML-First Strategy Discovery methodology to analyze 685,906 trades and discover optimal trading rules. Key findings:

1. **Mean Reversion in Low Volatility** is the recommended strategy (WR=45.2%, Avg R=0.098)
2. **Trade sequences are NOT independent** - losses cluster heavily (23% momentum effect)
3. **Volatility-based routing** improves Avg R by +0.019 (45% lift)
4. **Current drawdown duration is ~9 days** (below the 14-day target)

---

## Phase 1.1: Feature Importance Analysis

### Key Findings

| Models | Avg Importance | Feature |
|--------|---------------|---------|
| 10/10 | 0.0069 | `context_at_entry_risk_initial_risk_ccy` |
| 5/10 | 0.0023 | `hour_of_day` |
| 4/10 | 0.0032 | `context_at_entry_global_features_15min_atr_14` |
| 4/10 | 0.0030 | `context_at_entry_global_features_15min_atr_pct` |

**Observations**:
1. Initial Risk (position sizing) is #1 predictive feature across ALL models
2. ATR-based volatility features dominate
3. Hour of Day matters for intraday timeframes

---

## Phase 1.2: Quintile Trade Analysis

- **Total trades**: 685,906
- **Q0 (worst 20%)**: Avg R = -1.401
- **Q4 (best 20%)**: Avg R = +1.703

### Strategy-Specific Insights

**Mean Reversion**: Winners have LOW ATR percentile
**Trend Following**: Winners have HIGH ATR percentile

**Critical Insight**: Mean reversion and trend following have OPPOSITE volatility preferences!

---

## Phase 1.3: Regime Correlation Analysis

### Volatility Regime (ATR Percentile)

| Strategy | Best Regime | Win Rate | Avg R |
|----------|-------------|----------|-------|
| Mean Reversion | Low Vol | 46.0% | 0.131 |
| Trend Following | High Vol | 22.8% | 0.020 |

### Session Distribution

Best session: **Asia-London overlap** (WR=34.4%, Avg R=0.052)

---

## Phase 1.4: Classifier Threshold Recommendations

| Context | Threshold | Win Rate | Coverage |
|---------|-----------|----------|----------|
| 5min_trend_following | 0.53 | 35.4% | 30.9% |
| 15min_trend_following | 0.53 | 35.4% | 30.9% |
| 5min_mean_reversion | 0.60 | 69.6% | 1.0% |

---

## Phase 1.5: Trade Sequence Dependency (Markov Analysis)

### CRITICAL FINDING: Strong Positive Momentum

| Metric | Value |
|--------|-------|
| P(win\|prev_win) | 49.0% |
| P(win\|prev_loss) | 25.6% |
| **Momentum effect** | **+23.3%** |
| Max loss streak | **131 trades** |
| Expected (if independent) | 33 trades |

**Implication**: Trades cluster. After a loss, only 25.6% chance of winning. Consider pausing after consecutive losses.

---

## Phase 1B: Data-Driven Regime Discovery

Using K-Means clustering with K=4:

**Mean Reversion**: Best in Cluster 1 (Avg R=0.134)
- HIGH RSI slope, HIGH BB width percentile, LOW range_atr_ratio

**Trend Following**: Best in Cluster 0 (Avg R=0.018)
- HIGH ATR percentile, HIGH BB width, LOW 4H RSI slope

---

## Phase 2: Classifier-Based Entry Gating

### Volatility-Based Gating Results

| Gating Rule | Coverage | Win Rate | Avg R | Lift |
|-------------|----------|----------|-------|------|
| Baseline (all) | 100% | 33.4% | 0.042 | - |
| Vol Routing | 54.9% | 35.2% | 0.062 | +0.020 |

---

## Phase 3: Multi-Strategy Ensemble

### Regime Routing Effectiveness

| Strategy | Favorable Regime | WR Lift | R Lift |
|----------|-----------------|---------|--------|
| Mean Reversion | ATR pct < 50 | +0.6% | +0.018 |
| Trend Following | ATR pct > 50 | +0.9% | +0.007 |

**Combined lift**: WR +2.2%, Avg R +0.019

---

## Phase 4: Holding Period & Exit Analysis

### Exit Reason Analysis

| Exit Reason | N Trades | Win Rate | Avg R |
|-------------|----------|----------|-------|
| opposite_signal | 256,997 | 35.8% | 0.301 |
| stop-loss | 213,859 | 28.3% | -0.270 |

### Strategy-Specific Exit Insights

**Mean Reversion**:
- 84.9% exit on opposite signal (Avg R=0.459)
- Holding longer HURTS performance (R change = -0.080)

**Trend Following**:
- 50.3% exit on stop-loss (Avg R=0.116)
- Holding longer HELPS slightly (R change = +0.010)

---

## Phase 5: Drawdown-Focused Optimization

### Baseline Drawdown Metrics

| Metric | Value |
|--------|-------|
| Max Drawdown | -355.4R |
| Max DD Duration | 37 trades (~9 days) |
| Time in Drawdown | 66.8% |

### Gating Strategy Comparison

| Strategy | DD Duration | Time in DD | Avg R | Coverage |
|----------|-------------|------------|-------|----------|
| **mr_only_low_vol** | 33 trades | 64.0% | **0.098** | 27.3% |
| vol_routing_tight | 33 trades | 65.3% | 0.061 | 36.0% |
| vol_routing | 33 trades | 65.5% | 0.061 | 45.5% |
| baseline | 37 trades | 66.8% | 0.042 | 100% |

### RECOMMENDED STRATEGY: Mean Reversion Only in Low Volatility

- **Filter**: `strategy_archetype == 'mean_reversion' AND ATR_percentile < 50`
- **Max DD Duration**: 33 trades
- **Time in Drawdown**: 64.0%
- **Win Rate**: 45.2%
- **Avg R-multiple**: 0.098
- **Coverage**: 27.3%

---

## Key Findings Summary

### 1. Volatility-Based Strategy Routing is Essential
Mean reversion and trend following require OPPOSITE market conditions.

### 2. Trade Sequences are Highly Dependent
Losses cluster (max 131 consecutive). Consider position sizing rules after consecutive losses.

### 3. Mean Reversion Outperforms in Current Data
With low-vol gating: WR=45.2%, Avg R=0.098 (2.3x baseline)

### 4. Exit Timing Differs by Strategy
- Mean reversion: Exit on signal reversal (don't hold longer)
- Trend following: Stops are valuable; can hold slightly longer

### 5. Drawdown Target is Achievable
Current max DD duration ~9 days (below 14-day target)

---

## Artifacts Generated

| File | Description |
|------|-------------|
| `feature_importances.csv` | Full diagnostic model feature importances |
| `feature_importances_entry_only.csv` | Entry-time features only |
| `quintile_comparison.csv` | Q0 vs Q4 feature comparison |
| `calibration_analysis.csv` | Classifier calibration by probability bin |
| `markov_analysis.csv` | Trade sequence transition probabilities |
| `trades_with_clusters.csv` | Regime cluster assignments |
| `ensemble_trades.parquet` | Regime-matched trades for validation |

---

## Next Steps

1. **Validate on out-of-sample data** - Run walk-forward validation
2. **Wire gating into RMM config** - Implement ATR percentile < 50 filter for MR
3. **Add loss-streak pause rule** - Reduce size after 3+ consecutive losses
4. **Paper trade** - Run 2-4 weeks in simulation before live deployment
5. **Monitor regime shifts** - Track if volatility regime distribution changes

---
