# Refactoring Plan: State-Based → Command-Based Signals

## Overview

Refactor the signal architecture from state-based signals ("long"/"short"/"flat") to command-based signals ("enter_long", "enter_short", "exit_long", "exit_short", None). This eliminates ambiguity, makes entry windows more logical, and fixes AI diagnostic confusion about signal duration.

## Motivation

**Current Problems:**
- State-based signals create ambiguity: Does "long" mean "enter long" or "stay long"?
- AI diagnostic complains about `avg_signal_duration_bars` being 9803 (entire backtest)
- Entry window logic requires complex state tracking to detect transitions
- "flat" signal conflates "exit" with "don't enter"

**Benefits of Commands:**
- Unambiguous intent: `enter_long` means exactly one thing
- Strategy stays pure: generates commands without tracking positions
- PM handles reality: ignores impossible commands (exit when flat, enter when positioned)
- Entry windows apply naturally to entry commands only
- AI diagnostics will show signal duration = 1 bar per command

## Architecture Principles

1. **Strategy: Pure Signal Generator (No Position Awareness)**
   - Generates commands based ONLY on price/indicators
   - Has NO idea if a position is open
   - Can emit "exit_long" even when flat → PM will ignore

2. **Portfolio Manager: Command Executor**
   - Filters impossible commands
   - Manages entry windows (applies to entry commands only)
   - Tracks actual position state
   - Enforces flip policy

3. **Commands Can Overlap/Conflict**
   - Strategy can emit "enter_long" and "exit_short" on same bar
   - PM resolves based on current state

---

## Phase 1: Architecture & Design (30 min)

### 1.1 Define Command Types
- [x] Create or update `src/trading_platform/core/types.py`

```python
from typing import Literal

SignalCommand = Literal["enter_long", "enter_short", "exit_long", "exit_short", None]
```

### 1.2 Update Requirements Doc
- [x] Modify [SE-3.1]
```markdown
**[SE-3.1]** **Core Mandate**: The Strategy Engine is responsible for **signal generation only**.
Strategies generate **trading commands** (enter_long, enter_short, exit_long, exit_short) based on
market conditions. Strategies are stateless and do not track position state - they generate commands
independently, and the Portfolio Manager enforces feasibility (e.g., ignoring exit commands when no
position exists).
```

- [x] Update [PM-5.8.3]
- [x] Update [SE-3.3]
- [x] Update [BT-7.1.2]
```markdown
**[PM-5.8.3]** Support configurable entry window policies:
  - Entry windows apply only to **entry commands** (enter_long, enter_short)
  - Exit commands are executed immediately if a matching position exists
  - entry_window_bars: 0 = execute entry commands on exact bar only
  - entry_window_bars: N > 0 = keep entry window open for N bars after command
  - entry_window_bars: -1 = infinite window (always try when entry command active)
```

### 1.3 Decision Points to Document
- [x] Document these decisions:

**Decision 1: Position Flipping**
- **Q:** Should `enter_short` when in long position trigger auto-exit?
  - **A:** Yes, an opposite-side entry command ALWAYS triggers exit of current position, regardless of `allow_flip_on_bar`. If `allow_flip_on_bar=True`, then open entry window for new side after exit. If `allow_flip_on_bar=False`, just exit and don't enter.

**Decision 2: Multiple Commands Per Bar**
- **Q:** Can both entry and exit commands fire on same bar?
  - **A:** Yes. Strategy can emit multiple commands. PM processes in order: exits first, then entries.

**Decision 3: Backwards Compatibility**
- **Q:** Backwards compatibility during transition?
  - **A:** No backwards compatibility needed. This is a breaking change for all strategies. All YAML strategies will be updated in this refactor.

**Decision 4: Exit Commands Without Position**
- **Q:** What happens when strategy emits `exit_long` but there's no position (or wrong side)?
  - **A:** PM silently ignores it with reason "no_matching_position". Strategies don't track positions, so they can emit "impossible" commands.

**Decision 5: Entry Windows for None Commands**
- **Q:** If entry window is open and current bar has `None` command, should window stay open?
  - **A:** Yes. Entry windows persist across `None` commands until: (a) entry occurs, (b) window expires per `entry_window_bars`, or (c) opposite-side command received.

---

## Phase 2: Core Changes (Portfolio Manager) (1 hour)

