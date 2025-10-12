# Refactor Execution Model Implementation Plan (v3)

**Objective:** Refactor the `PortfolioManager`, `Backtester`, and `RiskExitManager` to cleanly separate state management from execution timing. This will enable a true `next_bar_open` execution model for both entries and exits, which is required to achieve perfect alignment with TradingView golden validation data.

**Architecture Decision:** This implements a hybrid approach where the `PortfolioManager` returns action descriptors (decisions) while maintaining its own state, and the `Backtester` acts as the sole executor that determines timing based on the execution model.

---

## Instructions for Developer

You will be refactoring core components of the backtesting engine. Follow these instructions precisely in the exact order listed. Do not skip steps or deviate from the plan.

First, create a new branch for this work:
```bash
git checkout -b feature/execution-model-refactor
```

Execute the following tasks in the exact order they are listed.

---

## Task List

### Part 1: Restore Stable Baseline

1.  **[ ] Document Current Partial Implementation**
    *   **Action:** Before reverting, save the current work-in-progress for reference.
    *   **Command:**
        ```bash
        git diff > workspace/execution_model_partial_work.patch
        git status > workspace/execution_model_files_modified.txt
        ```
    *   **Rationale:** Preserves any useful insights from the previous session.

2.  **[ ] Revert Local Changes**
    *   **Action:** Revert all uncommitted changes in your local working directory to match the `HEAD` of your current branch. This is critical to ensure we start from a clean, known-good state.
    *   **Command:**
        ```bash
        git checkout -- .
        ```
    *   **Verification:** Run `git status` and confirm working directory is clean.

3.  **[ ] Verify Baseline Tests Pass**
    *   **Action:** Run the full test suite to confirm the baseline is stable.
    *   **Command:**
        ```bash
        pytest -v
        ```
    *   **Verification:** All tests must pass. If any fail, investigate before proceeding.

---

### Part 2: Refactor `PortfolioManager` to Return Action Descriptors

The goal of this part is to stop the `PortfolioManager` from executing trades directly. It will be modified to return a dictionary describing the action that *should* be taken, while deferring the actual execution to the caller (the `Backtester`). The Portfolio Manager will still manage its own internal state (positions, entry windows, etc.), but it will not call `close_position()` or `create_new_position()` from within its command processing methods.

#### 2.1: Add Internal State for Pending Exits

4.  **[ ] Add Test for Pending Exit Flag**
    *   **File:** `tests/portfolio/test_portfolio_manager.py`
    *   **Action:** Create a new test function `test_pending_exit_flag_set_on_flip`.
    *   **Logic:**
        *   Instantiate a `PortfolioManager`.
        *   Simulate an active `long` position.
        *   Call `portfolio.process_command('enter_short', bar_index=100, ...)` (a flip scenario).
        *   Assert that `portfolio._pending_exit` is `True`.
        *   Assert that `portfolio.current_position` is **not** `None` (position still exists).
        *   Assert that `portfolio.is_entry_window_open('short', 100)` is `False` (window NOT opened yet).

5.  **[ ] Add `_pending_exit` Flag to PortfolioManager**
    *   **File:** `src/trading_platform/portfolio/portfolio.py`
    *   **Action:** Modify the `__init__` method.
    *   **Logic:**
        *   Add a new instance variable: `self._pending_exit: bool = False`.
    *   **Verification:** Run test from step 4. It will fail because we haven't implemented the logic yet, but it should at least not error on the attribute access.

#### 2.2: Refactor Entry Command Handling

6.  **[ ] Create Tests for Entry Command Action Descriptors**
    *   **File:** `tests/portfolio/test_portfolio_manager.py`
    *   **Action:** Create test functions for each scenario:
        *   `test_entry_command_with_no_position_returns_open_window`: Call `process_command('enter_long', ...)` when no position exists. Assert returns `{'action': 'open_entry_window', 'side': 'long', 'bar_index': ...}`.
        *   `test_entry_command_with_same_side_position_returns_no_action`: Call `process_command('enter_long', ...)` when a long position already exists. Assert returns `{'action': 'no_action', 'reason': 'already_in_position', 'side': 'long'}`.
        *   `test_entry_command_with_opposite_position_returns_should_close`: Call `process_command('enter_short', ...)` when a long position exists. Assert returns `{'action': 'should_close', 'reason': 'opposite_signal', 'entry_side': 'short', 'bar_index': ...}`.
        *   In the opposite position test, also assert that `portfolio._pending_exit` is `True` and `portfolio.is_entry_window_open('short', bar_index)` is `False`.

