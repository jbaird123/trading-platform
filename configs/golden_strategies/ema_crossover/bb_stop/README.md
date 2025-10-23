# EMA Crossover with Bollinger Stop

This variation keeps the EMA 20/50 crossover entries from the baseline run
but manages exits using the Bollinger lower/upper bands. The stop is anchored
at the active band with a small canonical offset (0.0005) to account for
trading costs. Use this variation to validate indicator-based exits that rely
on prior-bar calculations and 1-minute zoom verification.

## TradingView Export Checklist
- Load the generated `strategy.pine` script in TradingView.
- Chart: EUR/USD 1H, timezone `UTC (Reykjavik)`.
- Date range: 2022-12-01 → 2024-12-31 (warmup + validation).
- Export trades (`Strategy Tester → List of Trades → Export`).
- Export OHLCV (`Chart → ... → Export chart data`).
- Save files into `data/dvc/golden/strategies/ema_crossover/bb_stop/`.

After exporting, run:
```bash
poetry run python tests/validation/validate_golden_data.py \
  --strategy ema_crossover/bb_stop
```

## Platform Backtest
Once the TradingView data is in place, generate the platform golden trades:
```bash
poetry run python tests/validation/generate_golden_trades.py
```

Track the new data with DVC and commit the generated `.dvc` file alongside the
updated configs.