### 2.1 Update PortfolioManager Interface
- [x] Remove old methods from `src/trading_platform/portfolio/portfolio.py`
```python
def update_signal_state(...)  # Delete
def should_attempt_entry(...)  # Delete
def mark_entry_on_signal(...)  # Delete
```

- [x] Add `process_command` method
```python
def process_command(
    self,
    command: SignalCommand,
    bar_index: int,
    warmup_threshold: int,
    entry_window_bars: int,
    allow_flip: bool,
    current_bar: pd.Series,
    context: dict | None = None
) -> dict[str, Any]:
    """
    Process a strategy command and return action taken.

    Args:
        command: The signal command from strategy
        bar_index: Current bar index
        warmup_threshold: Bar index where warmup ends
        entry_window_bars: Entry window policy (0, N, or -1)
        allow_flip: Whether to allow flipping positions
        current_bar: Current market data bar
        context: Strategy context (regime, indicators, etc.)

    Returns:
        Dictionary with:
        - "action": "entered" | "exited" | "ignored" | "window_opened" | "window_active"
        - "side": "long" | "short" | None
        - "reason": str (if ignored)
    """
```

### 2.2 Command Processing Logic
- [x] Implement `process_command` method logic

```python
def process_command(self, command, bar_index, warmup_threshold, entry_window_bars,
                   allow_flip, current_bar, context=None):
    # Skip warmup period
    if bar_index < warmup_threshold:
        return {"action": "ignored", "reason": "warmup", "side": None}

    # Handle None/null commands
    if command is None:
        # Check if we have active entry windows to maintain
        return self._check_active_entry_windows(bar_index, entry_window_bars, current_bar, context)

    # Entry commands
    if command in ["enter_long", "enter_short"]:
        side = "long" if command == "enter_long" else "short"
        return self._handle_entry_command(side, bar_index, entry_window_bars,
                                         allow_flip, current_bar, context)

    # Exit commands
    elif command in ["exit_long", "exit_short"]:
        side = "long" if command == "exit_long" else "short"
        return self._handle_exit_command(side, current_bar, context)

    return {"action": "ignored", "reason": "unknown_command", "side": None}


def _handle_entry_command(self, side, bar_index, entry_window_bars, allow_flip,
                         current_bar, context):
    """Handle enter_long or enter_short command."""

    # Already in same-side position
    if self.current_position and self.current_position.side == side:
        return {"action": "ignored", "reason": "already_in_position", "side": side}

    # In opposite position
    if self.current_position and self.current_position.side != side:
        if allow_flip:
            # Close current position first
            self.close_position(
                exit_price=current_bar["close"],
                exit_time=current_bar.name,
                exit_reason="flip",
                context_at_exit=context
            )
            # Then fall through to open new entry window
        else:
            return {"action": "ignored", "reason": "flip_not_allowed", "side": side}

    # Open entry window for this side
    self._entry_windows[side] = (bar_index, None)  # (window_start, last_entered)

    # Try immediate entry (might be blocked by RMM, etc.)
    # This is handled by caller (backtester) - we just mark window open
    return {"action": "window_opened", "side": side}


def _handle_exit_command(self, side, current_bar, context):
    """Handle exit_long or exit_short command."""

    if self.current_position and self.current_position.side == side:
        self.close_position(
            exit_price=current_bar["close"],
            exit_time=current_bar.name,
            exit_reason="signal",
            context_at_exit=context
        )
        return {"action": "exited", "side": side}
    else:
        return {"action": "ignored", "reason": "no_matching_position", "side": side}


def _check_active_entry_windows(self, bar_index, entry_window_bars, current_bar, context):
    """Check if we have active entry windows to maintain (for None commands)."""

    # This allows entry windows to stay open across bars with None commands
    # Caller (backtester) will check if entry is now possible (e.g., RMM unblocked)

    for side in ["long", "short"]:
        window_start, last_entered = self._entry_windows[side]

        if window_start >= 0 and last_entered is None:  # Window open, not entered
            bars_since_start = bar_index - window_start

            if entry_window_bars == -1 or bars_since_start <= entry_window_bars:
                return {"action": "window_active", "side": side}

    return {"action": "ignored", "reason": "no_active_command", "side": None}
```

- [x] Implement `_handle_entry_command` method
- [x] Implement `_handle_exit_command` method
- [x] Implement `_check_active_entry_windows` method

### 2.3 Keep Entry Window State
- [x] Delete `_prev_signal` variable

