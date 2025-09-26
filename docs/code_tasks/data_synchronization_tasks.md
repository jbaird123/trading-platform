# Data Synchronization Service Implementation Plan

This document outlines the precise, ordered steps required to implement the automated data synchronization service. The developer must follow these tasks in sequence to ensure correctness and maintain 100% test coverage.

### 1. Refactor Instrument Definition Logic

*   **1.1. Create Test for Asset Class Defaults**
    *   **File:** `tests/data/test_instrument.py`
    *   **Action:** Create a new test function `test_get_instrument_definition_uses_asset_class_defaults`.
    *   **Logic:**
        1.  Import `get_instrument_definition`.
        2.  Call `get_instrument_definition` for "EUR/USD".
        3.  Assert that the returned object's `asset_class` is "Forex".
        4.  Assert that the `sessions` property is not empty.
        5.  Assert that the `tick_size` is `0.00001` (the instrument-specific override).
        6.  Call `get_instrument_definition` for "EUR/JPY" and assert its `tick_size` is `0.001`.

*   **1.2. Implement Asset Class Default Logic**
    *   **File:** `src/trading_platform/data/instrument.py`
    *   **Action:** Refactor the file to use a dictionary for asset class defaults.
    *   **Logic:**
        1.  Create a new dictionary `_ASSET_CLASS_DEFAULTS` that maps `"Forex"` to its default properties (e.g., `asset_class`, `point_value`, `sessions`).
        2.  Modify `_INSTRUMENT_DEFINITIONS` to only contain properties that are *unique* to each instrument (like `tick_size`).
        3.  Update the `get_instrument_definition` function to merge the asset class defaults with the instrument-specific overrides before creating the `InstrumentDefinition` object.

### 2. Implement Data Synchronization Service

*   **2.1. Create Test for Last Sync Date Discovery**
    *   **File:** `tests/data/test_sync_service.py` (create this new file).
    *   **Action:** Create a test function `test_get_last_sync_date_from_filenames`.
    *   **Logic:**
        1.  Import a new (to be created) function `get_last_sync_date` from `src/trading_platform/data/sync_service.py`.
        2.  Create a list of dummy filenames: `['eurusd_interval_min_1_20240101_20240531.csv', 'eurusd_interval_min_1_20240601_20240823.csv']`.
        3.  Call `get_last_sync_date` with this list and assert that it returns a `datetime.date` object for `2024-08-23`.

*   **2.2. Implement Last Sync Date Discovery**
    *   **File:** `src/trading_platform/data/sync_service.py` (create this new file).
    *   **Action:** Create the `get_last_sync_date` function.
    *   **Logic:**
        1.  The function signature shall be `get_last_sync_date(files: list[Path]) -> date | None`.
        2.  It will iterate through the list of `Path` objects, using a regular expression on `path.name` to extract the `toDate` part (the second date).
        3.  It will keep track of the most recent date found and return it as a `datetime.date` object.

### 3. Implement Main Orchestration Script

*   **3.1. Create Test for Main Sync Script**
    *   **File:** `tests/data/test_sync.py` (create this new file).
    *   **Action:** Create a test function `test_main_sync_logic`.
    *   **Logic:**
        1.  This is an integration test. Use a temporary directory for the data root.
        2.  Create a dummy file: `tmp_path/full/eurusd_interval_min_1_20250901_20250920.csv`.
        3.  Use `pytest.MonkeyPatch` to mock `sync_service.download_and_save_data`.
        4.  Call the main (to be created) `main(args)` function from `src/trading_platform/data/sync.py` with `['--symbol', 'EUR/USD', '--data-root', str(tmp_path)]`.
        5.  Assert `download_and_save_data` was called with `start_date=date(2025, 9, 21)` and `end_date` being yesterday.
        6.  Repeat the test, calling `main` with `['--all', ...]`. Assert that `download_and_save_data` is called for all defined instruments.

*   **3.2. Implement Main Orchestration Script**
    *   **File:** `src/trading_platform/data/sync.py` (create this new file).
    *   **Action:** Create the main script logic.
    *   **Logic:**
        1.  Import `argparse`, `datetime`, `glob`, `pathlib`, and helper functions.
        2.  Create a `main()` function that uses `argparse` to handle `--symbol`, `--all`, and `--data-root` arguments.
        3.  If `--all` is used, get the list of symbols from `_INSTRUMENT_DEFINITIONS.keys()`.
        4.  For each symbol, find all existing data files, call `get_last_sync_date`, calculate the new date range (last date + 1 day to yesterday), and call `download_and_save_data` if there are new days to fetch.
        5.  Add the `if __name__ == "__main__"` block.

### 4. Refactor Data Loader for Incremental Files

*   **4.1. Create Test for Unified Data Loading**
    *   **File:** `tests/data/test_loader.py`
    *   **Action:** Create a test function `test_load_from_catalog_loads_incremental_data`.
    *   **Logic:**
        1.  Use a temporary directory. Create a dummy base file and several dummy incremental files.
        2.  Call `load_from_catalog` for the relevant symbol.
        3.  Assert that the returned DataFrame contains the correct total number of rows and that the index is sorted and unique.

*   **4.2. Implement Unified Data Loading**
    *   **File:** `src/trading_platform/data/loader.py`
    *   **Action:** Refactor the `load_from_catalog` function.
    *   **Logic:**
        1.  After loading the base file, construct the path to the incremental directory (e.g., `data/incremental/eurusd/`).
        2.  Use `glob` to find all CSV files in the incremental directory.
        3.  Load all base and incremental files into a list of DataFrames.
        4.  Use `pd.concat` to combine them.
        5.  Sort the index and drop duplicates to ensure a clean time-series before returning.