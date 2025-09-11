from __future__ import annotations

import typing
from pathlib import Path

import pandas as pd
import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from trading_platform.data.schema import load_and_normalize_data


@pytest.fixture
def shared_context() -> dict:
    """A dictionary to share state between test steps."""
    return {}


# This single line will generate test functions for all scenarios in the feature file.
# It's a cleaner way to link tests than using the @scenario decorator for each one.
scenarios("../../features/data_handler/data_schema.feature")


def _create_csv_file(
    tmp_path: Path,
    shared_context: dict,
    filename: str,
    data: dict[str, list[typing.Any]],
):
    """Helper function to create a CSV file in a temporary directory."""
    df = pd.DataFrame(data)
    data_path = tmp_path / filename
    df.to_csv(data_path, index=False)
    shared_context["data_path"] = data_path


@given(parsers.parse('a raw data file "{filename}" with columns "{columns}"'))
def given_raw_data_file_with_columns(
    tmp_path: Path, shared_context: dict, filename: str, columns: str
):
    """Create a dummy CSV file with specified columns and some data."""
    column_list = [col.strip().replace('"', "") for col in columns.split(",")]
    data: dict[str, list[typing.Any]] = {
        "UTCTime": [
            "2023-01-01T00:00:00Z",
            "2023-01-01T00:01:00Z",
            "2023-01-01T00:02:00Z",
        ],
        "Open": [100, 101, 102],
        "High": [105, 106, 107],
        "Low": [99, 100, 101],
        "Close": [101, 102, 103],
        "Volume": [1000, 1100, 1200],
    }
    df_data: dict[str, list[typing.Any]] = {
        col: data[col] for col in column_list if col in data
    }
    _create_csv_file(tmp_path, shared_context, filename, df_data)


@given(parsers.parse('a raw data file "{filename}"'))
def given_raw_data_file_missing_timestamp(
    tmp_path: Path, shared_context: dict, filename: str
):
    """Create a dummy CSV file with a missing timestamp."""
    data: dict[str, list[typing.Any]] = {
        # "UTCTime" is intentionally missing for this scenario
        "Open": [100, 101, 102],
        "High": [105, 106, 107],
        "Low": [99, 100, 101],
        "Close": [101, 102, 103],
        "Volume": [1000, 1100, 1200],
    }
    _create_csv_file(tmp_path, shared_context, filename, data)


@when("the data is loaded and normalized")
def when_data_is_loaded(shared_context: dict):
    """Load the data from the dummy file and normalize it."""
    data_path = shared_context["data_path"]
    df, flags = load_and_normalize_data(data_path)
    shared_context["df"] = df
    shared_context["quality_flags"] = flags


@then(parsers.parse('the resulting DataFrame should have columns "{columns}"'))
def then_dataframe_has_columns(shared_context: dict, columns: str):
    """Verify the columns of the resulting DataFrame."""
    df = shared_context["df"]
    expected_columns = [col.strip().replace('"', "") for col in columns.split(",")]
    # The 'timestamp' is the index, so we check it separately.
    # Here, we verify the remaining data columns.
    expected_data_columns = [col for col in expected_columns if col != "timestamp"]
    assert list(df.columns) == expected_data_columns


@then('the "timestamp" column should be a UTC datetime index')
def then_timestamp_is_utc_index(shared_context: dict):
    """Verify the index is a UTC datetime index."""
    df = shared_context["df"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.name == "timestamp"
    assert df.index.tz is not None and str(df.index.tz) == "UTC"


@then(parsers.parse("the DataFrame should contain {row_count:d} rows"))
def then_dataframe_has_rows(shared_context: dict, row_count: int):
    """Verify the number of rows in the DataFrame."""
    df = shared_context["df"]
    assert len(df) == row_count


@then(parsers.parse('a "{flag_name}" quality flag should be raised'))
def then_quality_flag_is_raised(shared_context: dict, flag_name: str):
    """Verify that a specific data quality flag was raised."""
    quality_flags = shared_context["quality_flags"]
    assert flag_name in quality_flags


@then("the DataFrame should be empty")
def then_dataframe_is_empty(shared_context: dict):
    """Verify the resulting DataFrame is empty."""
    df = shared_context["df"]
    assert df.empty


@then("no data quality flags should be raised")
def then_no_quality_flags_raised(shared_context: dict):
    """Verify that no data quality flags were raised."""
    quality_flags = shared_context["quality_flags"]
    assert not quality_flags
