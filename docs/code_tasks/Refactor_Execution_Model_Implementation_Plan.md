# Refactor Execution Model Implementation Plan (v2)

**Objective:** Refactor the `PortfolioManager`, `Backtester`, and `RiskExitManager` to cleanly separate state management from execution timing. This will enable a true `next_bar_open` execution model for both entries and exits, which is required to achieve perfect alignment with TradingView golden validation data.

---

## Instructions for Developer

You will be refactoring core components of the backtesting engine. Follow these instructions precisely. Do not deviate from the plan.

First, create a new branch for this work:
```bash
git checkout -b feature/execution-model-refactor
```

Execute the following tasks in the exact order they are listed.

---

## Task List

### Part 1: Restore Stable Baseline

1.  **[ ] Revert Local Changes**
    *   **Action:** Revert all uncommitted changes in your local working directory to match the `HEAD` of your current branch. This is critical to ensure we start from a clean, known-good state.
    *   **Command:**
        ```bash
        git checkout -- .
        ```

### Part 2: Refactor `PortfolioManager` to Return Action Descriptors

The goal of this part is to stop the `PortfolioManager` from executing trades directly. It will be modified to return a dictionary describing the action that *should* be taken, while still managing its own internal state.

2.  **[ ] Create Tests for `process_command` Refactor**
    *   **File:** `tests/portfolio/test_portfolio_manager.py`
    *   **Action:** Create a new test function `test_process_command_returns_action_descriptors`.
    *   **Logic:**
        *   Instantiate a `PortfolioManager`.
        *   Simulate an active `long` position.
        *   Call `portfolio.process_command` with a `short` command (a flip).
        *   Assert that the returned value is a dictionary equal to: `{'action': 'should_close', 'reason': 'opposite_signal', 'side': 'short'}`.
        *   Assert that `portfolio.current_position` is **not** `None` (i.e., the position was not closed by `process_command`).
        *   Assert that `portfolio.is_entry_window_open('short', bar_index)` is `True` (the entry window state was updated internally).

3.  **[ ] Refactor `PortfolioManager.process_command`**
    *   **File:** `src/trading_platform/portfolio/portfolio.py`
    *   **Action:** Modify the `_handle_entry_command` and `_handle_exit_command` methods.
    *   **`_handle_entry_command` Logic:**
        *   In the section for an opposite position, **remove** the call to `self.close_position(...)` and instead `return {'action': 'should_close', 'reason': 'opposite_signal', 'side': side}`.
        *   **Keep** the logic that sets the entry window: `self._entry_windows[side] = (bar_index, None)`.
    *   **`_handle_exit_command` Logic:**
        *   In the section for a matching exit signal, **remove** the call to `self.close_position(...)` and instead `return {'action': 'should_close', 'reason': 'signal', 'side': side}`.
    *   **Verification:** Run the tests from step 2. They must pass, and code coverage must be 100%.

### Part 3: Refactor `RiskExitManager` for Deferred Execution

This part ensures that REM-based exits (stop-loss/take-profit) also respect the execution model.

4.  **[ ] Create Tests for `check_exits` Refactor**
    *   **File:** `tests/risk_manager/test_rem.py` (or a new test file if more appropriate).
    *   **Action:** Create a test `test_check_exits_returns_descriptor`.
    *   **Logic:**
        *   Set up a `RiskExitManager` with a simple stop-loss rule.
        *   Create a mock position and a `current_bar` that would trigger the stop-loss.
        *   Call `rem.check_exits(position, current_bar)`.
        *   Assert that the returned value is a dictionary like `{'action': 'should_close', 'reason': 'stop_loss'}`. It must **not** contain an `'exit_price'` key.

5.  **[ ] Refactor `RiskExitManager.check_exits`**
    *   **File:** `src/trading_platform/risk_manager/rem.py`
    *   **Action:** Modify the `check_exits` method.
    *   **Logic:**
        *   Change the logic so that when an exit condition (stop-loss or take-profit) is met, it no longer calculates the `exit_price`.
        *   Instead, it should return a dictionary descriptor, e.g., `{'action': 'should_close', 'reason': 'stop_loss'}` or `{'action': 'should_close', 'reason': 'take_profit'}`.
    *   **Verification:** The test from step 4 must pass with 100% coverage for the modified file.