```python
self._entry_windows: dict[str, tuple[int, int | None]] = {
    "long": (-1, None),
    "short": (-1, None),
}
```

### 2.4 Add Helper for Entry Attempts
- [x] Add `can_attempt_entry` helper method
```python
def can_attempt_entry(self, side: str, bar_index: int, entry_window_bars: int) -> bool:
    """Check if we can attempt entry for this side (used by backtester)."""
    window_start, last_entered = self._entry_windows[side]

    if window_start < 0 or last_entered is not None:
        return False  # No window open or already entered

    bars_since_start = bar_index - window_start

    if entry_window_bars == -1:
        return True  # Infinite window

    return bars_since_start <= entry_window_bars
```

---

## Phase 3: Strategy Layer Changes (1.5 hours)

### 3.1 Update BaseStrategy Interface
- [x] Update `src/trading_platform/strategy/base.py` docstring and type hints

```python
from trading_platform.core.types import SignalCommand

class BaseStrategy:
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate trading command signals from market data.

        Returns:
            Series of SignalCommand values:
            - "enter_long": Signal to enter long position
            - "enter_short": Signal to enter short position
            - "exit_long": Signal to exit long position
            - "exit_short": Signal to exit short position
            - None: No command (do nothing)
        """
```

### 3.2 Refactor yaml_strategy.py State Machine
- [x] Refactor `_generate_signals_from_rules` in `src/trading_platform/strategy/yaml_strategy.py`

```python
def _generate_signals_from_rules(self, df: pd.DataFrame) -> pd.Series:
    """
    Generate command signals from entry/exit rules.

    Strategy maintains internal state to detect transitions,
    but this state is not exposed to the caller.
    """
    le = self._eval_entries(df, "long")
    se = self._eval_entries(df, "short")
    lx = self._eval_exits(df, "long")
    sx = self._eval_exits(df, "short")

    commands = []

    # Internal state for detecting when to generate commands
    # This is NOT the same as actual position state
    internal_state = "flat"

    for i in range(len(df)):
        cmd = None

        # Check exits first (if we think we're in a position internally)
        if internal_state == "long" and bool(lx.iloc[i]):
            cmd = "exit_long"
            internal_state = "flat"
        elif internal_state == "short" and bool(sx.iloc[i]):
            cmd = "exit_short"
            internal_state = "flat"

        # Check entries (only if we think we're flat internally)
        if internal_state == "flat":
            if bool(le.iloc[i]):
                if not self.slope_filter or self._check_slope(df, i, "long"):
                    cmd = "enter_long"
                    internal_state = "long"
            elif bool(se.iloc[i]):
                if not self.slope_filter or self._check_slope(df, i, "short"):
                    cmd = "enter_short"
                    internal_state = "short"

        commands.append(cmd)

    return pd.Series(commands, index=df.index, dtype=object)


def _check_slope(self, df: pd.DataFrame, i: int, side: str) -> bool:
    """Helper to check slope filter if enabled."""
    if side == "long":
        return bool(self._slope_up.iloc[i]) if hasattr(self, '_slope_up') else True
    else:
        return bool(self._slope_down.iloc[i]) if hasattr(self, '_slope_down') else True
```

**Key points:**
- Strategy maintains `internal_state` to know when to generate entry vs exit commands
- This is NOT actual position tracking - just for command generation logic
- If exit rules are empty, strategy can rely on opposite entry as implicit exit
- Exits checked before entries (same bar can have both, exit takes precedence)

### 3.3 Strategy YAML Schema
- [x] Verify YAML schema (no changes needed)

```yaml
long_entry_rules: [...]   # Generates "enter_long"
long_exit_rules: [...]    # Generates "exit_long"
short_entry_rules: [...]  # Generates "enter_short"
short_exit_rules: [...]   # Generates "exit_short"
```

### 3.4 Update Existing Strategy YAMLs
- [x] Review all YAML files in `config/strategy/` to ensure entry/exit rules are correct

**For EMA crossover specifically:**
- `long_entry_rules`: cross_above → "enter_long"
- `short_entry_rules`: cross_below → "enter_short"
- Exit rules can be empty (opposite entry acts as implicit exit)

---

## Phase 4: Backtester Changes (30 min)

> **Note (2025-10-27):** The original refactor relied on a `warmup_bars` field.
> The engine now derives the first fully initialized timestamp for strategy and
> global features and trims any warmup rows automatically before the main loop.

