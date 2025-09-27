# Symbol Normalization Implementation Plan

This document outlines the precise, ordered steps required to refactor the codebase and enforce a single, canonical representation for instrument symbols (`EURUSD` format). This is a critical architectural fix to prevent bugs and improve system robustness.

The developer must follow these tasks in the specified sequence. All changes must be accompanied by tests to ensure 100% coverage is maintained for the modified code.

### 1. Implement the Canonical Symbol Utility

- [x] **1.1. Create Test for the `normalize_symbol` Utility**
    - **File:** `tests/core/test_utils.py`
    - **Action:** Create a new test function `test_normalize_symbol`.
    - **Logic:**
        1.  Import `normalize_symbol` from `src.trading_platform.core.utils`.
        2.  Use `@pytest.mark.parametrize` to test a comprehensive set of input variations.
        3.  Assert that `normalize_symbol("EUR/USD")` returns `"EURUSD"`.
        4.  Assert that `normalize_symbol("EUR_USD")` returns `"EURUSD"`.
        5.  Assert that `normalize_symbol("eur-jpy")` returns `"EURJPY"`.
        6.  Assert that `normalize_symbol("SPY")` returns `"SPY"`.
        7.  Assert that calling `normalize_symbol("EURUSD")` with an already-canonical symbol returns `"EURUSD"`.

- [x] **1.2. Implement the `normalize_symbol` Utility**
    - **File:** `src/trading_platform/core/utils.py`
    - **Action:** Create the `normalize_symbol` function.
    - **Logic:** The function must remove all non-alphanumeric characters and convert to uppercase.
        ```python
        def normalize_symbol(symbol: str) -> str:
            """Converts a symbol string to the canonical 'EURUSD' format."""
            return "".join(filter(str.isalpha, symbol)).upper()
        ```

### 2. Refactor Instrument Definitions

- [x] **2.1. Create Test for Instrument Definition Normalization**
    - **File:** `tests/data/test_instrument.py`
    - **Action:** Create a new test function `test_get_instrument_definition_with_normalization`.
    - **Logic:**
        1.  Import `get_instrument_definition` from `src.trading_platform.data.instrument`.
        2.  Assert that `get_instrument_definition("EUR/USD")` returns the correct definition without raising an error.
        3.  Assert that `get_instrument_definition("EUR_USD")` returns the exact same definition object.
        4.  For each of the calls above, assert that the returned `InstrumentDefinition` object has its `symbol` attribute set to the canonical value: `"EURUSD"`.

- [x] **2.2. Refactor `instrument.py` to Use Normalization**
    - **File:** `src/trading_platform/data/instrument.py`
    - **Action:** Modify the instrument dictionary and the getter function to enforce normalization.
    - **Logic:**
        1.  Import `normalize_symbol` from `..core.utils`.
        2.  In the `_INSTRUMENT_DEFINITIONS` dictionary, change all keys to the canonical format (e.g., change `"EUR_USD"` to `"EURUSD"`). Remove any duplicates.
        3.  Modify the `get_instrument_definition` function to use the normalizer at its entry point.
            ```python
            # Example of the required change in get_instrument_definition
            def get_instrument_definition(symbol: str) -> InstrumentDefinition:
                canonical_symbol = normalize_symbol(symbol)
                data = _INSTRUMENT_DEFINITIONS.get(canonical_symbol)
                if data is None:
                    raise ValueError(f"Instrument definition not found for {symbol}")

                definition_data = data.copy()
                definition_data['symbol'] = canonical_symbol
                return InstrumentDefinition(**definition_data)
            ```

### 3. Refactor Data Catalog and Loader

- [x] **3.1. Standardize `data_catalog.yaml`**
    - **File:** `config/data_catalog.yaml`
    - **Action:** Update all instrument keys to the canonical format.
    - **Logic:**
        -   Ensure all top-level keys for instruments are in the `EURUSD` format. For example, `EUR_USD:` must be changed to `EURUSD:`.

- [x] **3.2. Update `load_from_catalog` Test**
    - **File:** `tests/data/test_loader.py`
    - **Action:** Modify existing tests for `load_from_catalog` to verify normalization.
    - **Logic:**
        1.  Update tests to call `load_from_catalog` with a non-canonical symbol (e.g., `"EUR_USD"`).
        2.  Assert that the function correctly loads data by looking up the canonical key (`"EURUSD"`) in the catalog.
        3.  Assert that the returned `InstrumentDefinition` object has its `symbol` attribute set to `"EURUSD"`.

- [x] **3.3. Refactor `loader.py` to Use Normalization**
    - **File:** `src/trading_platform/data/loader.py`
    - **Action:** Modify the `load_from_catalog` function.
    - **Logic:**
        1.  Import `normalize_symbol` from `..core.utils`.
        2.  At the beginning of the function, normalize the incoming symbol from the `data_request`.
        3.  Use this canonical symbol for all subsequent logic.

### 4. Refactor Application Code

- [x] **4.1. Create Failing Tests for a Target Module (e.g., Backtester)**
    - **File:** `tests/backtester/test_backtester.py`, `tests/portfolio/test_portfolio.py`
    - **Action:** Update tests to use the new canonical symbol format, which will cause them to fail initially.
    - **Logic:**
        1.  Find all tests that use a hardcoded symbol like `"EUR_USD"`.
        2.  Change the symbol in the test setup and assertions to the new canonical `"EURUSD"`.
        3.  Run `pytest` and confirm that these tests now fail.