7.  **[ ] Refactor `PortfolioManager._handle_entry_command`**
    *   **File:** `src/trading_platform/portfolio/portfolio.py`
    *   **Action:** Modify the `_handle_entry_command` method to return action descriptors instead of executing trades.
    *   **Logic:**
        *   **Case 1: No position exists:**
            *   Set `self._entry_windows[side] = (bar_index, None)`.
            *   Return `{'action': 'open_entry_window', 'side': side, 'bar_index': bar_index}`.
        *   **Case 2: Same-side position exists:**
            *   Return `{'action': 'no_action', 'reason': 'already_in_position', 'side': side}`.
        *   **Case 3: Opposite-side position exists (flip scenario):**
            *   Set `self._pending_exit = True`.
            *   **Do not** set `self._entry_windows[side]` yet (window will open after exit completes).
            *   Return `{'action': 'should_close', 'reason': 'opposite_signal', 'entry_side': side, 'bar_index': bar_index}`.
    *   **Verification:** Run tests from step 6. All must pass with 100% coverage of modified code.

8.  **[ ] Add Method to Clear Pending Exit and Open Entry Window**
    *   **File:** `src/trading_platform/portfolio/portfolio.py`
    *   **Action:** Create a new public method `complete_pending_exit_and_open_entry_window`.
    *   **Signature:** `def complete_pending_exit_and_open_entry_window(self, side: str, bar_index: int) -> dict[str, Any]:`
    *   **Logic:**
        *   Assert that `self._pending_exit` is `True` (sanity check).
        *   Set `self._pending_exit = False`.
        *   Set `self._entry_windows[side] = (bar_index, None)`.
        *   Return `{'action': 'entry_window_opened', 'side': side, 'bar_index': bar_index}`.
    *   **Test:** Create `test_complete_pending_exit_opens_window` in `tests/portfolio/test_portfolio_manager.py`:
        *   Set `portfolio._pending_exit = True` manually.
        *   Call `complete_pending_exit_and_open_entry_window('short', 101)`.
        *   Assert `portfolio._pending_exit` is `False`.
        *   Assert `portfolio.is_entry_window_open('short', 101)` is `True`.

#### 2.3: Refactor Exit Command Handling

9.  **[ ] Create Tests for Exit Command Action Descriptors**
    *   **File:** `tests/portfolio/test_portfolio_manager.py`
    *   **Action:** Create test functions:
        *   `test_exit_command_with_no_position_returns_no_action`: Call `process_command('exit_long', ...)` when no position exists. Assert returns `{'action': 'no_action', 'reason': 'no_position'}`.
        *   `test_exit_command_with_matching_position_returns_should_close`: Call `process_command('exit_long', ...)` when a long position exists. Assert returns `{'action': 'should_close', 'reason': 'signal', 'side': 'long'}`.
        *   `test_exit_command_with_opposite_position_returns_no_action`: Call `process_command('exit_short', ...)` when a long position exists. Assert returns `{'action': 'no_action', 'reason': 'wrong_side'}`.

10. **[ ] Refactor `PortfolioManager._handle_exit_command`**
    *   **File:** `src/trading_platform/portfolio/portfolio.py`
    *   **Action:** Modify the `_handle_exit_command` method to return action descriptors.
    *   **Logic:**
        *   **Case 1: No position exists:**
            *   Return `{'action': 'no_action', 'reason': 'no_position'}`.
        *   **Case 2: Exit command matches current position side:**
            *   Return `{'action': 'should_close', 'reason': 'signal', 'side': self.current_position.side}`.
        *   **Case 3: Exit command for opposite side:**
            *   Return `{'action': 'no_action', 'reason': 'wrong_side'}`.
    *   **Note:** Remove the call to `self.close_position(...)` from this method.
    *   **Verification:** Run tests from step 9. All must pass with 100% coverage.

---

### Part 3: Refactor `RiskExitManager` for Deferred Execution

This part ensures that REM-based exits (stop-loss/take-profit) also return descriptors with calculated prices, allowing the Backtester to decide when to execute based on the execution model.

