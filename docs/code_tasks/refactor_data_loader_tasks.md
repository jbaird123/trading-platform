# Refactor Data Loader Implementation Plan

This plan details the steps required to refactor the data loading mechanism. We will move from a configuration-based approach (`data_catalog.yaml`) to a convention-based approach, where data files are discovered automatically based on a standardized directory structure.

### 1. Branch Creation

1.  [ ] Create a new git branch for this feature. The branch name must be `feature/convention-based-data-loader`.

    ```bash
    git checkout -b feature/convention-based-data-loader
    ```

### 2. Test Environment Setup

1.  [ ] Create a new directory structure within `tests/fixtures/` to serve as mock data for the new convention-based loading logic.

    *   Create the directory: `tests/fixtures/data/eurusd_test/full/`
    *   Create the directory: `tests/fixtures/data/eurusd_test/incremental/`

2.  [ ] Create dummy data files within the new fixture directories. The content should be minimal valid CSV.

    *   Create file `tests/fixtures/data/eurusd_test/full/eurusd_minute_1_20230101_20230101.csv` with the following content:
        ```csv
        timestamp,open,high,low,close,volume
        2023-01-01 00:00:00+00:00,1.1,1.1,1.1,1.1,10
        ```
    *   Create file `tests/fixtures/data/eurusd_test/incremental/eurusd_minute_1_20230102_20230102.csv` with the following content:
        ```csv
        timestamp,open,high,low,close,volume
        2023-01-02 00:00:00+00:00,1.2,1.2,1.2,1.2,20
        ```

### 3. Implement New Data Loader (Test-First)

1.  [ ] Create a new test file: `tests/data/test_loader_convention.py`.

2.  [ ] In `tests/data/test_loader_convention.py`, add the following test case. It will fail initially. This test verifies that the new loader can find, load, and correctly combine a base file and an incremental file based on the directory convention.

    ```python
    import pandas as pd
    from pathlib import Path
    import pytest
    from trading_platform.data.loader import load_instrument_data

    def test_load_instrument_data_success():
        """
        Verify data is loaded from a conventional directory structure,
        combining 'full' and 'incremental' files.
        """
        test_data_root = Path("tests/fixtures/data")
        df, _ = load_instrument_data("EURUSD", test_data_root)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert df.index[0].isoformat() == "2023-01-01T00:00:00+00:00"
        assert df.index[1].isoformat() == "2023-01-02T00:00:00+00:00"
        assert df.iloc[1]["open"] == 1.2
    ```

3.  [ ] In `tests/data/test_loader_convention.py`, add a second test case to verify correct error handling when an instrument's data directory does not exist.

    ```python
    def test_load_instrument_data_not_found():
        """
        Verify a FileNotFoundError is raised for a symbol with no data.
        """
        test_data_root = Path("tests/fixtures/data")
        with pytest.raises(FileNotFoundError, match="No data files found for symbol"):
            load_instrument_data("NOSUCHSYMBOL", test_data_root)
    ```

4.  [ ] In `src/trading_platform/data/loader.py`, create the new `load_instrument_data` function. Implement the logic required to make the tests in the previous steps pass. Do not modify `load_from_catalog` yet.

    *   The function signature must be: `def load_instrument_data(symbol: str, data_root: Path) -> tuple[pd.DataFrame, list[str]]:`
    *   It should sanitize the `symbol` to lowercase for path construction.
    *   Use `glob` to find the base file in `{data_root}/full/{sanitized_symbol}/*.csv`. Raise `FileNotFoundError` if not found.
    *   Use `glob` to find incremental files in `{data_root}/incremental/{sanitized_symbol}/*.csv`.
    *   Use the existing `load_and_normalize_data` helper to load the files, collecting flags.
    *   Concatenate the dataframes, sort by index, and drop duplicates.
    *   Return the final dataframe and the list of collected flags.

5.  [ ] Run `poetry run pytest tests/data/test_loader_convention.py`. All new tests in this file must pass before proceeding.

### 4. Refactor CLI to Use New Loader

1.  [ ] In `src/trading_platform/cli.py`, modify the file to use the new `load_instrument_data` function instead of `load_from_catalog`.

    *   Update the import from `loader` to be: `from trading_platform.data.loader import load_instrument_data`.
    *   Find the line: `df, dq_flags, instrument_def = load_from_catalog(data_req)`.
    *   Replace it with logic that calls the new function and decouples the instrument definition lookup.
        ```python
        from pathlib import Path
        from trading_platform.data.instrument import get_instrument_definition
        from trading_platform.data.schema import resample_ohlc
        import pandas as pd

        instrument_def = get_instrument_definition(data_req["symbol"])
        df, dq_flags = load_instrument_data(data_req["symbol"], Path("data"))

        tf = data_req.get("timeframe")
        if tf:
            df = resample_ohlc(df, str(tf), instrument_def)

        start = data_req.get("start")
        end = data_req.get("end")
        if start:
            df = df.loc[pd.to_datetime(start, utc=True) :]
        if end:
            df = df.loc[: pd.to_datetime(end, utc=True)]
        ```

### 5. Cleanup and Final Verification

1.  [ ] Run all tests to ensure the refactoring did not break any existing functionality.

    ```bash
    poetry run pytest
    ```
    All tests must pass.

2.  [ ] In `src/trading_platform/data/loader.py`, delete the now-unused `load_from_catalog` function.

3.  [ ] Delete the configuration file `config/data_catalog.yaml` from the project.

4.  [ ] Run the test suite one final time to guarantee the project is still in a working state after deleting the old code and configuration.

    ```bash
    poetry run pytest
    ```
    All tests must pass.
