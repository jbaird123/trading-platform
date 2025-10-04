# PnL Reporting and Calculation Implementation Plan

**Objective:** This is a consolidated plan to refactor all PnL calculations for maximum clarity and realism. It covers both the reporting of **closed trades** in the brief and the calculation of **unrealized PnL** for open positions during a backtest.

**Branch Name:** `feature/pnl-reporting-clarity`

---

### Part 1: PnL Reporting for Closed Trades

**Goal:** Refactor the `Trade` object and reporting to provide a clear, auditable waterfall from ideal PnL to net PnL.

1.  **[ ] Modify the `Trade` Dataclass.**
    *   **File:** `src/trading_platform/portfolio/trade.py`
    *   **Action:**
        1.  Remove the line: `pnl_gross: float = 0.0  # Gross PnL before costs`
        2.  Add a new line: `pnl_movement: float = 0.0  # PnL from mid-price movement`

2.  **[ ] Update the `Position` Dataclass.**
    *   **File:** `src/trading_platform/portfolio/position.py`
    *   **Action:** Add a new field `entry_mid_price: float` to the `Position` dataclass.

3.  **[ ] Update `PortfolioManager` to Store `entry_mid_price`.**
    *   **File:** `src/trading_platform/portfolio/portfolio.py`
    *   **Action:** Modify the `create_new_position` method to pass the `entry_price` (which is the mid-price) to the new `entry_mid_price` field of the `Position` object.

4.  **[ ] Create a New Test for the PnL Waterfall.**
    *   **File:** `tests/portfolio/test_trade_creation.py` (create this new file).
    *   **Action:** Add a new test function, `test_pnl_calculation_waterfall`.
    *   **Logic:** For a sample closed trade, assert that:
        1.  `trade.pnl_movement` equals the profit from `exit_mid_price - entry_mid_price`.
        2.  `trade.cost_breakdown['spread']` equals the total spread cost.
        3.  `trade.pnl` equals `pnl_movement - total_costs`.

5.  **[ ] Refactor `PortfolioManager.close_position` Method.**
    *   **File:** `src/trading_platform/portfolio/portfolio.py`
    *   **Action:** Rewrite the PnL calculation logic inside the `close_position` method to use the new `pnl_movement` field and correctly calculate the final `pnl` by subtracting all costs.

6.  **[ ] Update JSON Schema for the Brief.**
    *   **File:** `docs/schemas/brief.schema.json`
    *   **Action:** In the `definitions.trade.properties` section, delete the `pnl_gross` property and add the `pnl_movement` property with the description: "The theoretical profit or loss from pure price movement, calculated from the mid-price at entry to the mid-price at exit, excluding all transaction costs."

7.  **[ ] Update All Failing Tests for Closed Trades.**
    *   **Action:** Run `poetry run pytest`. Many tests will fail due to the removal of `pnl_gross`. Update each failing test to use the new, clearer fields (`pnl`, `pnl_movement`).

---

### Part 2: Unrealized PnL for Open Positions

**Goal:** Ensure the real-time, unrealized PnL of an open position correctly reflects the full spread cost, mimicking a live broker.

8.  **[ ] Update `Position` Dataclass for Unrealized PnL.**
    *   **File:** `src/trading_platform/portfolio/position.py`
    *   **Action:** Add a new field: `unrealized_pnl: float = 0.0`.

9.  **[ ] Create Test for Unrealized PnL.**
    *   **File:** `tests/portfolio/test_pnl_realism.py` (create this new file).
    *   **Action:** Add a test function `test_unrealized_pnl_reflects_full_spread`.
    *   **Logic:** Create a `PortfolioManager` and an open `Position`. Call the method that updates the position on a new bar. Assert that `portfolio.current_position.unrealized_pnl` is calculated using the `cost_model.get_exit_price()`, correctly reflecting the full spread.

10. **[ ] Implement Unrealized PnL Calculation.**
    *   **File:** `src/trading_platform/portfolio/portfolio.py`
    *   **Action:** Locate the `_update_position_metrics` method, which is called on every bar for an open position.
    *   **Logic:** Inside this method, add the logic to calculate the `unrealized_pnl` using `self._cost_model.get_exit_price(current_bar['close'], position.side)` and update the `position.unrealized_pnl` field.

11. **[ ] Final Verification.**
    *   **Action:** Run `poetry run pytest` one last time to ensure all new and existing tests pass.