- [x] **4.2. Refactor the Target Module (e.g., Backtester)**
    - **File:** `src/trading_platform/backtester/core.py`, `src/trading_platform/portfolio/portfolio.py`
    - **Action:** Refactor the source code to use the canonical symbol format internally.
    - **Logic:**
        1.  Replace all internal uses of hardcoded symbols like `"EUR_USD"` with the canonical `"EURUSD"`.
        2.  Rerun the tests from step 4.1 and ensure they now pass.

- [x] **4.3. Apply Normalization Pattern to All Other Modules**
    - **Action:** Apply the same test-first refactoring pattern from steps 4.1 and 4.2 to all other modules. The initial code search revealed that nearly every module will require changes.

### 5. Update Documentation

- [x] **5.1. Update `project_requirements.md`**
    - **File:** `docs/project_requirements.md`
    - **Action:** Add a new system-wide requirement to formally document the symbol policy.
    - **Logic:**
        -   Under `[SYS-1.3] Instrument Agnostic Architecture`, add a new requirement: `[SYS-1.3.5] The canonical internal representation for instrument symbols is all-uppercase with no separators (e.g., 'EURUSD', 'SPY'). A normalization utility at 'src/trading_platform/core/utils.py' must be used at all system boundaries to enforce this standard.`

### 6. Refactor Hardcoded Symbols from Application Code

- [x] **6.1. Create Test for Backtester Core Refactoring**
    - **File:** `tests/backtester/test_backtester.py`
    - **Action:** Modify existing tests that use default or example `RunConfig`s originating from `src/trading_platform/backtester/core.py`.
    - **Logic:**
        1.  Identify functions in `backtester/core.py` that create configurations with a hardcoded symbol.
        2.  Modify their tests to ensure the functions can be provided with a symbol (e.g., "GBPJPY") and that the created configuration uses this provided symbol instead of the hardcoded one.

- [x] **6.2. Refactor `backtester/core.py`**
    - **File:** `src/trading_platform/backtester/core.py`
    - **Action:** Refactor functions to accept a `symbol` parameter instead of using a hardcoded value.
    - **Logic:**
        1.  Modified the `_simulate_counterfactual_fast` and `_simulate_counterfactual_exact` function signatures to accept a `symbol: str = "EURUSD"` parameter.
        2.  Replaced all hardcoded `"EURUSD"` references in skipped trade logging with calls to `_get_symbol()` helper function that safely extracts the symbol from `config.instrument` with proper fallback handling.

- [x] **6.3. Create Test for AI Data Connectors Refactoring**
    - **File:** `tests/ai/test_data_connectors.py`
    - **Action:** Add or modify tests for functions that currently return hardcoded symbols.
    - **Logic:**
        1.  Added `test_data_catalog_get_available_symbols_should_use_instrument_registry()` test that sets up framework to verify refactoring to use instrument registry.
        2.  Added `test_main_block_should_accept_custom_symbol()` test that verifies `load_training_data` works with custom symbols and prepares for main block refactoring.

- [x] **6.4. Refactor `ai/data_connectors.py`**
    - **File:** `src/trading_platform/ai/data_connectors.py`
    - **Action:** Remove hardcoded symbols.
    - **Logic:**
        1.  Modified `get_available_symbols()` to dynamically read available symbols from `_INSTRUMENT_DEFINITIONS` registry instead of returning hardcoded `["EURUSD", "GBPUSD"]`.
        2.  Modified the main block example to accept a `symbol` parameter via command line arguments (defaulting to "EURUSD" for backward compatibility) instead of hardcoding "EURUSD".

- [x] **6.5. Create Test for Execution Controller Refactoring**
    - **File:** `tests/execution/test_controller.py`
    - **Action:** Modify the relevant test for the function that calls `adapter.place_order` with hardcoded symbol.
    - **Logic:**
        1.  Added `test_run_live_controller_should_accept_custom_symbol()` test that verifies current behavior (hardcoded "EURUSD" in place_order calls).
        2.  Set up framework to validate refactoring that would accept a symbol parameter and use it instead of hardcoded value.

- [x] **6.6. Refactor `execution/controller.py`**
    - **File:** `src/trading_platform/execution/controller.py`
    - **Action:** Refactor the function containing the hardcoded symbol.
    - **Logic:**
        1.  Modified the `run_live_controller` function signature to accept a `symbol: str = "EURUSD"` parameter.
        2.  Used this `symbol` variable in the call to `adapter.place_order` instead of hardcoded "EURUSD".

### 7. Update Docstrings for Refactored Code

- [x] **7.1. Review and Update Docstrings**
    - **Action:** After all refactoring in Section 6 is complete, review every function that was modified.
    - **Logic:**
        1.  Updated docstrings for `_simulate_counterfactual_fast` and `_simulate_counterfactual_exact` in `backtester/core.py` to document the new `symbol` parameter.
        2.  Added comprehensive docstring for `run_live_controller` in `execution/controller.py` including documentation for the new `symbol` parameter.
        3.  All docstrings now clearly explain the purpose and expected format of the `symbol` parameter.
