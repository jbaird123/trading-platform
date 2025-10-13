# Re-Export Instructions for EMA Crossover Strategy

## Context

We discovered that the original export was using the wrong execution model. TradingView was executing trades at the **next bar close** instead of the **next bar open**.

We've updated the PineScript strategy to explicitly set:
- `process_orders_on_close=false` → Execute at next bar open (not close)
- `calc_on_order_fills=false` → No recalculation on fills
- `calc_on_every_tick=false` → Only calculate on bar close

This should result in more realistic execution prices (next bar open).

## Steps to Re-Export

### 1. Update PineScript Strategy in TradingView

Copy the updated strategy from:
```
configs/golden_strategies/ema_crossover/strategy.pine
```

Paste into TradingView Pine Editor and save.

### 2. Apply Strategy to Chart

- Symbol: OANDA:EURUSD
- Timeframe: 1H
- Date range: Keep as wide as possible (TradingView will show full available history)

### 3. Verify Execution Model

Check the **first trade** to verify it's using next bar open:

**Expected behavior:**
- EMA crossover detected at: 2023-01-06 14:00 EST bar close
- Entry should execute at: 2023-01-06 15:00 EST bar **OPEN** = **1.06456**

**Previous (wrong) behavior:**
- Entry was at: 2023-01-06 15:00 EST bar **CLOSE** = 1.06463

**How to check:**
1. Click on the first trade marker on the chart
2. Note the entry price
3. Compare to the bar's open price (should match)

If the entry price is **1.06456**, the execution model is correct!
If the entry price is still **1.06463**, TradingView may be ignoring the script settings.

### 4. Export Data (Same as Before)

#### A. Export Trades List
1. Open Strategy Tester tab
2. Click "List of Trades"
3. Export to CSV
4. Save as: `trades_reexport.csv` (temporary name for comparison)

#### B. Export OHLCV Data
1. Right-click on chart
2. "Export chart data..."
3. Select date range to match or exceed the trades range
4. Include "Indicator Values" (to get EMA values)
5. Save as: `ohlcv_reexport.csv`

### 5. Compare Results

Before overwriting the old data, let's compare:

**Key metrics to check:**
- Total trades: Should still be 243 (same signals)
- First trade entry price: Should be **1.06456** (not 1.06463)
- First trade entry time: Should show 2023-01-06 **16:00** EST (but this is actually the 15:00 bar due to TV's 1-hour offset quirk)

**Price differences:**
- With next bar open execution, prices should be more realistic
- Entry/exit prices should better match our platform's capability

### 6. What to Report Back

Please report:
1. ✅ First trade entry price: _______ (expecting 1.06456)
2. ✅ First trade entry time in CSV: _______ (expecting 16:00 EST)
3. ✅ Total number of closed trades: _______ (expecting 243)
4. ✅ Net profit: _______ (will differ from before due to different execution prices)

If the entry price is **1.06456**, we're good to proceed!
If it's still **1.06463**, we need to investigate TradingView's settings further.

## Next Steps After Re-Export

Once you confirm the execution prices look correct:
1. We'll replace the old data with the new export
2. Update metadata.json with new metrics
3. Re-run validation tests
4. Expect much smaller (or zero) price differences between platform and TradingView

## Notes

- The number of trades should remain 243 (same entry signals)
- Only the **execution prices** should change
- Total PnL will change slightly due to better execution prices
- This is more realistic for live trading simulation