11. **[ ] Create Tests for REM Exit Descriptors**
    *   **File:** `tests/risk_manager/test_rem.py`
    *   **Action:** Create test functions:
        *   `test_check_exits_with_stop_triggered_returns_descriptor`: Set up a `RiskExitManager` with a stop-loss rule. Create a mock position and `current_bar` where the low triggers the stop. Call `rem.check_exits_intrabar(position, current_bar)`. Assert returns `{'action': 'should_close', 'reason': 'stop_loss', 'exit_price': <calculated_price>}` where `exit_price` equals the stop-loss level.
        *   `test_check_exits_with_take_profit_triggered_returns_descriptor`: Similar test for take-profit.
        *   `test_check_exits_with_no_trigger_returns_none`: When neither stop nor TP is triggered, assert returns `None`.

12. **[ ] Add `check_exits_intrabar` Method to RiskExitManager**
    *   **File:** `src/trading_platform/risk_manager/rem.py`
    *   **Action:** Create a new method `check_exits_intrabar`.
    *   **Signature:** `def check_exits_intrabar(self, position: Position, current_bar: pd.Series) -> dict[str, Any] | None:`
    *   **Logic:**
        *   Call `self.check_exits(position.side, position.entry_price, ...)` to get stop/TP prices.
        *   Check if `current_bar['low']` <= stop-loss price (for long) or `current_bar['high']` >= stop-loss price (for short).
        *   If stop is triggered, return `{'action': 'should_close', 'reason': 'stop_loss', 'exit_price': stop_loss_price}`.
        *   Check if take-profit is triggered similarly.
        *   If TP is triggered, return `{'action': 'should_close', 'reason': 'take_profit', 'exit_price': take_profit_price}`.
        *   If neither triggered, return `None`.
    *   **Note:** Keep the existing `check_exits()` method unchanged for now (it returns tuple of prices).
    *   **Verification:** Run tests from step 11. All must pass with 100% coverage.

---

### Part 4: Empower `Backtester` as the Sole Executor

The `Backtester` will now interpret descriptors from both the `PortfolioManager` and the `RiskExitManager` and execute trades at the appropriate time based on the execution model.

#### 4.1: Implement Deferred Execution Logic

13. **[ ] Create Test for Backtester Executing Pending Actions**
    *   **File:** `tests/backtester/test_backtester.py`
    *   **Action:** Create test `test_backtester_executes_pending_exit_at_next_bar_open`.
    *   **Logic:**
        *   Create a `RunConfig` with `execution_model: "next_bar_open"`.
        *   Create a DataFrame with 5 bars.
        *   Create a strategy that:
            *   Bar 0: Enter long
            *   Bar 2: Exit long (signal)
        *   Run backtest.
        *   Assert that:
            *   Entry occurs at bar 1 open (next bar after signal).
            *   Exit occurs at bar 3 open (next bar after exit signal).
            *   Exit price equals bar 3 open price.

14. **[ ] Refactor `Backtester.run_backtest` Main Loop for Deferred Execution**
    *   **File:** `src/trading_platform/backtester/core.py`
    *   **Action:** Modify the main loop in `run_backtest`.
    *   **Logic for execution order at the start of each bar iteration:**
        1.  **Execute pending exit** (if `pending_exit` dict is not None):
            *   Call `portfolio.close_position(exit_price=current_bar['open'], exit_time=current_bar.name, exit_reason=pending_exit['reason'], context_at_exit=pending_exit['context'])`.
            *   If `pending_exit` included `'entry_side'` and `'bar_index'`, call `portfolio.complete_pending_exit_and_open_entry_window(pending_exit['entry_side'], bar_index)`.
            *   Set `pending_exit = None`.
        2.  **Execute pending entry** (if `pending_entry` dict is not None):
            *   Call `portfolio.create_new_position(entry_price=current_bar['open'], ...)` using data from `pending_entry`.
            *   Set `pending_entry = None`.
        3.  **Check REM exits** (if position exists):
            *   Call `rem_result = rem.check_exits_intrabar(portfolio.current_position, current_bar)`.
            *   If `rem_result` is not None and `rem_result['action'] == 'should_close'`:
                *   If `config.execution_model == 'current_bar_close'`: Call `portfolio.close_position(exit_price=rem_result['exit_price'], ...)` immediately.
                *   If `config.execution_model == 'next_bar_open'`: Store in `pending_exit` (override REM's exit_price with next bar's open) and `continue` to next iteration.
        4.  **Process strategy command**:
            *   Get command from strategy.
            *   Call `command_result = portfolio.process_command(command, bar_index, ...)`.
            *   If `command_result['action'] == 'should_close'`:
                *   If `config.execution_model == 'current_bar_close'`: Call `portfolio.close_position(exit_price=current_bar['close'], ...)` immediately.
                *   If `config.execution_model == 'next_bar_open'`: Store in `pending_exit`. **Do not** `continue` (allow flip entry to be processed).
            *   If `command_result['action'] == 'open_entry_window'`: Check RMM and caps, then potentially create `pending_entry` (existing logic).
    *   **Verification:** Run test from step 13. It must pass.

