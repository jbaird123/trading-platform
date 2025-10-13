# Execution Model Analysis - EMA Crossover Strategy

## Problem Discovery

When comparing platform backtests to TradingView exports, we found:
- **Trade count**: Perfect match (243 trades)
- **Entry/exit times**: 1-2 hour differences due to timezone parsing
- **Entry/exit prices**: 56 trades had small differences (0.1 to $3 PnL impact)
- **Total PnL difference**: -$98.20 ($100 tolerance)

Initial hypothesis: Small data precision differences.

## Root Cause Analysis

### Investigation Steps

1. **Verified EMA calculations**: Perfect match between platform and TradingView
2. **Checked crossover timing**: EMA crossover detected at identical bars
3. **Analyzed execution prices**: Found systematic 1-bar execution lag

### Key Finding: Execution Model Mismatch

**Example: First Trade (Long entry)**

| System | Crossover Detected | Execution Bar | Execution Price | Price Used |
|--------|-------------------|---------------|-----------------|------------|
| EMA Crossover | 2023-01-06 14:00 EST close | - | - | Fast > Slow |
| Platform | ✓ | 14:00 EST | 14:00 EST close | **1.06456** |
| TradingView (original) | ✓ | 15:00 EST | 15:00 EST close | **1.06463** |
| Expected (corrected) | ✓ | 15:00 EST | 15:00 EST **open** | **1.06456** |

**The issue:** TradingView was executing at next bar **close**, not next bar **open**.

### Why This Matters

**Current bar close execution (platform):**
- ❌ Unrealistic - can't know the close price until bar is finished
- ❌ Optimistic - assumes perfect timing
- ❌ Not achievable in live trading

**Next bar close execution (TradingView original):**
- ⚠️ More realistic than current bar close
- ⚠️ Still slightly optimistic - order fills mid-bar
- ⚠️ Better than current bar, but not ideal

**Next bar open execution (correct model):**
- ✅ Realistic - signal detected at bar close, order placed
- ✅ Order fills at next bar open (first available price)
- ✅ Achievable in live trading
- ✅ Industry standard for backtesting

## Solution

### 1. PineScript Changes

Updated `strategy.pine` to explicitly set execution model:

```pinescript
strategy("EMA Crossover Golden",
         overlay=true,
         initial_capital=100000,
         default_qty_value=10000,
         commission_type=strategy.commission.percent,
         commission_value=0.0,
         pyramiding=1,
         process_orders_on_close=false,  // Execute at next bar open
         calc_on_order_fills=false,       // No recalc on fills
         calc_on_every_tick=false)        // Only calc on bar close
```

**Key parameters:**
- `process_orders_on_close=false`: Default behavior, fills at next bar **open**
- `calc_on_order_fills=false`: Prevents multiple calculations per bar
- `calc_on_every_tick=false`: Only calculate on bar close (not every tick)

### 2. Platform Changes (Planned)

Our platform currently executes at **current bar close** (line 420 in core.py):
```python
entry_price = current_bar["close"]  # Current implementation
```

**Proposed change:** Execute at **next bar open**
- Detect signal at current bar close
- Mark pending entry
- Execute at next bar's open price

**YAML Configuration (Planned):**
```yaml
execution:
  model: "next_bar_open"  # Options: "current_bar_close", "next_bar_open", "next_bar_close"
```

This allows strategies to declare their execution model explicitly.

## Expected Impact After Re-Export

### Price Alignment

With TradingView using next bar open (1.06456) and platform using next bar open (1.06456):
- ✅ Entry prices should match perfectly
- ✅ Exit prices should match perfectly
- ✅ PnL should match within rounding errors only

### Validation Test Results

**Before correction:**
- Trade count: 243 ✓
- Timing differences: 1-2 hours (timezone)
- Price differences: 56 trades (small)
- Total PnL diff: -$98.20

**After correction (expected):**
- Trade count: 243 ✓
- Timing differences: 0-1 hours (DST only)
- Price differences: 0-5 trades (rounding only)
- Total PnL diff: <$10

## Documentation for Future Strategies

### Execution Model Options

When setting up a new golden strategy, specify execution model:

**1. Next Bar Open (Recommended - Most Realistic)**
- TradingView: `process_orders_on_close=false`
- Platform: `execution.model: "next_bar_open"`
- Use case: All strategies for live trading

**2. Next Bar Close**
- TradingView: Custom logic needed
- Platform: `execution.model: "next_bar_close"`
- Use case: Research/comparison only

**3. Current Bar Close (Not Recommended)**
- TradingView: `process_orders_on_close=true`
- Platform: Current default behavior
- Use case: Legacy strategies only (overly optimistic)

### Best Practices

1. **Always use next bar open** for realistic backtests
2. **Match execution models** between platform and TradingView
3. **Document execution model** in strategy YAML
4. **Test with small tolerances** (< 0.01% price diff expected)
5. **Account for timezone differences** in validation tests

## References

- TradingView Docs: [Strategies Execution Model](https://www.tradingview.com/pine-script-docs/concepts/strategies/)
- TradingView Docs: [Strategy Properties](https://www.tradingview.com/support/solutions/43000628599-strategy-properties/)
- Our validation tests: `tests/validation/test_strategy_validation.py`
- Backtester core: `src/trading_platform/backtester/core.py:420`