### 4.1 Update Main Loop
- [x] Refactor main loop in `src/trading_platform/backtester/core.py`
```python
warmup_threshold = max(0, config.warmup_bars)

for i in range(len(market_data)):
    current_signal = signals.iloc[i]
    current_bar = market_data.iloc[i]
    context = strategy.get_context(i)

    # Update portfolio's signal tracking state
    portfolio.update_signal_state(current_signal, i, warmup_threshold)

    # ... REM checks ...
    # ... on_bar processing ...

    # Entry logic
    should_attempt = portfolio.should_attempt_entry(current_signal, i, config.entry_window_bars)
    if not portfolio.current_position and should_attempt and ...:
        # ... entry logic ...
        portfolio.mark_entry_on_signal(current_signal, i)
```

**New code:**
```python
warmup_threshold = max(0, config.warmup_bars)

for i in range(len(market_data)):
    command = signals.iloc[i]
    current_bar = market_data.iloc[i]
    context = strategy.get_context(i)

    # Enrich context with regime
    if rmm_context is not None:
        rmm_ctx = rmm_context.get(cast(datetime, current_bar.name))
        if rmm_ctx is not None:
            context = dict(context or {})
            context["regime_label"] = rmm_ctx.get("label")

    # REM exits (before processing command)
    if portfolio.current_position:
        exit_details = rem.check_exits(portfolio.current_position, current_bar)
        if exit_details:
            portfolio.close_position(
                exit_price=exit_details["exit_price"],
                exit_time=cast(datetime, current_bar.name),
                exit_reason=exit_details["reason"],
                context_at_exit=context,
            )
            if return_exposure:
                exposure_curve.append((cast(datetime, current_bar.name), 0.0))
            continue

    # Process command through Portfolio Manager
    result = portfolio.process_command(
        command=command,
        bar_index=i,
        warmup_threshold=warmup_threshold,
        entry_window_bars=config.entry_window_bars,
        allow_flip=config.allow_flip_on_bar,
        current_bar=current_bar,
        context=context
    )

    # Handle result
    if result["action"] in ["window_opened", "window_active"]:
        # Try to enter if conditions allow
        side = result["side"]

        if portfolio.can_attempt_entry(side, i, config.entry_window_bars):
            if policy.can_open(cast(datetime, current_bar.name)):
                # Check RMM
                if rmm_context is not None:
                    # ... RMM checking logic ...
                    # If blocked, add to skipped

                # Check daily loss cap
                # ... loss cap logic ...

                # Check position cap
                # ... position cap logic ...

                # If all pass, create position
                portfolio.create_new_position(
                    symbol=symbol,
                    side=side,
                    entry_price=current_bar["close"],
                    size=float(config.position_size),
                    entry_time=cast(datetime, current_bar.name),
                    instrument=config.instrument,
                    context_at_entry=context,
                    initial_risk_ccy=None,
                )

                # Mark entry in window
                portfolio._entry_windows[side] = (
                    portfolio._entry_windows[side][0],
                    i
                )

    # Update exposure
    if return_exposure:
        exposure_val = 0.0
        if portfolio.current_position:
            exposure_val = float(abs(portfolio.current_position.size) * float(current_bar["close"]))
        exposure_curve.append((cast(datetime, current_bar.name), exposure_val))
```

### 4.2 Simplification Opportunities
- [x] Simplify backtester loop logic
- Command validation
- Entry window management
- Exit feasibility

The backtester just needs to:
1. Get command from strategy
2. Pass to PM.process_command()
3. If PM says "window_opened" or "window_active", check filters (RMM, loss cap, etc.) and try entry
4. If PM says "exited", record it

### 4.3 Remove Old Code
- [x] Delete old PM method calls from backtester
- `portfolio.update_signal_state()`
- `portfolio.should_attempt_entry()`
- `portfolio.mark_entry_on_signal()`

---

## Phase 5: Testing Strategy (2 hours)

### 5.1 Update Portfolio Manager Tests
- [x] Add new command-based tests to `tests/portfolio/test_portfolio.py`