#### 4.2: Handle Same-Bar Flips Correctly

15. **[ ] Create Test for Same-Bar Flip with Next Bar Open**
    *   **File:** `tests/backtester/test_backtester.py`
    *   **Action:** Create test `test_backtester_handles_flip_with_next_bar_open`.
    *   **Logic:**
        *   Create a `RunConfig` with `execution_model: "next_bar_open"` and `allow_flip_on_bar: true`.
        *   Create a strategy that generates a flip:
            *   Bar 0: Enter long
            *   Bar 2: Exit long + Enter short (flip)
        *   Run backtest.
        *   Assert:
            *   Trade 1 (long): Entry at bar 1 open, exit at bar 3 open.
            *   Trade 2 (short): Entry at bar 3 open (same time/price as trade 1 exit).
            *   Both exit and entry occur at bar 3 open, same price.

16. **[ ] Verify Flip Logic in Backtester**
    *   **File:** `src/trading_platform/backtester/core.py`
    *   **Action:** Review the logic from step 14 to ensure same-bar flips work.
    *   **Key insight:** When a flip occurs (opposite entry signal):
        1.  `portfolio.process_command('enter_short', ...)` returns `{'action': 'should_close', ..., 'entry_side': 'short'}`.
        2.  Backtester stores this in `pending_exit` (including `entry_side`).
        3.  **Crucially:** Backtester does **not** `continue` after storing pending_exit for signal-based exits.
        4.  Next iteration (bar N+1):
            *   Execute `pending_exit` → closes old position, calls `complete_pending_exit_and_open_entry_window`.
            *   Entry window for new side is now open at bar N+1.
            *   Process command for bar N+1 → RMM/caps allow entry → create `pending_entry`.
            *   (If execution_model is next_bar_open, this entry executes at bar N+2 open).
        *   **Wait, this is wrong for same-bar execution.** Let me reconsider...
    *   **Corrected Logic for Flip:**
        *   When `pending_exit` includes `'entry_side'`, after executing the exit, immediately check if the entry window should open and process the entry on the **same bar**:
            1.  Execute `pending_exit` (close position at open).
            2.  Call `portfolio.complete_pending_exit_and_open_entry_window(entry_side, bar_index)`.
            3.  Call `portfolio.process_command(f'enter_{entry_side}', bar_index, ...)` again.
            4.  If RMM/caps allow, create position immediately at same bar's open (not pending).
    *   **Implementation:** Modify step 14 logic:
        ```python
        # At start of bar:
        if pending_exit is not None:
            portfolio.close_position(exit_price=current_bar['open'], ...)
            if 'entry_side' in pending_exit:
                # Flip scenario - open entry window and try to enter immediately
                portfolio.complete_pending_exit_and_open_entry_window(
                    pending_exit['entry_side'], bar_index
                )
                # Re-process entry command for flip side
                entry_command = f"enter_{pending_exit['entry_side']}"
                flip_result = portfolio.process_command(entry_command, bar_index, ...)
                if flip_result['action'] == 'open_entry_window':
                    # Check RMM and caps
                    if rmm_allows and not_capped:
                        # Create position immediately at same bar open
                        portfolio.create_new_position(
                            entry_price=current_bar['open'], ...
                        )
            pending_exit = None
        ```
    *   **Verification:** Run test from step 15. It must pass.

#### 4.3: Update Existing Backtester Tests

