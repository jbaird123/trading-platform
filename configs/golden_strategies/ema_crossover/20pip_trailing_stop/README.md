# EMA Crossover - 20pip Trailing Stop Loss

This is a golden validation strategy variant that tests **trailing stop-loss** functionality.

## Strategy Overview

- **Entry Signal**: EMA(9) crosses above/below EMA(21)
- **Exit Logic**: 20-pip trailing stop loss
- **Position Size**: $10,000 per trade
- **Execution Model**: Next bar open (matches TradingView)

## Key Differences from Baseline

This variant adds a **trailing stop loss** that:
- Starts 20 pips away from entry price
- Trails (moves favorably) as price moves in profitable direction
- Never moves against you (stop only tightens, never loosens)
- For longs: Stop moves up as price rises, but stays fixed if price falls
- For shorts: Stop moves down as price falls, but stays fixed if price rises

## Configuration Files

- `strategy.yaml`: Strategy configuration (EMA parameters)
- `rem.yaml`: Risk & Exit Manager configuration with trailing stop
- `run_config.yaml`: Backtest run configuration
- `strategy.pine`: TradingView PineScript implementation

## TradingView Export Instructions

### CRITICAL: Warmup Period Requirements

**Use exactly 1 month of warmup data before validation range starts.**

For 2023-01-01 validation start:
- Export from: **2022-12-01**
- Validate from: **2023-01-01** onwards

Why 1 month for hourly data:
- EMA(21) needs ~60+ bars minimum
- EMA(9) needs ~27+ bars minimum
- Buffer for indicator stabilization
- **100 bars is NOT sufficient** for perfect golden validation

### Export Settings (TradingView)

1. **Date Range**:
   - Start: 2022-12-01 (1 month warmup for 2023-01-01 validation start)
   - End: 2024-12-31

2. **Strategy Settings**:
   - Initial Capital: $100,000
   - Position Size: $10,000 (cash per order)
   - Commission: 0%
   - Slippage: 0
   - Fast EMA Length: 9
   - Slow EMA Length: 21
   - Trailing Stop: 20 pips

3. **Chart Settings**:
   - Symbol: OANDA:EURUSD
   - Timeframe: 1 hour
   - Timezone: UTC (Reykjavik)

4. **Indicator Export**:
   - Add strategy to chart
   - Export OHLCV data with EMA columns:
     - Export Chart Data → Include all visible indicators
     - Columns: time, open, high, low, close, ema_9, ema_21
     - Save as: `ohlcv.csv`

5. **Trade Export**:
   - View Strategy Tester → List of Trades
   - Export all trades (both entry and exit rows)
   - Save as: `trades.csv`

### Import to Platform

After exporting from TradingView:

1. **Review Files First**:
   - Check CSV format and encoding (should be UTF-8)
   - Verify date ranges match expected values
   - Ensure OHLCV has EMA columns

2. **Move to DVC Folder**:
   ```bash
   # Place files in:
   data/dvc/golden/strategies/ema_crossover/20pip_trailing_stop/
   ```

3. **Create Metadata**:
   Create `metadata.json` with:
   - Strategy name and variant
   - Date ranges (export start and validation start)
   - Trade counts (total and validation range)
   - Trailing stop configuration (20 pips)
   - Notes about warmup period

4. **Add to DVC**:
   ```bash
   dvc add data/dvc/golden/strategies/ema_crossover
   dvc push
   git add data/dvc/golden/strategies/ema_crossover.dvc
   git commit -m "Add 20pip trailing stop golden validation data"
   ```

## Validation Tests

The test suite validates:

1. **Trade Count**: Platform generates same number of trades as TradingView
2. **Entry Times**: All entry times match exactly
3. **Entry Prices**: All entry prices match (tolerance: 0.00001)
4. **Exit Times**: All exit times match exactly
5. **Exit Prices**: All exit prices match (tolerance: 0.00001)
6. **Metadata**: Proper validation range configuration

## Known Limitations

### Trailing Stop Behavior

**Platform (RiskExitManager)**:
- Tracks peak/trough prices intra-bar
- Updates trailing stop based on actual price movement
- Can exit mid-bar when trailing stop is hit

**TradingView (Historical Backtesting)**:
- Cannot track intra-bar trailing stop updates
- Applies trailing logic at bar close
- May show different exit prices for volatile bars

### Expected Edge Cases

Expect potential mismatches in trades where:
1. **Volatile bars**: Large intra-bar moves that hit trailing stop mid-bar
2. **Fast reversals**: Price moves favorably then reverses within same bar
3. **Gap moves**: Large gaps between bars that skip over trailing stop levels

These are **fundamental limitations** of TradingView's historical backtesting with trailing stops, not bugs in either system.

## Testing

Run the validation tests:

```bash
pytest tests/validation/test_strategy_validation.py::test_ema_crossover_20pip_trailing_stop_* -v
```

All tests should pass with known edge cases properly documented.

## References

- [BT-7] Validates backtester execution model matches TradingView
- [SE-3] Risk & Exit Manager with trailing stop functionality
- [TV-1] Golden validation framework for strategy testing
