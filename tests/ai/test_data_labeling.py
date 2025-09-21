import pandas as pd
import pytest

from src.trading_platform.ai.data_labeling import DataLabeler


@pytest.fixture
def sample_dataframe():
    """Provides a sample DataFrame for testing DataLabeler."""
    data = {
        "timestamp": pd.to_datetime(
            [
                "2023-01-01",
                "2023-01-02",
                "2023-01-03",
                "2023-01-04",
                "2023-01-05",
                "2023-01-06",
                "2023-01-07",
                "2023-01-08",
            ]
        ),
        "open": [1.0, 1.05, 1.1, 1.08, 1.12, 1.15, 1.13, 1.10],
        "high": [1.1, 1.15, 1.12, 1.10, 1.18, 1.17, 1.16, 1.12],
        "low": [0.95, 1.0, 1.07, 1.05, 1.09, 1.12, 1.10, 1.08],
        "close": [1.05, 1.1, 1.08, 1.12, 1.15, 1.13, 1.10, 1.09],
        "volume": [100, 110, 105, 120, 115, 130, 125, 110],
    }
    return pd.DataFrame(data).set_index("timestamp")


def test_datalabeler_init():
    """
    Verifies that DataLabeler initializes correctly with default and custom
    look_ahead_bars.
    """
    labeler_default = DataLabeler()
    assert labeler_default.look_ahead_bars == 1
    assert labeler_default.labeling_methodology_version == "v1.0_future_price_direction"

    labeler_custom = DataLabeler(look_ahead_bars=5)
    assert labeler_custom.look_ahead_bars == 5


def test_generate_future_price_direction_basic(sample_dataframe):
    """
    Tests basic functionality of generating future price direction labels.
    """
    labeler = DataLabeler(look_ahead_bars=1)
    labels = labeler.generate_future_price_direction(sample_dataframe)

    expected_labels = pd.Series(
        [0, -1, 1, 1, -1, -1, -1],
        index=pd.to_datetime(
            [
                "2023-01-01",
                "2023-01-02",
                "2023-01-03",
                "2023-01-04",
                "2023-01-05",
                "2023-01-06",
                "2023-01-07",
            ]
        ),
        dtype=int,
    )
    pd.testing.assert_series_equal(labels, expected_labels, check_names=False)


def test_generate_future_price_direction_custom_look_ahead(sample_dataframe):
    """
    Tests generating labels with a custom look_ahead_bars value.
    """
    labeler = DataLabeler(look_ahead_bars=2)
    labels = labeler.generate_future_price_direction(sample_dataframe)

    expected_labels = pd.Series(
        [-1, 1, 1, -1, -1, -1],
        index=pd.to_datetime(
            [
                "2023-01-01",
                "2023-01-02",
                "2023-01-03",
                "2023-01-04",
                "2023-01-05",
                "2023-01-06",
            ]
        ),
        dtype=int,
    )
    pd.testing.assert_series_equal(labels, expected_labels, check_names=False)


def test_generate_future_price_direction_missing_close_column():
    """
    Ensures a ValueError is raised if the DataFrame lacks a 'close' column.
    """
    df_no_close = pd.DataFrame({"open": [1, 2, 3]}, index=pd.to_datetime(["2023-01-01"]))
    labeler = DataLabeler()
    with pytest.raises(ValueError, match="DataFrame must contain a 'close' column."):
        labeler.generate_future_price_direction(df_no_close)


def test_generate_future_price_direction_all_same_price():
    """
    Tests behavior when all close prices are identical.
    """
    df_same_price = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "close": [100, 100, 100],
        }
    ).set_index("timestamp")
    labeler = DataLabeler(look_ahead_bars=1)
    labels = labeler.generate_future_price_direction(df_same_price)
    expected_labels = pd.Series(
        [0, 0],
        index=pd.to_datetime(["2023-01-01", "2023-01-02"]),
        dtype=int,
    )
    pd.testing.assert_series_equal(labels, expected_labels, check_names=False)


def test_generate_future_price_direction_only_up():
    """
    Tests behavior when prices only go up.
    """
    df_only_up = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "close": [100, 102, 104],
        }
    ).set_index("timestamp")
    labeler = DataLabeler(look_ahead_bars=1)
    labels = labeler.generate_future_price_direction(df_only_up)
    expected_labels = pd.Series(
        [1, 1],
        index=pd.to_datetime(["2023-01-01", "2023-01-02"]),
        dtype=int,
    )
    pd.testing.assert_series_equal(labels, expected_labels, check_names=False)


def test_generate_future_price_direction_only_down():
    """
    Tests behavior when prices only go down.
    """
    df_only_down = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "close": [104, 102, 100],
        }
    ).set_index("timestamp")
    labeler = DataLabeler(look_ahead_bars=1)
    labels = labeler.generate_future_price_direction(df_only_down)
    expected_labels = pd.Series(
        [-1, -1],
        index=pd.to_datetime(["2023-01-01", "2023-01-02"]),
        dtype=int,
    )
    pd.testing.assert_series_equal(labels, expected_labels, check_names=False)


def test_get_labeling_methodology_version():
    """
    Verifies that get_labeling_methodology_version returns the correct string.
    """
    labeler = DataLabeler()
    assert labeler.get_labeling_methodology_version() == "v1.0_future_price_direction"