```python
@requires("PM-5.8")
def test_process_enter_long_command():
    """Test processing enter_long command opens entry window."""
    pm = PortfolioManager(initial_cash=100000)

    result = pm.process_command(
        command="enter_long",
        bar_index=0,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=False,
        current_bar=pd.Series({"close": 1.0, "open": 1.0, "high": 1.0, "low": 1.0}),
        context=None
    )

    assert result["action"] == "window_opened"
    assert result["side"] == "long"
    assert pm.can_attempt_entry("long", 0, 3)


@requires("PM-5.8")
def test_process_exit_when_no_position():
    """Test exit command is ignored when no position exists."""
    pm = PortfolioManager(initial_cash=100000)

    result = pm.process_command(
        command="exit_long",
        bar_index=0,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=False,
        current_bar=pd.Series({"close": 1.0, "open": 1.0, "high": 1.0, "low": 1.0}),
        context=None
    )

    assert result["action"] == "ignored"
    assert result["reason"] == "no_matching_position"


@requires("PM-5.8")
def test_process_enter_when_already_in_position():
    """Test enter command is ignored when already in same position."""
    pm = PortfolioManager(initial_cash=100000)

    # Enter long
    pm.process_command("enter_long", bar_index=0, warmup_threshold=0, entry_window_bars=3,
                      allow_flip=False, current_bar=pd.Series({"close": 1.0}), context=None)
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        size=100,
        entry_time=datetime(2024, 1, 1)
    )

    # Try to enter long again
    result = pm.process_command("enter_long", bar_index=1, warmup_threshold=0,
                               entry_window_bars=3, allow_flip=False,
                               current_bar=pd.Series({"close": 1.0}), context=None)

    assert result["action"] == "ignored"
    assert result["reason"] == "already_in_position"


@requires("PM-5.8")
def test_process_flip_position():
    """Test entering opposite position with allow_flip=True."""
    pm = PortfolioManager(initial_cash=100000)

    # Enter long
    pm.create_new_position(
        symbol="EURUSD",
        side="long",
        entry_price=1.0,
        size=100,
        entry_time=datetime(2024, 1, 1)
    )

    # Enter short with flip allowed
    result = pm.process_command(
        "enter_short",
        bar_index=1,
        warmup_threshold=0,
        entry_window_bars=3,
        allow_flip=True,
        current_bar=pd.Series({"close": 1.01, "name": datetime(2024, 1, 1, 1)}),
        context=None
    )

    assert result["action"] == "window_opened"
    assert result["side"] == "short"
    assert pm.current_position is None  # Closed long
    assert len(pm.trades) == 1  # Long trade closed


@requires("PM-5.8")
def test_entry_window_remains_open_with_none_commands():
    """Test entry window stays open across bars with None commands."""
    pm = PortfolioManager(initial_cash=100000)

    # Bar 0: enter_long command
    result = pm.process_command("enter_long", bar_index=0, warmup_threshold=0,
                               entry_window_bars=3, allow_flip=False,
                               current_bar=pd.Series({"close": 1.0}), context=None)
    assert result["action"] == "window_opened"

    # Bar 1: None command (window should stay active)
    result = pm.process_command(None, bar_index=1, warmup_threshold=0,
                               entry_window_bars=3, allow_flip=False,
                               current_bar=pd.Series({"close": 1.0}), context=None)
    assert result["action"] == "window_active"
    assert result["side"] == "long"
    assert pm.can_attempt_entry("long", 1, 3)

    # Bar 4: Window expired
    result = pm.process_command(None, bar_index=4, warmup_threshold=0,
                               entry_window_bars=3, allow_flip=False,
                               current_bar=pd.Series({"close": 1.0}), context=None)
    assert result["action"] == "ignored"
    assert not pm.can_attempt_entry("long", 4, 3)
```

- [x] Remove old state-based tests from `tests/portfolio/test_portfolio.py`
  - Delete `test_entry_window_event_based` (replaced by command-based tests)
- Delete `test_entry_window_delayed_entry` (replaced)
- Delete `test_entry_window_infinite` (replaced)
- Delete `test_entry_window_prevents_reentry_after_entry` (replaced)
- Delete `test_entry_window_resets_on_new_transition` (replaced)
- Delete `test_entry_window_warmup_threshold` (replaced)

### 5.2 Update Strategy Tests
- [ ] Add command generation tests to `tests/strategy/test_yaml_strategy.py` (TODO: Not done yet)