17. **[ ] Identify Broken Backtester Tests**
    *   **Action:** Run the backtester test suite.
    *   **Command:**
        ```bash
        pytest tests/backtester/ -v
        ```
    *   **Expected:** Multiple tests will fail because they expect old behavior (Portfolio Manager executing trades directly).
    *   **Task:** Create a list of all failing test names.

18. **[ ] Fix Broken Backtester Tests**
    *   **File:** `tests/backtester/test_backtester.py` (and related test files)
    *   **Action:** Update each failing test to align with new architecture.
    *   **Common fixes:**
        *   Tests that mock `portfolio.close_position` or `portfolio.create_new_position` need to verify the Backtester calls these, not the Portfolio Manager.
        *   Tests that verify timing of trades should now account for `next_bar_open` execution model.
        *   Update assertions to match the new execution flow.
    *   **Verification:** After each test fix, run `pytest tests/backtester/test_backtester.py::<test_name>` to verify it passes. Continue until all tests pass.

19. **[ ] Run Full Test Suite**
    *   **Action:** Verify all tests pass with 100% coverage.
    *   **Command:**
        ```bash
        pytest --cov=src/trading_platform --cov-report=term-missing
        ```
    *   **Verification:** All tests pass, coverage is 100% for modified files.

---

### Part 5: Adjust Golden Validation Test

20. **[ ] Update TradingView Test Parser for Timestamp Convention**
    *   **File:** `tests/validation/test_strategy_validation.py`
    *   **Action:** Modify the `parse_tradingview_trades` helper function (or wherever TradingView timestamps are parsed).
    *   **Logic:**
        *   When parsing `entry_time` and `exit_time` from TradingView CSV, subtract one hour from each timestamp.
        *   Add this detailed comment above the subtraction:
            ```python
            # TradingView Timestamp Convention Adjustment:
            # TradingView labels bars with their CLOSE time (end of bar),
            # while our platform labels bars with their OPEN time (start of bar).
            # Example: A 1-hour bar from 17:00-18:00 UTC:
            #   - Our platform labels it: 17:00 (bar open time)
            #   - TradingView labels it:  18:00 (bar close time)
            # Both systems execute at the same moment (the bar's open price),
            # but the timestamp labels differ by the bar's duration.
            # This -1 hour adjustment aligns the labels for 1:1 comparison.
            # For other timeframes, adjust accordingly (e.g., -4 hours for 4H bars).
            ```

21. **[ ] Tighten Golden Validation Tolerances**
    *   **File:** `tests/validation/test_strategy_validation.py`
    *   **Action:** Update the `TRADE_VALIDATION_TOLERANCES` dictionary.
    *   **Changes:**
        *   Set `"entry_time": timedelta(hours=0)` (exact match after timestamp adjustment).
        *   Set `"exit_time": timedelta(hours=0)` (exact match after timestamp adjustment).
        *   Set `"entry_price": 0.00001` (0.1 pip for forex).
        *   Set `"exit_price": 0.00001` (0.1 pip for forex).
        *   Set `"trade_pnl": 1.00` (tighter than before).
        *   Set `"total_pnl": 5.00` (tighter than before).

22. **[ ] Create Integration Test for Next Bar Open Execution**
    *   **File:** `tests/backtester/test_execution_model_integration.py` (new file)
    *   **Action:** Create a comprehensive integration test that verifies the complete next_bar_open execution flow without TradingView dependency.
    *   **Test name:** `test_next_bar_open_execution_model_complete_flow`
    *   **Logic:**
        *   Create a simple DataFrame with 10 bars, with known OHLC values.
        *   Create a strategy that:
            *   Bar 1: Signal to enter long
            *   Bar 4: Signal to exit long
            *   Bar 6: Signal to enter short
            *   Bar 9: Signal to exit short
        *   Run backtest with `execution_model: "next_bar_open"`.
        *   Assert:
            *   Trade 1 (long): Entry at bar 2 open, exit at bar 5 open.
            *   Trade 2 (short): Entry at bar 7 open, exit at bar 10 open (if bar 10 exists).
            *   Entry/exit prices match the respective bar open prices exactly.
        *   This test serves as a smoke test for the entire execution model before running golden validation.

