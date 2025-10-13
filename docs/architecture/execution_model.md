# Execution Model Architecture

## Overview

The execution model architecture defines the separation of concerns between the Backtester (execution timing) and Portfolio Manager (state tracking and decision-making). This design allows for flexible execution timing while maintaining clean separation of responsibilities.

### Key Design Principles

1. **Decision vs Execution Separation**: Portfolio Manager makes decisions about when trades _should_ occur, Backtester decides _when_ they actually execute
2. **Action Descriptors**: Components return structured dictionaries describing desired actions, not direct execution
3. **Configurable Execution Timing**: Same strategy code works with different execution models (realistic vs legacy)
4. **Stateless Decisions**: Portfolio Manager decisions are pure functions of current state + signal

## Action Descriptors

Action descriptors are dictionary objects returned by Portfolio Manager and Risk Exit Manager to communicate desired actions without executing them directly.

### Portfolio Manager Action Descriptors

**Open Entry Window**:
```python
{
    'action': 'open_entry_window',
    'side': 'long',  # or 'short'
    'bar_index': 42
}
```

**Should Close (Exit)**:
```python
{
    'action': 'should_close',
    'reason': 'signal',  # or 'opposite_signal' for flips
    'entry_side': 'short'  # Only present for flip scenarios
}
```

**No Action**:
```python
{
    'action': 'no_action',
    'reason': 'no_position'  # or 'already_in_position', 'wrong_side'
}
```

**Window Active**:
```python
{
    'action': 'window_active',
    'side': 'long'
}
```

### Risk Exit Manager Action Descriptors

**Should Close (Risk Exit)**:
```python
{
    'action': 'should_close',
    'reason': 'stop_loss',  # or 'take_profit'
    'exit_price': 1.23456  # Calculated exit price
}
```

**No Exit**:
```python
None  # REM returns None when no exit is triggered
```

## Execution Models

### current_bar_close (Legacy/Unrealistic)

**Behavior**: Executes trades immediately at the signal bar's close price.

**Characteristics**:
- **Unrealistic**: Assumes you can act on information and execute at the same bar's close
- **Look-ahead bias**: Implicitly uses future information (the close price is only known after bar completes)
- **Use case**: Rapid prototyping, quick strategy iterations

**Execution Flow**:
```
Bar N:
  1. Signal: enter_long
  2. PM returns: {'action': 'open_entry_window', 'side': 'long'}
  3. Backtester immediately executes: create_position(price=bar_N_close)
```

### next_bar_open (Realistic/Industry Standard)

**Behavior**: Defers trade execution to the next bar's open price.

**Characteristics**:
- **Realistic**: Matches how trades execute in live markets (signal on bar N, execute on bar N+1)
- **TradingView compatible**: Matches TradingView's strategy.entry/strategy.close behavior
- **No look-ahead bias**: Uses only information available when the bar closes
- **Use case**: Production strategies, golden validation, realistic backtesting

**Execution Flow**:
```
Bar N:
  1. Signal: enter_long
  2. PM returns: {'action': 'open_entry_window', 'side': 'long'}
  3. Backtester stores: pending_entry = {...}

Bar N+1:
  1. Backtester executes pending_entry: create_position(price=bar_N+1_open)
```

## Four-Phase Execution Order

The Backtester processes each bar in four phases to ensure correct execution order:

### Phase 1: Execute Pending Exit

If a pending exit exists from the previous bar (deferred in `next_bar_open` mode):
1. Close the position at current bar's open price
2. For flip scenarios: open entry window for opposite side
3. Clear `pending_exit`

### Phase 2: Execute Pending Entry

If a pending entry exists from the previous bar:
1. Create new position at current bar's open price
2. Update entry window to mark entry as completed
3. Clear `pending_entry`

### Phase 3: Check REM Exits

If a position exists, check for risk-based exits (stop-loss, take-profit):
1. Call `REM.check_exits_intrabar(position, current_bar)`
2. If exit triggered:
   - `current_bar_close`: Execute immediately and `continue`
   - `next_bar_open`: Store in `pending_exit` and `continue`

### Phase 4: Process Strategy Command

Process the strategy signal for the current bar:
1. Call `PM.process_command(signal, ...)`
2. If action is `should_close`:
   - `current_bar_close`: Execute immediately
   - `next_bar_open`: Store in `pending_exit`
3. If action is `open_entry_window` or `window_active`:
   - Check RMM gating and position caps
   - If allowed:
     - `current_bar_close`: Execute immediately
     - `next_bar_open`: Store in `pending_entry`

## Same-Bar Flips

A "flip" occurs when the strategy signals an entry in the opposite direction while a position is open (e.g., enter_short while long position is open).

### Flip Execution with next_bar_open

**Example**: Long position open, bar 5 signals enter_short

```
Bar 5:
  Phase 4: PM.process_command('enter_short')
  Returns: {'action': 'should_close', 'reason': 'opposite_signal', 'entry_side': 'short'}
  Backtester stores: pending_exit = {reason: 'opposite_signal', entry_side: 'short'}

Bar 6:
  Phase 1:
    - Close long position at bar 6 open
    - Call PM.complete_pending_exit_and_open_entry_window('short', 6)
    - Create pending_entry for short position
  Phase 2:
    - Create short position at bar 6 open (same bar as exit!)
```

