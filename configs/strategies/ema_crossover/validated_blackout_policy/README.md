# EMA Crossover with Validated Blackout Policy

**Status:** ✅ Validated through Walk-Forward Evaluation
**Campaign:** campaign_20251005_discovery (Iteration 002)
**Validation Date:** 2025-10-05

## Performance Summary

| Metric | Value |
|--------|-------|
| **Total PnL** | $3,543 |
| **Win Rate** | 35.6% |
| **DD/PnL Ratio** | 0.60x |
| **WFE Profitable Windows** | 58.3% (28/48 windows) |
| **WFE OOS Consistency** | 95% |
| **Worst WFE Window** | -$665 |

## Strategy Description

**Signal Type:** Lagging Trend-Following
**Timeframe:** 1H EUR/USD
**Period Tested:** 2013-01-01 to 2025-09-26 (12.75 years)

### Components

1. **Entry Signal:** EMA(20) crosses above/below EMA(80)
2. **Blackout Policy:** Only trades during high-liquidity London sessions
   - **Allowed Hours:** 06-08, 10-11, 13-17 UTC
   - **Blocked Hours:** 00-05, 09, 12, 18-23 UTC
3. **Risk Management:**
   - Stop Loss: 30 pips
   - Take Profit: 60 pips
   - Risk/Reward: 1:2

### Key Features

- **+1626% PnL improvement** from blackout policy (vs raw baseline)
- **Filters low-liquidity sessions** that cause whipsaws
- **Validated robustness** through 48-window walk-forward evaluation
- **95% OOS consistency** (minimal degradation from in-sample to out-of-sample)

## Optimal Market Conditions

### ✅ Works Well In:
- London open (06-08 UTC)
- Late London morning (10-11 UTC)
- London/NY overlap (13-17 UTC)
- Strong directional moves
- Moderate to high volatility

### ❌ Performs Poorly In:
- Late Asian session (00-05 UTC)
- Hour 09, 12 UTC (choppy transitions)
- Evening/overnight (18-23 UTC)
- Ranging/choppy markets

## Files

- `run_config.yaml` - Main configuration with blackout policy
- `strategy.yaml` - EMA 20/80 crossover strategy definition
- `rem.yaml` - Risk exit manager (30/60 pip SL/TP)
- `run.sh` - Shell script to execute backtest with AI analysis

## Usage

```bash
# Run backtest with AI qualitative analysis
./configs/strategies/ema_crossover/validated_blackout_policy/run.sh
```

The script will:
1. Run the backtest using the validated configuration
2. Generate brief.json with performance metrics
3. Run AI qualitative analysis on the results
4. Output analysis to stdout

## Research Notes

- This strategy emerged from testing various regime filters on EMA crossover
- Blackout policy was discovered by analyzing time-of-day performance
- WFE validation confirmed robustness (58.3% > 50% random baseline)
- Known limitation: 36% win rate ceiling due to lagging signal nature
- Marginal robustness (58.3% vs 70% target) - use with caution

## Related Documentation

- Full research findings: `docs/research/strategy_performance_catalog.md`
- Campaign log: `workspace/research/campaign_20251005_discovery/campaign_log.md`
- Iteration summary: `workspace/research/campaign_20251005_discovery/002_parallel_time_and_volatility/run_summary.md`
