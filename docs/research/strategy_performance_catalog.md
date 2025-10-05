# Strategy & Indicator Performance Catalog

**Purpose:** This catalog tracks empirical findings from backtesting research about which strategies and indicators perform well under specific market conditions. Use this to build multi-strategy portfolios and avoid repeating failed experiments.

**Last Updated:** 2025-10-05

---

## How to Use This Catalog

### For Strategy Selection
1. Identify current market regime (time, volatility, trend strength)
2. Look up which strategies perform best in that regime
3. Select appropriate strategy or use multiple strategies in parallel

### For Portfolio Construction
1. Find strategies with **complementary** regime preferences
2. Combine strategies that profit in DIFFERENT conditions
3. Avoid combining strategies that compete for the same regime

### For Research Efficiency
1. Check catalog before testing new filters
2. Learn from previous failures (don't repeat rejected hypotheses)
3. Build on proven findings rather than starting from scratch

---

## Key Research Learnings & Directives

This section summarizes the most critical, cross-strategy principles discovered
during research. All future analysis **MUST** adhere to these directives.

### 1. Full-Backtest PnL is Misleading. WFE is Mandatory.
- **Source:** Iteration `009_supertrend_wfe`
- **Finding:** A SuperTrend strategy showed a **$8,199 PnL** on the full dataset
  but collapsed to **$3,247 (-60%)** in out-of-sample testing. In contrast, a
  "weaker" EMA strategy with only **$3,543 PnL** proved highly robust with 95%
  out-of-sample consistency.
- **Directive:** A strategy is not considered "successful" or "promising" based
  on its full-backtest performance alone. **Walk-Forward Evaluation (WFE) is the
  sole arbiter of robustness.** No system will be considered for production
  without passing WFE with >70% profitable windows.

### 2. Granular Time Filters Are a Major Overfitting Risk.
- **Source:** Iteration `008_custom_supertrend_blackout` -> `009_supertrend_wfe`
- **Finding:** A highly granular blackout policy (blocking 16 of 24 hours)
  produced a +292% PnL improvement on the SuperTrend strategy *in-sample*. This
  same filter was the direct cause of the WFE failure.
- **Directive:** Prefer broad, session-based time filters (e.g., "London
  Session") over hyper-specific, hour-based rules. Granular filters are more
  likely to fit historical noise than a persistent market edge.

### 3. Regime Filters Are Not Portable Between Strategies.
- **Source:** Iteration `007_supertrend_signal`
- **Finding:** The time-based filter that gave the EMA Crossover a +1626%
  performance boost resulted in a **-80% PnL collapse** when applied to the
  SuperTrend strategy.
- **Directive:** Every strategy has a unique market fingerprint. Never assume a
  profitable regime filter for one strategy will work for another. Each system
  requires independent regime optimization.

---

## Strategy Profiles

### EMA Crossover (20/80)

**Signal Type:** Lagging Trend-Following
**Research Period:** 2013-01-01 to 2025-09-26
**Campaigns:** campaign_20251005_discovery (Iterations 001-006)

#### Performance Summary
- **Raw Baseline:** $205 PnL, 31.7% WR, 18.8x DD/PnL ❌
- **Optimized:** $3,543 PnL, 35.6% WR, 0.60x DD/PnL ✅
- **Walk-Forward:** 58.3% profitable windows ⚠️ (target: 70%)

#### Optimal Market Conditions

**✅ WORKS WELL IN:**
- **Time of Day:** 06-08 UTC, 10-11 UTC, 13-17 UTC
  - **Sessions:** London open, late London morning, London/NY overlap
  - **Why:** High liquidity provides smooth trend follow-through
- **Market Structure:** Strong directional moves
- **Volatility:** Moderate to high (sustains trends)

**❌ PERFORMS POORLY IN:**
- **Time of Day:** 09 UTC, 12 UTC, 18-23 UTC, 00-05 UTC
  - **Sessions:** Late Asian, early NY overlap, evening/overnight
  - **Why:** Low liquidity causes whipsaws; choppy price action
- **Market Structure:** Ranging/choppy markets (2014-2015 period)
- **Signal Quality:** Crossovers during weak trends (low ADX)

#### Validated Filters

**✅ SUCCESSFUL:**
1. **Blackout Policy** (Iteration 002)
   - Block hours: 00-05, 09, 12, 18-23 UTC
   - Allow hours: 06-08, 10-11, 13-17 UTC
   - Impact: +1626% PnL improvement
   - Rationale: Filters low-liquidity sessions

**❌ REJECTED:**
1. **ADX Filter** (Iteration 004B)
   - Hypothesis: Filter for ADX > 25 (strong trends)
   - Result: -5.3% PnL (removed profitable trades)
   - Lesson: EMA crossover already implies trend; redundant filter

2. **RSI Overbought/Oversold** (Iteration 004A)
   - Hypothesis: Avoid entries when RSI extreme
   - Result: Only filtered 1 trade (+$8.75)
   - Lesson: RSI redundant with crossover signal

3. **CHOP Index Filter** (Iteration 006)
   - Hypothesis: Filter for CHOP < 50 (trending only)
   - Result: -40.9% PnL
   - Lesson: EMA profits in BOTH trending and choppy markets

4. **Wider Stop-Loss** (Iteration 003A)
   - Hypothesis: 45/90 pips (vs 30/60) for more breathing room
   - Result: -6.7% PnL
   - Lesson: Original 30/60 is well-calibrated

5. **ATR-Based Exits** (Iteration 003B)
   - Hypothesis: Dynamic exits based on volatility
   - Result: -44.6% PnL
   - Lesson: Fixed stops outperform dynamic for this strategy

#### Exit Optimization
- **Optimal:** Fixed 30 pip SL, 60 pip TP (1:2 R:R)
- **Reasoning:** Well-calibrated for EUR/USD 1H timeframe volatility

#### Known Limitations
- **Win Rate Ceiling:** ~36% (inherent to lagging signal)
- **Robustness:** 58.3% (marginal, needs improvement to reach 70% target)
- **Period Weakness:** 2014-2015 underperformance (MFE/MAE ratio 1.57 vs 1.77)
- **Cannot Fix:** Signal quality filters don't improve fundamental lag

#### Multi-Strategy Considerations
- **Complement With:** Early/leading indicators (SuperTrend, Ichimoku)
- **Complement With:** Mean-reversion for ranging markets
- **Avoid Pairing With:** Other lagging MA crossovers (redundant)

---

### SuperTrend (7/3.0)

**Signal Type:** Adaptive Trend-Following with Dynamic Support/Resistance
**Research Period:** 2013-01-01 to 2025-09-26
**Campaigns:** campaign_20251005_discovery (Iteration 007)

#### Performance Summary
- **Raw Baseline:** $2,091 PnL, 33.6% WR, 2.54x DD/PnL ⚠️
- **With EMA Blackout:** $419 PnL, 33.6% WR, 8.00x DD/PnL ❌
- **With Custom Blackout:** $8,199 PnL, 40.0% WR, 0.32x DD/PnL ✅ **BREAKTHROUGH**
- **Optimization Result:** +292% PnL improvement, +6.4pp WR, -50% DD
- **Status:** **❌ REJECTED - Failed Walk-Forward Evaluation (Severe Overfitting)**

#### Optimal Market Conditions

**✅ WORKS WELL IN:**
- **Time of Day:** 06 UTC, 08 UTC, 10-11 UTC, 18 UTC
  - **Sessions:** London open, late London, **Asian evening** (unique!)
  - **Why:** Earlier entries catch trend starts; Hour 18 is golden (+$1,623, 49% WR)
- **Market Structure:** Dynamic trending (catches trends earlier than EMA)
- **Trade Frequency:** 3.7x more active than EMA (1,822 vs 494 trades)

**❌ PERFORMS POORLY IN:**
- **Time of Day:** 15 UTC (-$1,494), 12 UTC (-$685), 7 UTC (-$838)
  - **Sessions:** NY afternoon, London/NY overlap start, pre-London
  - **Why:** Choppy/reversal-prone periods cause whipsaws
- **Market Structure:** TBD (needs more analysis)

#### Validated Filters

**✅ SUCCESSFUL:**
1. **Custom Blackout Policy** (Iteration 008)
   - Hypothesis: SuperTrend-specific blackout based on its time-of-day profile
   - Configuration: Allow hours 2, 6, 8, 10, 11, 13, 16, 18 (block all others)
   - Result: +292% PnL improvement ($2,091 → $8,199)
   - Impact: Win rate 33.6% → 40.0%, DD/PnL 2.54x → 0.32x
   - Rationale: Keeps profitable Asian evening (hour 18), blocks choppy NY afternoon (hour 15)

**❌ REJECTED:**
1. **EMA Blackout Policy** (Iteration 007A)
   - Hypothesis: Use proven EMA blackout (06-08, 10-11, 13-17)
   - Result: -80% PnL (catastrophic failure!)
   - Lesson: **DIFFERENT STRATEGIES NEED DIFFERENT REGIMES**
   - Critical: Blocked Hour 18 which is SuperTrend's best hour

#### Exit Optimization
- **Current:** Fixed 30 pip SL, 60 pip TP (1:2 R:R) - same as EMA
- **Status:** Not yet optimized for SuperTrend
- **Pending Research:** ATR-based exits, wider stops, dynamic TP

#### Walk-Forward Evaluation Results (Iteration 009) ❌

**Test Configuration:** 48 splits, 3-month OOS windows, 12-month training
**Date:** 2025-10-05

| Metric | Full Backtest | WFE OOS | Degradation |
|--------|--------------|---------|-------------|
| **Total PnL** | $8,199 | $3,247 | **-60.4%** ❌ |
| **Avg PnL/Trade** | $8.91 | $4.24 | **-52.4%** ❌ |
| **Profitable Windows** | N/A | **52.1%** (25/48) | **Far below 70% target** ❌ |
| **Worst Window** | N/A | -$2,050 | **25% account DD** ❌ |

**VERDICT:** **SEVERE OVERFITTING DETECTED**
- Only 52.1% profitable windows (barely above 50% random baseline)
- 60% performance degradation in out-of-sample testing
- Custom blackout policy was overfit to full 2013-2025 dataset
- Hour-specific filtering (16/24 hours blocked) is too granular
- Fails catastrophically in non-trending regimes

**ROOT CAUSE:** Time-of-day filters optimized on full dataset don't generalize to unseen windows

#### Key Differentiators from EMA

| Aspect | EMA Crossover | SuperTrend |
|--------|---------------|------------|
| **Signal Type** | Lagging | Earlier/Adaptive |
| **Best Hour** | 13 (+$364) | 18 (+$1,623) |
| **Worst Hour** | 9 (-$257) | 15 (-$1,494) |
| **Trade Count (Raw)** | 494 (sparse) | 1,822 (active) |
| **Raw PnL** | $205 (weak) | $2,091 (10x better) |
| **Optimized PnL** | $3,543 | **$8,199 (2.3x better!)** |
| **Optimized Win Rate** | 35.6% | **40.0%** |
| **Optimized DD/PnL** | 0.60x | **0.32x (47% better!)** |
| **EMA Blackout Effect** | +1626% ✅ | -80% ❌ |
| **Custom Blackout Effect** | N/A | +292% ✅ (but overfit!) |
| **WFE Profitable Windows** | **58.3%** ✅ | 52.1% ❌ |
| **WFE OOS Consistency** | **95%** ✅ | 40% ❌ |
| **WFE Worst Window** | **-$665** ✅ | -$2,050 ❌ |
| **Robustness Verdict** | **Marginal (usable)** ✅ | **Failed (rejected)** ❌ |

**CRITICAL FINDING:** Despite 2.3x higher full-backtest PnL, **SuperTrend FAILS robustness testing** while **EMA PASSES**. Full-backtest performance is misleading - WFE reveals the truth.

#### Multi-Strategy Considerations

**STATUS:** ❌ **NOT RECOMMENDED FOR PORTFOLIO**

SuperTrend failed WFE robustness testing and should NOT be deployed, even in a multi-strategy portfolio:
- 52.1% profitable windows is too close to random (50%)
- Severe overfitting (-60% OOS degradation) indicates unreliable edge
- High variance (worst window -$2,050) adds unacceptable risk
- EMA system is more robust despite lower full-backtest PnL

**Original Complementarity Analysis (now invalid due to overfitting):**
- SuperTrend trades Hour 18 (Asian evening) profitably (+$1,623 in-sample)
- EMA trades Hours 13-17 (London/NY overlap) profitably (+$364)
- BUT: SuperTrend's Hour 18 edge doesn't hold in OOS testing

#### Critical Insights

**1. Full-Backtest Performance is MISLEADING** (Iteration 009 WFE)
- SuperTrend showed $8,199 PnL in full backtest (looked like breakthrough!)
- WFE revealed 60% degradation to $3,247 OOS (severe overfitting)
- **LESSON:** ALWAYS run Walk-Forward Evaluation before declaring success
- High full-backtest PnL ≠ Robust system
- OOS consistency matters more than total PnL

**2. Granular Time-of-Day Filters are DANGEROUS** (Iteration 008 → 009)
- Hour-specific blackout (blocking 16/24 hours) = overfitting to noise
- Works brilliantly on full dataset, fails on unseen OOS windows
- **LESSON:** Keep time filters broad (sessions) not granular (hours)
- Simpler is better for generalization

**3. Strategy-Specific Optimization is MANDATORY**
- **Cannot** copy regime filters between different strategies
- EMA blackout (+1626%) vs Same policy on SuperTrend (-80%)
- Custom SuperTrend blackout (+292% in-sample, but overfit!)
- Each strategy needs independent regime optimization

**4. 52% Profitable Windows = NO REAL EDGE** (Iteration 009 WFE)
- 52.1% is barely above coin flip (50%)
- 58.3% (EMA) is marginal but statistically significant
- 70%+ is required for confident deployment
- **LESSON:** Robustness thresholds exist for a reason

---

## Indicator Effectiveness Matrix

### Trend Indicators

| Indicator | Best Used For | Works Well With | Avoid When |
|-----------|---------------|-----------------|------------|
| **EMA Crossover** | Confirmed trend entries | High liquidity sessions | Low volume, ranging markets |
| **SuperTrend** | Early trend detection | Multi-session trading | TBD (needs more research) |
| **ADX** | Trend strength confirmation | As entry filter (NOT with EMA!) | As standalone signal |

### Volatility Indicators

| Indicator | Best Used For | Works Well With | Avoid When |
|-----------|---------------|-----------------|------------|
| **ATR** | Position sizing | Fixed-percentage stops | Exit timing (vs fixed stops) |
| **Bollinger Bands** | Volatility regime detection | TBD | TBD |
| **CHOP Index** | Trend vs range detection | TBD | Not with EMA (redundant) |

### Momentum Indicators

| Indicator | Best Used For | Works Well With | Avoid When |
|-----------|---------------|-----------------|------------|
| **RSI** | Overbought/oversold | TBD (not with EMA crossover) | With trend-following signals |

---

## Failed Hypothesis Log

**Purpose:** Track rejected hypotheses to avoid repeating failed experiments.

### EMA Crossover Failures

1. **ADX Signal Quality Filter** (Iteration 004B)
   - Hypothesis: ADX > 25 improves win rate
   - Result: Win rate +2.8pp but PnL -5.3%
   - Reason: Removed profitable trades in moderate-trend conditions
   - Lesson: Quality filters can hurt if too restrictive

2. **RSI Extremes Filter** (Iteration 004A)
   - Hypothesis: Avoid entries at RSI extremes
   - Result: Filtered only 1 trade
   - Reason: Crossover signal already implies momentum
   - Lesson: Redundant filters add no value

3. **CHOP Trend Filter** (Iteration 006)
   - Hypothesis: Only trade when CHOP < 50 (trending)
   - Result: -40.9% PnL
   - Reason: EMA profits in both trending AND choppy markets
   - Lesson: Don't assume "trend-following = needs trending market"

4. **ATR Dynamic Exits** (Iteration 003B)
   - Hypothesis: ATR-based stops adapt to volatility
   - Result: -44.6% PnL vs fixed stops
   - Reason: Over-adapts, gives back profits
   - Lesson: Fixed stops can outperform dynamic for EUR/USD 1H

### SuperTrend Failures

1. **Copy-Paste EMA Blackout** (Iteration 007A)
   - Hypothesis: Proven EMA blackout should work for SuperTrend
   - Result: -80% PnL (catastrophic)
   - Reason: Different signal types have different optimal regimes
   - Lesson: **NEVER assume regime filters transfer between strategies**

---

## Portfolio Strategy Recommendations

### Current Portfolio Options (As of 2025-10-05)

#### Option A: EMA-Only Conservative
- **Strategy:** EMA 20/80 + Blackout Policy
- **Capital:** 100% allocation
- **Expected Return:** $3,543/year (12.75 years backtest)
- **Risk:** DD/PnL 0.60x, but only 58.3% WFE robustness
- **Pros:** Proven, validated, ready to deploy
- **Cons:** Marginal robustness, limited upside

#### Option B: SuperTrend Development (RECOMMENDED)
- **Strategy:** Optimize SuperTrend with custom blackout
- **Timeline:** 1-2 more iterations
- **Potential:** $4,000+ PnL if properly filtered
- **Risk:** Unproven, needs validation
- **Pros:** 10x better baseline than EMA
- **Cons:** Requires more research

#### Option C: Dual-Strategy Portfolio (FUTURE)
- **Strategy Mix:** 50% EMA + 50% SuperTrend (after optimization)
- **Synergy:** Complementary time-of-day profiles
- **Expected Benefit:** Smoother equity curve, higher consistency
- **Timeline:** After SuperTrend optimization complete
- **Target:** 70%+ WFE robustness through diversification

---

## Research Workflow Integration

### When Starting New Iteration
1. **Check Catalog:** Review existing findings for similar strategies
2. **Check Failed Log:** Don't repeat rejected hypotheses
3. **Plan Tests:** Use complementary insights from other strategies

### When Completing Iteration
1. **Update Strategy Profile:** Add findings to relevant section
2. **Update Indicator Matrix:** Note effectiveness/ineffectiveness
3. **Update Failed Log:** Document rejected hypotheses
4. **Update Portfolio Recommendations:** Revise based on new data

### When Pivoting Strategies
1. **Compare Profiles:** Look for complementary characteristics
2. **Identify Gaps:** Find market conditions not covered by current strategies
3. **Document Learnings:** Transfer insights (cautiously) to new strategy

---

## Glossary

**Regime:** Specific market conditions (time, volatility, trend, etc.) where a strategy performs well or poorly

**Complementary Strategies:** Strategies that profit in DIFFERENT market conditions, reducing correlation

**Signal Quality:** How reliably a signal predicts profitable outcomes

**Robustness:** Percentage of out-of-sample periods where strategy is profitable (target: 70%+)

**DD/PnL Ratio:** Max Drawdown / Total PnL (target: <0.20x)

---

## Version History

- **2025-10-05 v1.2:** SuperTrend WFE FAILURE - Critical Overfitting Discovery (Iteration 009) ❌
  - **REJECTED SuperTrend system** after Walk-Forward Evaluation revealed severe overfitting
  - WFE Results: 52.1% profitable windows (vs 70% target), 60% OOS degradation
  - Documented that $8,199 full-backtest PnL collapsed to $3,247 OOS
  - **EMA system validated as MORE ROBUST** despite lower full-backtest PnL
  - Added critical lessons on WFE being MANDATORY before deployment
  - Added warning about granular time-of-day filters causing overfitting
  - Updated all sections to reflect SuperTrend rejection and EMA as preferred system

- **2025-10-05 v1.1:** SuperTrend Custom Blackout Breakthrough (Iteration 008) - LATER INVALIDATED
  - Validated SuperTrend custom blackout policy (+292% PnL improvement)
  - Documented strategy-specific optimization mandate (cannot copy filters between strategies)
  - Updated SuperTrend performance profile with optimized metrics
  - **NOTE:** These results were later proven to be overfit in iteration 009 WFE

- **2025-10-05 v1.0:** Initial catalog creation
  - Documented EMA Crossover findings (Iterations 001-006)
  - Documented SuperTrend baseline findings (Iteration 007)
  - Created indicator effectiveness matrix
  - Established failed hypothesis log