**Key Insight**: Both the exit and entry execute at bar 6's open price, achieving a same-bar flip at the next available execution point.

## State Management

### Entry Windows

Entry windows track when entry signals are "active" and available for execution:

**Structure**:
```python
_entry_windows = {
    'long': (start_bar_index, last_entered_bar_index),
    'short': (start_bar_index, last_entered_bar_index)
}
```

- `start_bar_index`: Bar where entry command was received
- `last_entered_bar_index`: Bar where position was created (None if window still open)

**Lifecycle**:
1. Signal received → Open window: `(bar_N, None)`
2. Position created → Close window: `(bar_N, bar_M)`
3. Window expires after `entry_window_bars` → Close window: `(-1, None)`

### Pending Exit Flag

The `_pending_exit` flag in Portfolio Manager indicates that an exit has been requested but not yet completed:

- Set to `True` when flip scenario occurs (opposite entry signal while positioned)
- Cleared when `complete_pending_exit_and_open_entry_window()` is called
- Prevents entry window from opening until exit completes

## TradingView Timestamp Convention

### The Difference

**TradingView Convention**: Labels bars with their CLOSE time (end of bar)
**Our Platform Convention**: Labels bars with their OPEN time (start of bar)

### Example

A 1-hour bar from 17:00-18:00 UTC:
- **Our platform labels it**: `17:00` (bar open time)
- **TradingView labels it**: `18:00` (bar close time)

Both systems execute at the bar's open price, but the timestamp labels differ by the bar's duration.

### Golden Validation Adjustment

When comparing trades with TradingView exports, we subtract 1 hour (for 1H bars) from TradingView timestamps to align the labels:

```python
tv_timestamp = pd.to_datetime(tv_export_time)
adjusted_timestamp = tv_timestamp - timedelta(hours=1)  # Align with our convention
```

For other timeframes, adjust accordingly (e.g., -4 hours for 4H bars).

## Testing Strategy

### Unit Tests

- **Portfolio Manager Tests**: Verify action descriptors are returned correctly for all scenarios
- **REM Tests**: Verify exit descriptors are returned with correct prices
- **Backtester Tests**: Verify execution phases run in correct order

### Integration Tests

- **Execution Model Integration**: Test complete flow with both execution models (`test_execution_model_integration.py`)
- **Same-Bar Flip**: Verify flips execute both exit and entry at same bar's open
- **Deferred Execution**: Verify next_bar_open defers entries and exits correctly

### Golden Validation Tests

- **Trade Count**: Platform trade count matches TradingView
- **Trade Timing**: Entry/exit times match exactly (after timestamp adjustment)
- **Trade PnL**: PnL values match within tight tolerance
- **Equity Curve**: High correlation (r > 0.995) between platform and TradingView equity curves

## Migration Guide

### For Existing Strategies

To migrate an existing strategy to use the realistic `next_bar_open` execution model:

1. **Update run_config.yaml**:
   ```yaml
   execution_model: "next_bar_open"  # Add this line
   ```

2. **Review trade counts**: The first backtest run may show fewer trades if the strategy had end-of-backtest positions

3. **Adjust expectations**: Entry/exit prices will shift from bar close to next bar open

4. **Validate results**: Compare with TradingView or paper trading results to verify accuracy

### For Live Trading

The same Portfolio Manager code works in live trading:
- Portfolio Manager returns action descriptors
- Execution Layer (not Backtester) handles real broker integration
- `next_bar_open` behavior maps naturally to "submit order when bar closes, execute when next bar opens"

## Force-Close Behavior

When a backtest ends with an open position:
- The position is automatically closed at the last bar's close price
- Exit reason is set to `"end_of_data"`
- For golden validation, these force-closed trades are excluded from comparison (TradingView leaves positions open)

### Trade Count Considerations

**TradingView Behavior:**
- Shows "total_trades" (includes open positions as separate entries)
- Reports "closed_trades" in GUI (excludes open positions)
- Exports open positions with confusing "Exit X" label but "Open" status

**Our Platform Behavior:**
- Creates all trades including those that remain open at end
- Force-closes open positions with `exit_reason="end_of_data"`
- For golden validation: filters out force-closed trades to match TradingView's closed_trades count

**Golden Metadata Structure:**
```json
{
  "total_trades": 244,      // All trades including open positions
  "closed_trades": 243,      // Trades that closed naturally (compare against this)
  "open_trades": 1           // Positions still open at end of backtest
}
```

## Future Enhancements

Potential execution model improvements:
- **Intrabar execution**: Execute at specific intrabar prices (e.g., when stop is hit mid-bar)
- **Slippage models**: Simulate realistic price slippage based on liquidity
- **Partial fills**: Model scenarios where large orders fill across multiple bars
- **Market vs Limit orders**: Different execution models for different order types
