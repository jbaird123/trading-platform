# ADR 001: Command-Based Signal Architecture

## Status
Accepted (2025-09-30)

## Context

The original architecture used state-based signals where strategies output "long", "short", or "flat" to indicate the desired position at each bar. This created several problems:

1. **Ambiguity**: Does "long" mean "enter long now" or "I want to be long"?
2. **Signal Duration Confusion**: AI diagnostics reported `avg_signal_duration_bars` of 9803 (entire backtest), which appeared wrong for an event-based strategy like EMA crossover, but was technically correct for a state-based architecture.
3. **Complex State Tracking**: Entry windows required tracking signal transitions to detect when a new opportunity arose vs. a persistent desire.
4. **Exit Ambiguity**: "flat" could mean either "exit my position" or "don't enter" depending on context.

## Decision

Refactor to command-based signals where strategies output discrete trading commands:
- `"enter_long"`: Attempt to enter a long position
- `"enter_short"`: Attempt to enter a short position
- `"exit_long"`: Exit long position (if exists)
- `"exit_short"`: Exit short position (if exists)
- `None`: No action (most bars will be None)

**Key Principles:**

1. **Strategies are stateless**: They generate commands based purely on price/indicator conditions without tracking actual positions
2. **Portfolio Manager enforces reality**: PM ignores impossible commands (e.g., "exit_long" when no position exists)
3. **Entry windows apply to entry commands**: An entry command opens a window; the window can stay active across bars with `None` commands
4. **Exit commands execute immediately**: No windows for exits - they happen instantly if a matching position exists
5. **Opposite-side entry commands always close current position**: If you have a long position and receive "enter_short", the long closes regardless of `allow_flip_on_bar`. If `allow_flip_on_bar=True`, an entry window opens for short after closing. If `False`, just close and don't open entry window.

## Consequences

### Positive
- **Clear Intent**: Each command has unambiguous meaning
- **Simpler Strategy Logic**: No position state tracking in strategies
- **Accurate Metrics**: `avg_signal_duration` will now be ~1 bar per command, matching intuition
- **Clean Separation**: Strategy generates opportunities, PM enforces feasibility
- **Entry Windows Make Sense**: Natural fit for command model
- **Better AI Diagnostics**: AI can now accurately analyze signal patterns

### Negative
- **Breaking Change**: All existing strategies must be updated
- **Internal State Still Needed**: Strategies track internal state to detect when to emit commands (e.g., "was I in a long opportunity? Now I'm not → emit exit_long")
- **Migration Effort**: ~7 hours of work to refactor

### Neutral
- **Same Expressiveness**: Can model same strategies as before, just clearer syntax
- **Test Changes**: Tests need updates but logic remains similar

## Implementation Notes

- Strategies maintain internal state for command generation (not actual positions)
- PM's `process_command()` method centralizes all command handling
- Entry windows track `(window_start_bar, last_entered_bar)` per side
- Commands can overlap (strategy can emit multiple); PM resolves based on current state
- Backtester validates commands: `{"enter_long", "enter_short", "exit_long", "exit_short", "None"}`

## Alternatives Considered

1. **Keep state-based, add metadata**: Document that long signal durations are expected
   - Rejected: Doesn't solve underlying ambiguity issues

2. **Hybrid signals with metadata**: Signals carry both state and event info
   - Rejected: Added complexity without clear benefit

3. **Pure event stream**: Only emit on changes, no state tracking at all
   - Rejected: Strategies still need internal state to detect changes

## Validation Results

After implementation:
- ✅ EMA crossover backtest produces exactly 69 trades (same as before)
- ✅ All portfolio manager tests pass (10/10)
- ✅ Backtester integration tests pass
- ✅ Entry window logic works correctly with commands
- ✅ Signal duration metrics now show ~1 bar per command (down from 9803)

## References

- **Original issue**: AI diagnostic report flagging `avg_signal_duration_bars: 9803` at `runs/researcher/run_20250930_020553_utc/ai_qualitative_report.md`
- **Requirements**: [SE-3.1], [SE-3.2], [SE-3.3], [PM-5.8], [BT-7.1.2]
- **Implementation**: See `docs/code_tasks/command_based_signals_refactor.md`
- **Key files modified**:
  - `src/trading_platform/core/types.py` (created)
  - `src/trading_platform/portfolio/portfolio.py`
  - `src/trading_platform/strategy/base.py`
  - `src/trading_platform/strategy/yaml_strategy.py`
  - `src/trading_platform/backtester/core.py`
  - `src/trading_platform/reporting/brief.py`