23. **[ ] Run Golden Validation Test**
    *   **Action:** Execute the golden validation test for the EMA crossover strategy.
    *   **Command:**
        ```bash
        pytest -m validation -k "ema_crossover" -v
        ```
    *   **Verification:** The test should pass with near-zero tolerance on prices and exact match on times (after timestamp adjustment).
    *   **If test fails:** Investigate discrepancies:
        *   Check that EMA crossover strategy YAML exactly matches TradingView PineScript.
        *   Verify OHLCV data is identical.
        *   Review first 3 trades manually to understand any systematic differences.

---

### Part 6: Documentation

24. **[ ] Document New Architecture**
    *   **Action:** Create a new documentation file.
    *   **File:** `docs/architecture/execution_model.md`
    *   **Content Structure:**
        1.  **Overview:** Explain the separation of concerns between `Backtester` (execution timing) and `PortfolioManager` (state tracking and decisions).
        2.  **Action Descriptors:** Define the structure and purpose of action descriptor dictionaries returned by Portfolio Manager and REM.
        3.  **Execution Models:**
            *   `current_bar_close`: Immediate execution at signal bar's close (legacy, unrealistic).
            *   `next_bar_open`: Deferred execution at next bar's open (realistic, industry standard).
        4.  **Execution Flow Diagrams:**
            *   Flowchart for simple entry/exit with both execution models.
            *   Flowchart for same-bar flip scenario with `next_bar_open`.
            *   Flowchart for REM-based exit with `next_bar_open`.
        5.  **State Management:** Explain `_pending_exit` flag and entry window management.
        6.  **TradingView Timestamp Convention:** Document the bar close time vs bar open time labeling difference and why we adjust by -1 hour in tests.
        7.  **Testing Strategy:** Explain how integration tests and golden validation tests verify this architecture.

25. **[ ] Update RunConfig Schema Documentation**
    *   **File:** `src/trading_platform/core/config.py` (docstring for `execution_model` field)
    *   **Action:** Expand the description for the `execution_model` field in the `RunConfig` class.
    *   **New description:**
        ```python
        execution_model: Literal["current_bar_close", "next_bar_open"] = Field(
            "current_bar_close",
            description=(
                "Execution model for entries and exits. "
                "'current_bar_close' executes trades immediately at the signal bar's close price "
                "(unrealistic, but useful for rapid prototyping). "
                "'next_bar_open' defers execution to the next bar's open price "
                "(realistic, industry standard, matches TradingView behavior). "
                "For golden validation testing, always use 'next_bar_open'. "
                "See docs/architecture/execution_model.md for details."
            ),
        )
        ```

26. **[ ] Add Comment in PortfolioManager About Executor Responsibility**
    *   **File:** `src/trading_platform/portfolio/portfolio.py`
    *   **Action:** Add a module-level docstring or class-level comment explaining the design.
    *   **Content:**
        ```python
        """
        Portfolio Manager - State Tracking and Decision Making

        The Portfolio Manager is responsible for:
        1. Tracking portfolio state (cash, positions, trades)
        2. Making decisions about when positions should be opened or closed
        3. Managing entry window state for command-based strategies

        The Portfolio Manager does NOT execute trades directly. Instead, it returns
        "action descriptors" - dictionaries that tell the caller (Backtester or
        Execution Layer) what action should be taken. The caller is responsible for
        determining WHEN to execute (e.g., current bar close vs next bar open).

        This separation of concerns allows the same Portfolio Manager logic to be
        used in both backtesting (with configurable execution models) and live
        trading (with real-time execution).

        See docs/architecture/execution_model.md for detailed architecture.
        """
        ```

---

## Completion Checklist

Before marking this task as complete, verify:

- [ ] All 26 tasks have been completed in order
- [ ] All tests pass: `pytest -v`
- [ ] 100% code coverage maintained: `pytest --cov=src/trading_platform --cov-report=term-missing`
- [ ] Golden validation test passes: `pytest -m validation -k "ema_crossover" -v`
- [ ] Documentation is complete: `docs/architecture/execution_model.md` exists and is accurate
- [ ] No uncommitted changes remain (commit your work)
- [ ] Branch is ready for PR: `git push origin feature/execution-model-refactor`

---

## Key Design Decisions Documented

### Decision 1: Portfolio Manager Returns Descriptors, Not Executes

