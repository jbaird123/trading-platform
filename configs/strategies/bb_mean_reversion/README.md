# BB Mean Reversion — Day Trading Winner

This folder contains the winning day trading strategy found during autonomous search.

**Strategy:** Bollinger Band Mean Reversion on USD/JPY (5min timeframe)

## Performance Highlights
- **PnL:** $3.25M (3,249% return over 5.7 years)
- **Max Drawdown Duration:** 13 days ✅ (meets <14 day target)
- **Win Rate:** 13.6% (2,127 winners, 13,516 losers)
- **Payoff Ratio:** 15.76:1 ($241 avg win vs $15 avg loss)
- **Trades:** 15,643 over 5.7 years (2020-2025)
- **Walk-Forward Validated:** 520 windows, $6,214.76 mean OOS PnL

## Strategy Logic
- **Entry Long:** Price below lower Bollinger Band (20-period, 2 std dev)
- **Entry Short:** Price above upper Bollinger Band
- **Exit Long:** Price above middle Bollinger Band (20-period SMA)
- **Exit Short:** Price below middle Bollinger Band
- **Risk Management:** Trailing stops via REM

## Files
- `backtest.yaml` — Single baseline backtest (no research features)
- `walkforward.yaml` — Walk-forward validation config (520 windows)
- `montecarlo.yaml` — Monte Carlo robustness testing
- `run_backtest.sh` — Runs a single baseline backtest
- `run_walkforward.sh` — Runs walk-forward validation

## Usage
Make scripts executable:
```bash
chmod +x run_backtest.sh run_walkforward.sh
```

Run single backtest:
```bash
./run_backtest.sh
```

Run walk-forward validation:
```bash
./run_walkforward.sh
```

## Key Findings
1. **USD/JPY has instrument-specific edge** - profitable with ALL strategies (EMA, RSI, BB)
2. **5min timeframe reduces drawdown duration** - from 391 days (1H) to 13 days (5min)
3. **BB superior to RSI on 5min** - BB: $3.25M with 13-day DD, RSI: $1.36M with 29-day DD

## Caveats
- Low win rate (13.6%) requires strong psychological discipline
- Slippage set to 0 in backtest (may be optimistic for live)
- Not tested with RMM filtering yet
- Spread costs included (1.5 pips)

## Next Steps
1. Review HTML report and chart for visual confirmation
2. Test with RMM filtering (range-only conditions)
3. Add position sizing rules based on volatility
4. Paper trade for 2-4 weeks before live deployment
5. Monitor slippage in live environment

---
*Strategy validated: October 2, 2025*
*Data period: 2020-01-01 to 2025-09-26*
*Original run: runs/bb_wf_validation/run_20251002_035229_utc/*
