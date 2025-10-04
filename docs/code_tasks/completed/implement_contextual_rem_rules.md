# Implementation Plan: Context-Aware Risk Management

**Epic:** Context-Aware Risk Management

**Description:** This feature will enable the Risk & Exit Manager (REM) to use dynamic, signal-specific context provided by a Strategy to calculate exit levels. This allows for more sophisticated risk management, such as placing a stop-loss relative to a dynamically identified price level (e.g., an order block) rather than a static offset from the entry price.

**High-Level Acceptance Criteria:**
- A backtest run using a strategy that passes contextual data and a REM that consumes it will correctly calculate and trigger stop-losses based on that context.
- All new logic must be covered by unit and integration tests, maintaining 100% code coverage.

---

### Branching Instructions

Please create a new feature branch for this implementation:
`git checkout -b feat/contextual-rem-rules`

---

### Task List

#### Part 1: Enhance Signal Generation (Strategy Engine)

*Objective: Modify the strategy engine to generate signals as rich objects containing a `command` and a `context` dictionary, instead of simple strings.*

1.  **[X] Task 1.1: Define `Signal` Data Structure**
    -   **File to Create:** `src/trading_platform/core/signal.py`
    -   **Action:** Create a new Pydantic `BaseModel` or a standard Python `@dataclass` named `Signal`.
    -   **Details:**
        -   The class must contain two fields:
            -   `command: str` (e.g., 'enter_long', 'exit_short')
            -   `context: dict[str, Any] = Field(default_factory=dict)`
    -   **Acceptance Criteria:** The new class is defined in the specified file with correct type hints.

2.  **[X] Task 1.2: Create Tests for `YAMLStrategy` Context Parsing**
    -   **File to Modify:** `tests/strategy/test_yaml_strategy.py`
    -   **Action:** Add a new test case to verify that the `YAMLStrategy` correctly parses the new `context` block from a strategy YAML file.
    -   **Details:** The test should load a sample YAML string containing a `long_entry_rules` block with a `context` definition and assert that the parsed rule object contains the context mapping.
    -   **Acceptance Criteria:** The new test fails with an error indicating the `context` block is not being processed.

3.  **[X] Task 1.3: Implement `context` Parsing in `YAMLStrategy`**
    -   **File to Modify:** `src/trading_platform/strategy/yaml_strategy.py`
    -   **Action:** Modify the `compile_strategy` function or the internal rule parsing logic.
    -   **Details:** The parser must be updated to recognize the `context` key within a rule block. It should parse the dictionary of `name: {ref: feature_name}` and store this mapping within the internal representation of the rule.
    -   **Acceptance Criteria:** The test from Task 1.2 now passes.

4.  **[X] Task 1.4: Create Tests for `Signal` Object Generation**
    -   **File to Modify:** `tests/strategy/test_yaml_strategy.py`
    -   **Action:** Add a new test case to `test_generate_signals`.
    -   **Details:** This test will use a strategy config with a `context` block. It will assert that the `generate_signals` method produces a pandas Series with `dtype=object`, and that the non-null elements in the series are `Signal` objects with a correctly populated `context` dictionary (i.e., the live values of the referenced features).
    -   **Acceptance Criteria:** The new test fails with an error, as the `generate_signals` method still produces strings.

5.  **[X] Task 1.5: Implement `Signal` Object Generation**
    -   **File to Modify:** `src/trading_platform/strategy/yaml_strategy.py`
    -   **Action:** Modify the `generate_signals` method.
    -   **Details:**
        -   When a rule's conditions are met, the method must now instantiate a `Signal` object instead of returning a string command.
        -   It must populate the `signal.context` dictionary by looking up the live values of the features defined in the rule's context mapping.
        -   The returned pandas Series must be explicitly created with `dtype=object`.
    -   **Acceptance Criteria:** The test from Task 1.4 now passes.

#### Part 2: Enhance Risk & Exit Manager (REM)

*Objective: Teach the REM to understand and process the new `reference_price` rule type using the context from the `Signal` object.*

6.  **[X] Task 2.1: Create Test for Contextual Stop-Loss Rule**
    -   **File to Modify:** `tests/risk_manager/test_rem_core.py`
    -   **Action:** Add a new unit test for the `RiskExitManager`.
    -   **Details:**
        -   The test will initialize the `RiskExitManager` with our `order_block_context.yaml` configuration.
        -   It will call the exit checking method (e.g., `check_exits`) with a mock `Signal` object containing a `context` dictionary (e.g., `{'order_block_low': 1.2000}`).
        -   It must assert that the calculated stop-loss price is the correct value based on the context and the pip offset.
    -   **Acceptance Criteria:** The test fails, as the REM does not know how to process the `reference_price` rule type.

7.  **[X] Task 2.2: Implement Contextual Rule Logic in REM**
    -   **File to Modify:** `src/trading_platform/risk_manager/core.py`
    -   **Action:** Modify the `RiskExitManager`'s exit checking method (e.g., `check_exits`).
    -   **Details:**
        -   The method signature must be updated to accept the current bar's `Signal` object.
        -   Add logic to handle rules where `type` is `reference_price`.
        -   This logic must parse the `reference_point` string (e.g., "context.order_block_low") to get the key.
        -   It must then look up this key in the `signal.context` dictionary to retrieve the base price.
        -   It will then use the `RuleTranslator` (or similar logic) to convert the `offset` (e.g., `pips: -5`) into a price delta.
        -   Finally, it calculates and returns the absolute stop-loss price.
    -   **Acceptance Criteria:** The test from Task 2.1 now passes.

#### Part 3: Integrate in Backtester

*Objective: Plumb the new `Signal` object from the strategy through to the REM in the main backtesting loop.*

8.  **[X] Task 3.1: Create Integration Test**
    -   **File to Create:** `tests/backtester/test_contextual_rem_integration.py`
    -   **Action:** Create a new end-to-end integration test.
    -   **Details:**
        -   The test will run a full backtest using `configs/strategies/institutional_order_block/run_config.yaml`.
        -   It will assert that at least one trade is generated.
        -   It will then inspect the first generated `Trade` object and assert that its `exit_reason` is `stop_loss` (this may require crafting the test data to ensure the stop is hit).
        -   It can also assert that the recorded stop-loss price on the trade object matches the expected calculation.
    -   **Acceptance Criteria:** The test fails, likely because the `Signal` object is not being passed from the backtester loop to the REM.

9.  **[X] Task 3.2: Update Backtester Loop**
    -   **File to Modify:** `src/trading_platform/backtester/core.py`
    -   **Action:** Modify the main `run_backtest` simulation loop.
    -   **Details:**
        -   The loop iterates over the `signals` Series, which now contains `Signal` objects.
        -   On each bar, the `Signal` object (or `None`) must be retrieved.
        -   This `Signal` object must be passed as an argument to the `RiskExitManager`'s exit checking method.
    -   **Acceptance Criteria:** The integration test from Task 3.1 now passes.
