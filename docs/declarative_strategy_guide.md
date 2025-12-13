# Guide to Declarative Strategies

This document explains the philosophy, structure, and interaction of the declarative YAML-based strategy system.

## 1. The Two-Path Philosophy: YAML vs. Python

The trading platform supports two distinct methods for defining strategy logic, each with its own purpose:

### Declarative YAML Strategies (The "No-Code" Path)

-   **Purpose:** To enable rapid prototyping, iteration, and testing of common trading ideas without writing any Python code.
-   **Best For:** Strategies that are combinations of standard indicators and simple, reusable rules (e.g., "enter when the fast EMA crosses above the slow EMA and RSI is below 30").
-   **Limitation:** This path is intentionally not designed to handle every possible complex scenario. Its power comes from its simplicity and reusability.

### Custom Python Strategies (The "Pro-Code" Path)

-   **Purpose:** To provide unlimited power and flexibility for complex, unique, or stateful trading logic.
-   **Best For:**
    -   Strategies involving multi-timeframe analysis.
    -   Complex pattern detection (e.g., advanced order blocks, harmonic patterns).
    -   Strategies that require custom state management between bars.
    -   Any logic that cannot be expressed through the existing YAML predicates.
-   **Implementation:** Create a Python class that inherits from a `BaseStrategy` and implement the required methods.

**Golden Rule:** Start with YAML. If you find yourself fighting the structure or wishing for an `if/else` statement, it's a sign that you should move to a custom Python strategy.

---

## 2. The Configuration Ecosystem

A backtest is defined by a set of interacting YAML files, orchestrated by a master `run_config.yaml`.

### `run_config.yaml` (The Conductor)
This is the master file that binds all other components together for a single, reproducible run.

-   **Role:** Specifies the what, who, and how of a backtest.
-   **Key Sections:**
    -   `data_request`: Defines the instrument, timeframe, and date range.
    -   `strategy_path`: The path to your `strategy.yaml` file.
    -   `rem_path`: The path to your `rem.yaml` file.
    -   `rmm_path` (Optional): The path to your `rmm.yaml` file.

*Example:*
```yaml
name: "My EMA Crossover Backtest"
data_request:
  symbol: 'EURUSD'
  timeframe: '1H'
  start: '2022-01-01'
  end: '2023-01-01'

strategy_path: 'config/strategy/ema_crossover.yaml'
rem_path: 'config/rem/trailing_stops.yaml'
rmm_path: 'config/rmm/trend_filter.yaml'
```

### `strategy.yaml` (The Signal Generator)

-   **Role:** **Signal generation only.** Its sole purpose is to analyze market data and generate `enter_long`, `enter_short`, `exit_long`, or `exit_short` signals.
-   **Key Sections:**
    -   `features`: A list of indicators (e.g., EMA, RSI) to be calculated before rules are evaluated.
    -   `long_entry_rules`: A set of conditions that, if met, generate an `enter_long` signal.
    -   `long_exit_rules`: A set of conditions that, if met, generate an `exit_long` signal.
    -   `context` (Advanced): An optional block within a rule that passes dynamic, bar-specific data along with the signal for use by other components (like the REM).

### `rem.yaml` (The In-Trade Risk Manager)

-   **Role:** Manages an **open position**. It defines the rules for when to exit a trade due to risk management (stop-loss) or profit-taking.
-   **Key Sections:**
    -   `stop_loss`: A list of rules for cutting losses (e.g., fixed pip offset, ATR-based).
    -   `take_profit`: A list of rules for taking profits.
    -   `trailing_stop`: Rules for a dynamic, trailing stop-loss.

### `rmm.yaml` (The Market Condition Filter)

-   **Role:** Acts as a high-level filter. It classifies the market into a "regime" (e.g., `trending`, `ranging`, `volatile`) and tells the backtester whether trading is permitted under the current conditions.
-   **Key Sections:**
    -   `features`: Indicators used to classify the market.
    -   `regimes`: Definitions of different market states based on feature values.
    -   `policy`: Rules that map regimes to actions (e.g., `allow_labels: [trending]`).

---

## 3. Data Flow on a Single Bar

Here is how the components interact during a single bar of a backtest:

1.  **Data In:** The `Backtester` provides the current bar's data (`Open`, `High`, `Low`, `Close`) to the Strategy and RMM engines.
2.  **Parallel Processing:**
    -   The `StrategyEngine` calculates its features and evaluates its entry/exit rules. It produces a `Signal` object (e.g., `Signal(command='enter_long', context={'order_block_low': 1.123})`).
    -   The `RMMEngine` calculates its features and determines the current market regime (e.g., `Regime(label='trending')`).
3.  **Filtering:** The `Backtester` checks the RMM's policy. Is trading allowed in a `trending` regime? Let's assume yes.
4.  **Action - New Entry:**
    -   The `Backtester` sees the `enter_long` command from the `Signal`.
    -   It consults the `rem.yaml` configuration to determine the stop-loss.
    -   It passes the `Signal` (with its context) and the REM rule to the `RuleTranslator`.
    -   The `RuleTranslator` calculates the canonical stop-loss price.
    -   The `Backtester` sends a final, canonical order (entry price, stop-loss price, etc.) to the `PortfolioManager`.
5.  **Action - Position Management:**
    -   If a position is already open, the `Backtester` passes the current bar's data and the `Signal` to the `RiskExitManager`.
    -   The `REM` checks if any of its stop-loss or take-profit rules have been triggered by the current price action.
    -   The `StrategyEngine` checks if its own `exit_long` rules have been met.
    -   The `Backtester` enforces the exit precedence rule (e.g., REM exits first) and instructs the `PortfolioManager` to close the position if an exit is triggered.

This cycle repeats for every bar in the dataset.
