# Session-Aware Resampling Implementation Plan

This document outlines the precise, ordered steps required to implement session-aware daily resampling. The developer must follow these tasks in sequence to ensure correctness and maintain 100% test coverage.

### 1. Refactor: Strengthen the Instrument and Session Data Models

*   **1.1. Create Test for New Data Models**
    *   **File:** `tests/data/test_instrument.py`
    *   **Action:** Create a new test function `test_instrument_and_session_models`.
    *   **Logic:**
        1.  Import the `InstrumentDefinition` and a new (to be created) `SessionDefinition` model from `src/trading_platform/data/instrument.py`.
        2.  Assert that an `InstrumentDefinition` cannot be created without the `sessions` field, confirming it is a required field.
        3.  Assert that a `SessionDefinition` object can be successfully created with `close_time="17:00"` and `close_timezone="America/New_York"`.
        4.  Assert that an `InstrumentDefinition` can be successfully created when its `sessions` field is a list containing a valid `SessionDefinition` object.

*   **1.2. Implement `SessionDefinition` and Update `InstrumentDefinition`**
    *   **File:** `src/trading_platform/data/instrument.py`
    *   **Action:**
        1.  Import `time` from the `datetime` module.
        2.  Create a new Pydantic model:
            ```python
            class SessionDefinition(BaseModel):
                close_time: time
                close_timezone: str
            ```
        3.  Modify the `InstrumentDefinition` model. Change the `sessions` field from `list[tuple[str, str]]` to `list[SessionDefinition]`. Ensure it is a required field (it should not have a default value).

### 2. Update: Standardize Forex Session Information

*   **2.1. Create Test for Standard Forex Session**
    *   **File:** `tests/data/test_instrument.py`
    *   **Action:** Create a new test function `test_forex_instruments_use_standard_session`.
    *   **Logic:**
        1.  Import `get_instrument_definition` and `time` from `datetime`.
        2.  Define the expected session as `(time(17, 0), "America/New_York")`.
        3.  Call `get_instrument_definition("EUR_USD")` and assert that its `sessions[0].close_time` and `sessions[0].close_timezone` match the expected session.
        4.  Call `get_instrument_definition("GBP_JPY")` and assert the same.

*   **2.2. Implement Standard Forex Session Data**
    *   **File:** `src/trading_platform/data/instrument.py`
    *   **Action:**
        1.  At the top of the file, define a constant for the standard Forex session:
            ```python
            from datetime import time
            _FOREX_SESSION = [SessionDefinition(close_time=time(17, 0), close_timezone="America/New_York")]
            ```
        2.  In the `_INSTRUMENT_DEFINITIONS` dictionary, modify both the `EUR_USD` and `GBP_JPY` entries. Change the `sessions` value for both to use the new constant: `"sessions": _FOREX_SESSION`.

### 3. Refactor: Enhance Data Loader to Return Instrument Definition

*   **3.1. Create Test for Modified Loader Return Signature**
    *   **File:** `tests/data/test_loader.py` (create this new file).
    *   **Action:** Create a test function `test_load_from_catalog_returns_instrument_definition`.
    *   **Logic:**
        1.  Use `pytest.MonkeyPatch` to mock `get_instrument_definition` from `trading_platform.data.loader`.
        2.  Call `load_from_catalog` with a valid data request for "EUR_USD".
        3.  Assert that the function returns a tuple with exactly three elements.
        4.  Assert that the third element is an instance of `InstrumentDefinition`.

*   **3.2. Implement Modified Loader Logic**
    *   **File:** `src/trading_platform/data/loader.py`
    *   **Action:**
        1.  Import `get_instrument_definition` and `InstrumentDefinition` from `..data.instrument`.
        2.  Modify the function signature and return type hint for `load_from_catalog` to be:
            ```python
            def load_from_catalog(...) -> tuple[pd.DataFrame, list[str], InstrumentDefinition]:
            ```
        3.  Inside the function, after validating the `symbol`, call `instrument = get_instrument_definition(symbol)`.
        4.  Modify the final `return` statement to be `return df, flags, instrument`.

### 4. Implement: Session-Aware Daily Resampling

*   **4.1. Create Test for Daily Resampling with Session Offset**
    *   **File:** `tests/data/test_schema.py`
    *   **Action:** Create a new test function `test_resample_ohlc_with_daily_session_offset`.
    *   **Logic:**
        1.  Create a mock `InstrumentDefinition` for a test instrument with a session close time of `17:00`.
        2.  Create a sample DataFrame of 1-minute data that spans from `16:55` to `17:05` on a given day.
        3.  Call `resample_ohlc` with this DataFrame, the rule `'1D'`, and the mock instrument definition.
        4.  Assert that the resulting DataFrame has only one row.
        5.  Assert that the timestamp of this row is the date of the data, with the time component being `00:00:00`.
        6.  Assert that the `close` price of the resampled bar is equal to the `close` price of the 1-minute bar at `16:59`.

*   **4.2. Implement Session-Aware Resampling Logic**
    *   **File:** `src/trading_platform/data/schema.py`
    *   **Action:**
        1.  Import `InstrumentDefinition` from `..data.instrument`.
        2.  Change the function signature of `resample_ohlc` to:
            ```python
            def resample_ohlc(
                df: pd.DataFrame, rule: str, instrument: InstrumentDefinition | None = None
            ) -> pd.DataFrame:
            ```
        3.  Inside the function, before the `df.resample` call, add the following logic:
            ```python
            resample_kwargs = {"label": "left"}
            if rule.upper() in ("D", "1D") and instrument and instrument.sessions:
                # Use the hour from the first session definition as the base for daily bars
                session_hour = instrument.sessions[0].close_time.hour
                resample_kwargs["base"] = session_hour
            
            out = df.resample(rule, **resample_kwargs).agg(...)
            ```
        4.  Ensure the `df.resample` call uses `**resample_kwargs`.