```python
def test_ema_crossover_generates_enter_long_command():
    """Test EMA crossover generates enter_long on cross above."""
    # Create test data with clear cross above at bar 50
    df = create_test_data_with_cross_above_at_bar_50()

    strategy = load_yaml_strategy("config/strategy/ema_crossover.yaml")
    commands = strategy.generate_signals(df)

    # Should generate enter_long at crossover bar
    assert commands.iloc[50] == "enter_long"

    # Bars before and after should be None (no command)
    assert commands.iloc[49] is None
    assert commands.iloc[51] is None


def test_ema_crossover_generates_enter_short_command():
    """Test EMA crossover generates enter_short on cross below."""
    df = create_test_data_with_cross_below_at_bar_100()

    strategy = load_yaml_strategy("config/strategy/ema_crossover.yaml")
    commands = strategy.generate_signals(df)

    assert commands.iloc[100] == "enter_short"


def test_strategy_generates_none_when_no_conditions_met():
    """Test strategy generates None when no entry/exit conditions met."""
    df = create_flat_trending_data()

    strategy = load_yaml_strategy("config/strategy/ema_crossover.yaml")
    commands = strategy.generate_signals(df)

    # Most bars should be None
    none_count = (commands.isna() | (commands == None)).sum()
    assert none_count > len(df) * 0.9  # At least 90% None
```

### 5.3 Update Backtester Integration Tests
- [x] Verify integration tests in `tests/backtester/test_backtester.py` still work with commands

---

## Phase 6: Requirements & Documentation (30 min)

### 6.1 Update project_requirements.md
- [ ] Update [SE-3.1] in `docs/project_requirements.md`
```markdown
- **[SE-3.1]** **Core Mandate**: The Strategy Engine is responsible for **signal generation only**. Strategy definitions must be purely abstract and instrument-agnostic.
- **[SE-3.2]** A `BaseStrategy` interface will define methods for preparing data and generating a signal series (`long`, `short`, or `flat`). A `flat` signal is considered a **strategic exit**.
```

With:
```markdown
- **[SE-3.1]** **Core Mandate**: The Strategy Engine is responsible for **signal generation only**. Strategies generate **trading commands** (enter_long, enter_short, exit_long, exit_short, None) based on market conditions. Strategies are stateless and do not track position state - they generate commands independently, and the Portfolio Manager enforces feasibility (e.g., ignoring exit commands when no position exists).
- **[SE-3.2]** A `BaseStrategy` interface will define methods for preparing data and generating a command series. Commands are discrete trading actions:
  - `enter_long`: Signal to enter a long position
  - `enter_short`: Signal to enter a short position
  - `exit_long`: Signal to exit a long position
  - `exit_short`: Signal to exit a short position
  - `None`: No action (most common - strategies only emit commands on specific events)
```

- [ ] Update [SE-3.3] in `docs/project_requirements.md`
```markdown
- **[SE-3.3]** Strategy definitions **must not** contain instrument-specific logic or trade management rules like stop-loss or take-profit. This is the sole responsibility of the Risk & Exit Manager (REM). Strategies also **must not** track actual position state - they generate commands based purely on market data and indicator logic.
```

- [ ] Update [PM-5.8.3] in `docs/project_requirements.md`
```markdown
  - **[PM-5.8.3]** Support configurable entry window policies:
    - `entry_window_bars: 0` = Event-based (only enter on exact transition bar)
    - `entry_window_bars: N` (N > 0) = Allow delayed entry within N bars if initially blocked by filters (e.g., RMM)
    - `entry_window_bars: -1` = Infinite window (always try when signal is active, state-based)
```

With:
```markdown
  - **[PM-5.8.3]** Support configurable entry window policies:
    - Entry windows apply only to **entry commands** (enter_long, enter_short)
    - Exit commands are executed immediately if a matching position exists
    - `entry_window_bars: 0` = Execute entry commands on exact bar only
    - `entry_window_bars: N` (N > 0) = Keep entry window open for N bars after entry command (allows delayed entry if RMM initially blocked)
    - `entry_window_bars: -1` = Infinite window (keep trying to enter as long as entry command is active)
```

- [ ] Update [BT-7.1.2] in `docs/project_requirements.md`
```markdown
  - **[BT-7.1.2]** The Backtester **must not** contain entry decision logic. Entry decisions (including entry window checks) are the responsibility of the Portfolio Manager ([PM-5.8]).
```

With:
```markdown
  - **[BT-7.1.2]** The Backtester **must not** contain entry decision logic. The Backtester passes strategy commands to the Portfolio Manager, which determines feasibility and manages entry windows ([PM-5.8]). The Backtester enforces filters (RMM, loss caps, etc.) when PM indicates an entry window is open.
```

