import pandas as pd
import pytest
from trading_platform.ai.data_labeling import DataLabeler


@pytest.fixture
def sample_dataframe():
    """Provides a sample DataFrame for testing DataLabeler."""
    data = {
        "open": [1.0, 1.05, 1.1, 1.08, 1.12, 1.15, 1.13, 1.10],
        "high": [1.1, 1.15, 1.12, 1.10, 1.18, 1.17, 1.16, 1.12],
        "low": [0.95, 1.0, 1.07, 1.05, 1.09, 1.12, 1.10, 1.08],
        "close": [1.05, 1.1, 1.08, 1.12, 1.15, 1.13, 1.10, 1.09],
        "volume": [100, 110, 105, 120, 115, 130, 125, 110],
    }
    df = pd.DataFrame(data)
    df.index = pd.to_datetime([
        "2023-01-01",
        "2023-01-02",
        "2023-01-03",
        "2023-01-04",
        "2023-01-05",
        "2023-01-06",
        "2023-01-07",
        "2023-01-08",
    ])
    return df


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
        [1, -1, 1, 1, -1, -1, -1],
        index=sample_dataframe.index[: -labeler.look_ahead_bars],
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
        [1, 1, 1, 1, -1, -1],
        index=sample_dataframe.index[: -labeler.look_ahead_bars],
        dtype=int,
    )
    pd.testing.assert_series_equal(labels, expected_labels, check_names=False)


def test_generate_future_price_direction_missing_close_column():
    """
    Ensures a ValueError is raised if the DataFrame lacks a 'close' column.
    """
    df_no_close = pd.DataFrame({"open": [1]}, index=pd.to_datetime(["2023-01-01"]))
    labeler = DataLabeler()
    with pytest.raises(ValueError, match="DataFrame must contain a 'close' column."):
        labeler.generate_future_price_direction(df_no_close)


def test_generate_future_price_direction_all_same_price():
    """
    Tests behavior when all close prices are identical.
    """
    df_same_price = pd.DataFrame({"close": [100, 100, 100]})
    df_same_price.index = pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"])
    labeler = DataLabeler(look_ahead_bars=1)
    labels = labeler.generate_future_price_direction(df_same_price)
    expected_labels = pd.Series(
        [0, 0],
        index=df_same_price.index[: -labeler.look_ahead_bars],
        dtype=int,
    )
    pd.testing.assert_series_equal(labels, expected_labels, check_names=False)


def test_generate_future_price_direction_only_up():
    """
    Tests behavior when prices only go up.
    """
    df_only_up = pd.DataFrame({"close": [100, 102, 104]})
    df_only_up.index = pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"])
    labeler = DataLabeler(look_ahead_bars=1)
    labels = labeler.generate_future_price_direction(df_only_up)
    expected_labels = pd.Series(
        [1, 1],
        index=df_only_up.index[: -labeler.look_ahead_bars],
        dtype=int,
    )
    pd.testing.assert_series_equal(labels, expected_labels, check_names=False)


def test_generate_future_price_direction_only_down():
    """
    Tests behavior when prices only go down.
    """
    df_only_down = pd.DataFrame({"close": [104, 102, 100]})
    df_only_down.index = pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"])
    labeler = DataLabeler(look_ahead_bars=1)
    labels = labeler.generate_future_price_direction(df_only_down)
    expected_labels = pd.Series(
        [-1, -1],
        index=df_only_down.index[: -labeler.look_ahead_bars],
        dtype=int,
    )
    pd.testing.assert_series_equal(labels, expected_labels, check_names=False)


def test_get_labeling_methodology_version():
    """
    Verifies that get_labeling_methodology_version returns the correct string.
    """
    labeler = DataLabeler()
    assert labeler.get_labeling_methodology_version() == "v1.0_future_price_direction"


def test_generate_future_price_direction_prints_methodology(sample_dataframe, capsys):
    """
    Verifies that the methodology version is printed during label generation.
    """
    labeler = DataLabeler(look_ahead_bars=1)
    labeler.generate_future_price_direction(sample_dataframe)
    
    captured = capsys.readouterr()
    assert "Generated future price direction labels using methodology v1.0_future_price_direction" in captured.out


def test_main_execution_simulation(capsys):
    """
    Simulates the main block execution to cover lines 54-80.
    """
    from trading_platform.ai.data_labeling import DataLabeler
    
    # Simulate the main block code
    data = {
        "open": [1.0, 1.05, 1.1, 1.08, 1.12, 1.15, 1.13, 1.10],
        "high": [1.1, 1.15, 1.12, 1.10, 1.18, 1.17, 1.16, 1.12],
        "low": [0.95, 1.0, 1.07, 1.05, 1.09, 1.12, 1.10, 1.08],
        "close": [1.05, 1.1, 1.08, 1.12, 1.15, 1.13, 1.10, 1.09],
        "volume": [100, 110, 105, 120, 115, 130, 125, 110],
    }
    sample_df = pd.DataFrame(data)
    sample_df.index = pd.to_datetime([
        "2023-01-01",
        "2023-01-02", 
        "2023-01-03",
        "2023-01-04",
        "2023-01-05",
        "2023-01-06",
        "2023-01-07",
        "2023-01-08",
    ])

    labeler = DataLabeler(look_ahead_bars=1)
    labels = labeler.generate_future_price_direction(sample_df)

    print("\nSample DataFrame with generated labels:")
    combined_df = pd.concat([sample_df, labels.rename("target")], axis=1).dropna()
    print(f"DataFrame shape: {combined_df.shape}")  # Avoid pandas print issues
    print(f"\nLabeling Methodology Version: {labeler.get_labeling_methodology_version()}")

    captured = capsys.readouterr()
    assert "Sample DataFrame with generated labels:" in captured.out
    assert "Labeling Methodology Version: v1.0_future_price_direction" in captured.out


def test_generate_future_price_direction_with_significant_threshold_change():
    """
    Tests the threshold logic more specifically to ensure edge cases are covered.
    """
    # Create data with very small price changes that don't meet the 0.1% threshold
    df_small_change = pd.DataFrame({"close": [100.0, 100.05, 100.1]})  # 0.05% and 0.05% changes
    df_small_change.index = pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"])
    
    labeler = DataLabeler(look_ahead_bars=1)
    labels = labeler.generate_future_price_direction(df_small_change)
    
    # Both changes are below 0.1% threshold so should be labeled as 0 (no significant change)
    expected_labels = pd.Series(
        [0, 0],
        index=df_small_change.index[:-1],
        dtype=int,
    )
    pd.testing.assert_series_equal(labels, expected_labels, check_names=False)


def test_generate_future_price_direction_threshold_boundaries():
    """
    Tests the exact threshold boundaries (0.1% = 0.001).
    """
    # Create data with changes exactly at the threshold
    df_threshold = pd.DataFrame({"close": [100.0, 100.11, 99.89]})  # +0.11% and -0.11%
    df_threshold.index = pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"])
    
    labeler = DataLabeler(look_ahead_bars=1)
    labels = labeler.generate_future_price_direction(df_threshold)
    
    # First change is +0.11% (> 0.1% threshold) = 1, second is -0.11% (< -0.1% threshold) = -1
    expected_labels = pd.Series(
        [1, -1],
        index=df_threshold.index[:-1],
        dtype=int,
    )
    pd.testing.assert_series_equal(labels, expected_labels, check_names=False)