**Rationale:** Allows the same Portfolio Manager to be used in backtesting (with configurable execution timing) and live trading (with real execution) without duplicating logic.

### Decision 2: Pending Exit Flag Prevents Inconsistent State

**Rationale:** Opening an entry window while a position still exists (before exit completes) creates logical inconsistencies. The `_pending_exit` flag ensures the entry window only opens after the exit is processed.

### Decision 3: REM Calculates Exit Prices, Backtester Overrides for Execution Model

**Rationale:** REM knows the precise stop/TP levels and intra-bar trigger prices. For `current_bar_close`, we use REM's calculated price. For `next_bar_open`, the Backtester overrides with next bar's open price. This keeps REM's logic intact while allowing execution model flexibility.

### Decision 4: Same-Bar Flip Executes Both Trades at Next Bar Open

**Rationale:** For a strategy that flips on bar N (exit long + enter short), both actions should execute at bar N+1 open at the same price. This is realistic (you can't exit and re-enter instantaneously in real markets at two different prices) and matches TradingView behavior.

### Decision 5: TradingView Timestamp Adjustment in Tests Only

**Rationale:** The -1 hour adjustment is purely a labeling convention difference, not an execution timing difference. We adjust in tests to enable 1:1 comparison, but the core platform logic remains unchanged.

---

## Expected Outcome

After completing all tasks:

1. **EMA crossover golden validation test passes** with near-zero tolerance on prices and exact match on times.
2. **Total PnL difference < $5.00** between platform and TradingView.
3. **All 243 trades** match TradingView in timing, price, and sequence.
4. **Architecture is clean** with clear separation between state management (Portfolio Manager) and execution timing (Backtester).
5. **Same-bar flips work correctly** for both `current_bar_close` and `next_bar_open` execution models.
6. **REM-based exits respect execution model** (stop-loss/take-profit execute at next bar open when configured).
7. **Documentation is complete** explaining the new architecture and design decisions.

---

## Troubleshooting Guide

### Issue: Tests fail with "unexpected close_position call"

**Cause:** Test is mocking Portfolio Manager methods that are no longer called directly.

**Fix:** Update test to verify Backtester calls `portfolio.close_position`, not Portfolio Manager's internal methods.

---

### Issue: Trades are out of sequence

**Cause:** Execution order in Backtester main loop is incorrect.

**Fix:** Ensure order is: (1) Execute pending exit, (2) Execute pending entry, (3) Check REM exits, (4) Process strategy command.

---

### Issue: Entry window opens before exit completes

**Cause:** `_pending_exit` flag not set correctly or entry window logic doesn't check flag.

**Fix:** Verify `_handle_entry_command` sets `_pending_exit = True` before returning `should_close` descriptor, and doesn't set entry window until `complete_pending_exit_and_open_entry_window` is called.

---

### Issue: Same-bar flip executes at two different prices

**Cause:** Exit and entry are being executed on different bars instead of same bar.

**Fix:** Review flip logic in Backtester (step 16). After executing `pending_exit` for a flip, immediately open entry window and process entry on the same bar at the same open price.

---

### Issue: Golden validation still has significant PnL difference

**Cause:** Multiple possible causes:
1. OHLCV data doesn't match TradingView exactly
2. Strategy YAML doesn't match PineScript logic
3. Indicator calculations differ
4. Execution model not applied correctly

**Fix:**
1. Verify OHLCV data matches TradingView export exactly (compare first 10 rows)
2. Review strategy YAML vs PineScript line-by-line
3. Run indicator validation tests (Phase 1 of golden validation plan)
4. Add debug logging to Backtester to trace execution timing
5. Manually compare first 3 trades between platform and TradingView

---

## Notes

- This refactor maintains 100% test coverage at every step.
- The `_pending_exit` flag is an internal implementation detail and should not be exposed in the public API.
- The `complete_pending_exit_and_open_entry_window` method is public because the Backtester needs to call it, but it should only be called after a `close_position` call.
- The REM's `check_exits_intrabar` method is new and separate from the existing `check_exits` method to maintain backwards compatibility during the transition.
- All modified files should have their docstrings updated to reflect the new architecture.
- Consider adding type hints for action descriptor dictionaries using `TypedDict` in a future refactor.

---

**End of Implementation Plan**