### 6.2 Create Architecture Decision Record
- [ ] Create `docs/adr/001-command-based-signals.md`

```markdown
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

## Consequences

### Positive
- **Clear Intent**: Each command has unambiguous meaning
- **Simpler Strategy Logic**: No position state tracking in strategies
- **Accurate Metrics**: `avg_signal_duration` will now be ~1 bar per command, matching intuition
- **Clean Separation**: Strategy generates opportunities, PM enforces feasibility
- **Entry Windows Make Sense**: Natural fit for command model

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

## Alternatives Considered

1. **Keep state-based, add metadata**: Document that long signal durations are expected
   - Rejected: Doesn't solve underlying ambiguity issues

2. **Hybrid signals with metadata**: Signals carry both state and event info
   - Rejected: Added complexity without clear benefit

3. **Pure event stream**: Only emit on changes, no state tracking at all
   - Rejected: Strategies still need internal state to detect changes

## References

- Original issue: AI diagnostic report flagging `avg_signal_duration_bars: 9803`
- Requirements: [SE-3.1], [SE-3.2], [PM-5.8]
- Implementation: See `docs/code_tasks/command_based_signals_refactor.md`
```

---

## Phase 7: Migration & Validation (1 hour)

### 7.1 Incremental Testing Strategy
- [ ] Run portfolio tests after Phase 2

```bash
- [ ] Run strategy tests after Phase 3
```bash
# After PM changes (Phase 2)
poetry run pytest tests/portfolio/test_portfolio.py -xvs

# After Strategy changes (Phase 3)
poetry run pytest tests/strategy/test_yaml_strategy.py -xvs
```
- [ ] Run backtester tests after Phase 4
```bash
# After Backtester changes (Phase 4)
poetry run pytest tests/backtester/test_backtester.py -xvs
```
- [ ] Run all tests after Phase 5
```bash
# After all test updates (Phase 5)
poetry run pytest -x

# Full test suite
poetry run pytest --tb=short
```

### 7.2 Run EMA Crossover Backtest
- [x] Run EMA crossover backtest
```bash
./configs/strategies/ema_crossover/run_backtest.sh
```
- [x] Verify backtest results (69 trades, same entry/exit times) ✅ VERIFIED: 69 trades produced
- Number of trades is still 69
- Key crossover trades at Oct 21, Oct 29, Nov 1 still present
- Entry/exit times match previous run

```bash
# Check trade count
jq '.trades | length' runs/researcher/run_<timestamp>_utc/brief.json

# Check key trades
jq -r '.trades[] | select(.entry_time | contains("2024-10-21")) | .entry_time' runs/researcher/run_<timestamp>_utc/brief.json
jq -r '.trades[] | select(.entry_time | contains("2024-10-29")) | .entry_time' runs/researcher/run_<timestamp>_utc/brief.json
jq -r '.trades[] | select(.entry_time | contains("2024-11-01")) | .entry_time' runs/researcher/run_<timestamp>_utc/brief.json
```

### 7.3 Run AI Diagnostic
- [ ] Run AI diagnostic with qualitative report
```bash
# Generate new diagnostic with qualitative report
poetry run python -m trading_platform.cli ai-diagnose \
  --run runs/researcher/run_<timestamp>_utc \
  --qualitative-report
```
- [ ] Verify signal duration metrics are short (~1-3 bars)
- `avg_signal_duration_bars` is now short (~1-3 bars)
- AI report no longer flags signal duration as an issue
- Other metrics remain sensible

```bash
# Check signal quality metrics
jq '.signal_quality_analysis' runs/researcher/run_<timestamp>_utc/brief.json
```

### 7.4 Regression Checklist
- [ ] Complete regression checklist:
  - [ ] All tests pass (1099+)
  - [ ] EMA backtest produces 69 trades
  - [ ] Key crossover trades match previous run
  - [ ] `avg_signal_duration_bars` is short (~1-3 bars)
  - [ ] AI diagnostic no longer complains about signal duration
  - [ ] Entry windows still work (delayed entry tests pass)
  - [ ] Exit logic still works (positions close on exit commands)
  - [ ] RMM filtering still works (trades blocked when regime disallows)
  - [ ] Flip logic still works (can go long→short in one bar if enabled)

### 7.5 Compare Before/After
- [ ] Compare before/after results

```bash
# Before refactor
OLD_RUN=runs/researcher/run_20250930_020414_utc

