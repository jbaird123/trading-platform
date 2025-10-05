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
- **Status:** Requires strategy-specific optimization

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

**❌ REJECTED:**
1. **EMA Blackout Policy** (Iteration 007A)
   - Hypothesis: Use proven EMA blackout (06-08, 10-11, 13-17)
   - Result: -80% PnL (catastrophic failure!)
   - Lesson: **DIFFERENT STRATEGIES NEED DIFFERENT REGIMES**
   - Critical: Blocked Hour 18 which is SuperTrend's best hour

#### Pending Research
- Custom blackout policy for SuperTrend-specific time profile
- Volatility filters (if any)
- Signal quality filters (ADX, RSI, etc.)
- Exit optimization (currently uses same 30/60 pips as EMA)

#### Key Differentiators from EMA

| Aspect | EMA Crossover | SuperTrend |
|--------|---------------|------------|
| **Signal Type** | Lagging | Earlier/Adaptive |
| **Best Hour** | 13 (+$364) | 18 (+$1,623) |
| **Worst Hour** | 9 (-$257) | 15 (-$1,494) |
| **Trade Count** | 494 (sparse) | 1,822 (active) |
| **Raw PnL** | $205 (weak) | $2,091 (10x better) |
| **Blackout Effect** | +1626% ✅ | -80% ❌ |

#### Multi-Strategy Considerations
- **Complement With:** EMA crossover (different time-of-day profiles!)
  - SuperTrend trades Hour 18 (Asian evening) profitably
  - EMA trades Hours 13-17 (London/NY overlap) profitably
  - Minimal overlap/competition for the same opportunities
- **Portfolio Potential:** HIGH (complementary regime preferences)
- **Next Steps:** Optimize SuperTrend independently, then combine

#### Critical Insight
**SuperTrend performs in DIFFERENT market conditions than EMA crossover.** This makes them excellent candidates for a multi-strategy portfolio:
- SuperTrend: More active, earlier entries, profitable in Asian evening
- EMA: More selective, confirmed trends, profitable in London/NY sessions
- Combined: Could provide more consistent equity curve across all sessions

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

- **2025-10-05 v1.0:** Initial catalog creation
  - Documented EMA Crossover findings (Iterations 001-006)
  - Documented SuperTrend baseline findings (Iteration 007)
  - Created indicator effectiveness matrix
  - Established failed hypothesis log