### Part 4: Empower `Backtester` as the Sole Executor

The `Backtester` will now interpret descriptors from both the `PortfolioManager` and the `RiskExitManager`.

6.  **[ ] Update `run_backtest` to Handle All Descriptors and Flip Logic**
    *   **File:** `src/trading_platform/backtester/core.py`
    *   **Action:** Modify the main loop inside the `run_backtest` function.
    *   **Logic:**
        *   **Execution Order:** Structure the top of the loop to handle pending actions in a specific order to ensure correct same-bar flips:
            1.  Execute `pending_exit` from the previous bar (if it exists).
            2.  Execute `pending_entry` from the previous bar (if it exists).
        *   **REM Exits:** After the `pending` block, call `rem.check_exits(...)`. If it returns a `should_close` descriptor:
            *   If `config.execution_model == 'current_bar_close'`, execute `portfolio.close_position()` immediately.
            *   If `config.execution_model == 'next_bar_open'`, populate the `pending_exit` dictionary and `continue` to the next bar.
        *   **Signal Exits:** After calling `portfolio.process_command(...)`, if the result is a `should_close` descriptor:
            *   If `config.execution_model == 'current_bar_close'`, execute `portfolio.close_position()` immediately.
            *   If `config.execution_model == 'next_bar_open'`, populate `pending_exit`. **Do not** `continue`, to allow a flip entry to be processed in the same loop iteration.

7.  **[ ] Create Tests for New `Backtester` Execution Logic**
    *   **File:** `tests/backtester/test_backtester.py`
    *   **Action:** Create a new test function `test_backtester_handles_next_bar_open_flips_and_rem_exits`.
    *   **Logic:**
        *   **Flip Test:** Set up a `RunConfig` with `execution_model: "next_bar_open"`. Create a signal series that causes a position flip. Assert that the exit of trade 1 and entry of trade 2 happen at the same time (the open of the next bar) and at the same price.
        *   **REM Exit Test:** Set up a `RunConfig` with `execution_model: "next_bar_open"` and a stop-loss in the REM. Create a signal series that opens a position, then create market data that triggers the stop-loss. Assert that the position is closed at the `open` price of the bar *after* the trigger bar.

8.  **[ ] Fix Broken Backtester Tests**
    *   **Action:** Run the entire test suite. The changes in the previous steps will have broken existing tests.
    *   **Logic:** Modify the broken tests to align with the new architecture where the `Backtester` orchestrates all calls to `portfolio.close_position` and `portfolio.create_new_position` based on descriptors.
    *   **Verification:** All tests in the project must pass, and code coverage must be 100%.

### Part 5: Adjust Golden Validation Test

9.  **[ ] Update TradingView Test Parser**
    *   **File:** `tests/validation/test_strategy_validation.py`
    *   **Action:** Modify the `parse_tradingview_trades` helper function.
    *   **Logic:**
        *   When parsing `entry_time` and `exit_time`, subtract one hour.
        *   Add a detailed comment: `_# HACK: Adjust for TradingView's "bar close time" labeling convention. Their timestamp marks the end of the bar, while our platform uses the start. This -1 hour adjustment aligns the labels for a 1:1 comparison, even though the execution moment is identical._`
        *   Set `TRADE_VALIDATION_TOLERANCES` for `entry_time` and `exit_time` to `timedelta(hours=0)`.

10. **[ ] Run Golden Validation Test**
    *   **Action:** Execute the golden validation test for the EMA crossover strategy.
    *   **Command:** `pytest -m validation -k "ema_crossover"`
    *   **Verification:** The test should pass with near-zero tolerance on prices and zero tolerance on time.

### Part 6: Documentation

11. **[ ] Document New Architecture**
    *   **Action:** Create a new documentation file.
    *   **File:** `docs/architecture/execution_model.md`
    *   **Content:**
        *   Explain the separation of concerns between the `Backtester` (execution timing) and `PortfolioManager` (state tracking).
        *   Describe the role of action descriptors.
        *   Illustrate the flow for both `current_bar_close` and `next_bar_open` execution models, including a same-bar flip scenario.