# After refactor
NEW_RUN=runs/researcher/run_<timestamp>_utc

echo "=== Trade Count ==="
echo "Old: $(jq '.trades | length' $OLD_RUN/brief.json)"
echo "New: $(jq '.trades | length' $NEW_RUN/brief.json)"

echo -e "\n=== Signal Duration ==="
echo "Old: $(jq '.signal_quality_analysis.avg_signal_duration_bars' $OLD_RUN/brief.json)"
echo "New: $(jq '.signal_quality_analysis.avg_signal_duration_bars' $NEW_RUN/brief.json)"

echo -e "\n=== Total PnL ==="
echo "Old: $(jq '.overall_performance.total_pnl' $OLD_RUN/brief.json)"
echo "New: $(jq '.overall_performance.total_pnl' $NEW_RUN/brief.json)"
```

**Expected differences:**
- ✅ `avg_signal_duration_bars`: 9803 → ~1-3
- ✅ Trade count: Same (69)
- ✅ PnL: Same ($70)
- ✅ Entry/exit times: Same

---

## Timeline & Effort

| Phase | Description | Estimated Time | Cumulative |
|-------|-------------|----------------|------------|
| 1 | Architecture & Design | 30 min | 30 min |
| 2 | Portfolio Manager Changes | 1 hour | 1.5 hrs |
| 3 | Strategy Layer Changes | 1.5 hours | 3 hrs |
| 4 | Backtester Changes | 30 min | 3.5 hrs |
| 5 | Testing Updates | 2 hours | 5.5 hrs |
| 6 | Requirements & Docs | 30 min | 6 hrs |
| 7 | Migration & Validation | 1 hour | **7 hrs** |

**Total estimated effort: 7 hours (1 full work day)**

---

## Risk Assessment

### High Risk
- **Breaking existing tests**: Mitigated by incremental testing after each phase
- **Subtle behavior changes**: Mitigated by comprehensive regression testing and comparing before/after results
- **Edge cases in command handling**: Mitigated by thorough unit tests for all command combinations

### Medium Risk
- **YAML strategy state machine refactor**: Well-scoped change, clear logic
- **Test maintenance burden**: Many tests to update, but systematic
- **Flip logic complexity**: Need careful testing of position flipping

### Low Risk
- **Requirements doc updates**: Straightforward documentation
- **PM interface changes**: Well-defined, isolated changes
- **Signal type changes**: Simple type substitution

---

## Success Criteria

### Must Have (Blocking)
- ✅ All 1099+ tests pass
- ✅ EMA crossover produces same 69 trades at same times
- ✅ Entry windows work correctly (delayed entry tests pass)
- ✅ Exit logic works correctly (positions close on exit commands)

### Should Have (Important)
- ✅ `avg_signal_duration_bars` is short (~1-3 bars)
- ✅ AI diagnostic no longer flags signal duration issue
- ✅ Code is cleaner and more maintainable
- ✅ Documentation updated and accurate

### Nice to Have (Beneficial)
- ✅ Performance is same or better
- ✅ No new warnings or deprecations
- ✅ Test coverage maintained or improved

---

## Rollback Plan

If the refactor fails or introduces critical issues:

1. **Revert commits** to before refactor started
2. **Keep ADR** documenting what we tried and why it didn't work
3. **Alternative**: Add metadata to brief explaining state-based signals (original Option 3)

**Rollback trigger conditions:**
- Cannot achieve same trade results (69 trades at same times)
- Tests cannot be fixed within reasonable time (~2 hours debugging)
- Performance degrades significantly (>50% slower)
- Fundamental architectural issue discovered

---

## Post-Refactor Improvements

After successful refactor, consider:

1. **Add signal quality metrics** to brief:
   - `commands_per_bar`: How many commands per bar on average
   - `entry_command_count`: Total entry commands
   - `exit_command_count`: Total exit commands
   - `none_ratio`: Percentage of bars with None

2. **Strategy optimization**: Now that signals are clear, easier to:
   - Tune EMA parameters
   - Add filters
   - Test different exit rules

3. **New strategy types**: Command model makes certain patterns easier:
   - Explicit profit-taking exits
   - Time-based exits
   - Partial exits

4. **Better AI diagnostics**: AI can now analyze:
   - Command frequency vs trade frequency (shows filter impact)
   - Entry acceptance rate (commands → actual entries)
   - Exit command usage (strategic vs REM exits)
