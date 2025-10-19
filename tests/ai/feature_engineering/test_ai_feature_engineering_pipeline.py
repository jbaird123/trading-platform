import importlib
import runpy
import sys
from io import StringIO
from unittest.mock import patch

import pandas as pd
import pytest
from trading_platform.ai.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
)


@pytest.fixture
def sample_dataframe():
    """
    Provides a sample DataFrame with enough data for indicator calculations.
    """
    data = [
        ["2023-01-01", 100, 102, 99, 101, 100],
        ["2023-01-02", 101, 103, 100, 102, 110],
        ["2023-01-03", 102, 104, 101, 103, 105],
        ["2023-01-04", 103, 105, 102, 104, 120],
        ["2023-01-05", 104, 106, 103, 105, 115],
        ["2023-01-06", 105, 107, 104, 106, 130],
        ["2023-01-07", 106, 108, 105, 107, 125],
        ["2023-01-08", 107, 109, 106, 108, 110],
        ["2023-01-09", 108, 110, 107, 109, 100],
        ["2023-01-10", 109, 111, 108, 110, 110],
        ["2023-01-11", 110, 112, 109, 111, 105],
        ["2023-01-12", 111, 113, 110, 112, 120],
        ["2023-01-13", 112, 114, 111, 113, 115],
        ["2023-01-14", 113, 115, 112, 114, 130],
        ["2023-01-15", 114, 116, 113, 115, 125],
    ]
    df = pd.DataFrame(
        data, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.set_index("timestamp")


def test_feature_engineering_pipeline_init_success(sample_dataframe):
    """
    Verifies successful initialization of the pipeline with a valid DataFrame.
    """
    pipeline = FeatureEngineeringPipeline(sample_dataframe)
    pd.testing.assert_frame_equal(pipeline.df, sample_dataframe)
    assert not pipeline.df.empty


def test_feature_engineering_pipeline_init_invalid_input():
    """
    Ensures TypeError is raised for invalid input to the pipeline constructor.
    """
    with pytest.raises(TypeError, match="Input 'df' must be a pandas DataFrame."):
        FeatureEngineeringPipeline([1, 2, 3])


def test_add_sma_feature(sample_dataframe):
    """
    Tests adding an SMA feature to the DataFrame.
    """
    pipeline = FeatureEngineeringPipeline(sample_dataframe)
    feature_config = {"kind": "sma", "params": {"length": 3}}
    pipeline.add_feature(feature_config)

    assert "sma_3" in pipeline.df.columns
    # Check that the first few values are NaN due to window, then valid numbers
    assert pd.isna(pipeline.df["sma_3"].iloc[0])
    assert pd.isna(pipeline.df["sma_3"].iloc[1])
    assert not pd.isna(pipeline.df["sma_3"].iloc[2])
    # Basic value check for SMA(3) on [101, 102, 103] should be ~102
    # Use approx due to floating-point precision
    assert pipeline.df["sma_3"].iloc[2] == pytest.approx(
        (101 + 102 + 103) / 3, abs=1e-6
    )


def test_add_rsi_feature(sample_dataframe):
    """
    Tests adding an RSI feature to the DataFrame.
    """
    pipeline = FeatureEngineeringPipeline(sample_dataframe)
    feature_config = {"kind": "rsi", "params": {"length": 3}}
    pipeline.add_feature(feature_config)

    assert "rsi_3" in pipeline.df.columns
    # RSI also has a warm-up period
    assert pd.isna(pipeline.df["rsi_3"].iloc[0])
    assert not pd.isna(pipeline.df["rsi_3"].iloc[3])


def test_add_feature_missing_kind(sample_dataframe):
    """
    Ensures ValueError is raised if feature config is missing 'kind'.
    """
    pipeline = FeatureEngineeringPipeline(sample_dataframe)
    feature_config = {"params": {"length": 10}}
    with pytest.raises(ValueError, match="Feature config must include a 'kind'."):
        pipeline.add_feature(feature_config)


def test_add_feature_unsupported_kind(sample_dataframe):
    """
    Verifies behavior for unsupported feature kinds.
    Now that we use centralized compute_features, unsupported types
    result in a column with NaN values rather than an exception.
    """
    pipeline = FeatureEngineeringPipeline(sample_dataframe)
    feature_config = {"kind": "unsupported_feature", "params": {"length": 10}}
    pipeline.add_feature(feature_config)
    # Should create column with NaN values
    assert "unsupported_feature_10" in pipeline.df.columns
    assert pipeline.df["unsupported_feature_10"].isna().all()


def test_run_multiple_features(sample_dataframe):
    """
    Tests running the pipeline with multiple feature configurations.
    """
    pipeline = FeatureEngineeringPipeline(sample_dataframe)
    feature_configs = [
        {"kind": "sma", "params": {"length": 3}},
        {"kind": "rsi", "params": {"length": 3}},
    ]
    featured_df = pipeline.run(feature_configs)

    assert "sma_3" in featured_df.columns
    assert "rsi_3" in featured_df.columns
    # Check that NaNs from indicator warm-up are dropped
    assert featured_df.index.min() > sample_dataframe.index.min()
    assert not featured_df.isnull().any().any()


def test_run_empty_feature_list(sample_dataframe):
    """
    Tests running the pipeline with an empty list of feature configurations.
    """
    pipeline = FeatureEngineeringPipeline(sample_dataframe)
    featured_df = pipeline.run([])

    # No new columns should be added, and original data should be returned
    # (after dropna if any)
    pd.testing.assert_frame_equal(featured_df, sample_dataframe.dropna())


def test_run_dropna_behavior(sample_dataframe):
    """
    Verifies that dropna is called and removes rows with NaN values.
    """
    # Create a DataFrame that will have NaNs after feature calculation
    short_df = sample_dataframe.head(5)  # Not enough data for RSI(14) or SMA(14)
    pipeline = FeatureEngineeringPipeline(short_df)
    feature_configs = [
        {"kind": "sma", "params": {"length": 3}},
    ]
    featured_df = pipeline.run(feature_configs)

    # The first two rows should be dropped for SMA(3)
    assert len(featured_df) == len(short_df) - 2
    assert not featured_df.isnull().any().any()


# --- Consolidated from tests/ai/test_feature_engineering_coverage_gaps.py ---


def test_feature_engineering_pipeline_main_block():
    """Ensure the pipeline demo main block executes and prints status."""

    module_name = "trading_platform.ai.feature_engineering.pipeline"
    package_name = "trading_platform.ai.feature_engineering"
    captured_output = StringIO()

    saved_module = sys.modules.pop(module_name, None)
    package = sys.modules.get(package_name)
    saved_attr = None
    if package is not None and hasattr(package, "pipeline"):
        saved_attr = package.pipeline
        delattr(package, "pipeline")

    with patch("sys.stdout", captured_output), patch("sys.argv", ["pipeline.py"]):
        try:
            runpy.run_module(module_name, run_name="__main__")
        except SystemExit:
            pass
        finally:
            if saved_module is not None:
                sys.modules[module_name] = saved_module
            else:
                sys.modules.pop(module_name, None)

            package = sys.modules.get(package_name)
            if package is not None:
                if saved_attr is not None:
                    setattr(package, "pipeline", saved_attr)
                elif hasattr(package, "pipeline"):
                    delattr(package, "pipeline")
            elif saved_attr is not None:
                training_pkg = importlib.import_module(package_name)
                setattr(training_pkg, "pipeline", saved_attr)

    output = captured_output.getvalue()
    assert "Running feature engineering for 2 features..." in output
    assert "Feature engineering complete." in output
    assert "DataFrame with new features:" in output


def test_feature_engineering_pipeline_example_data():
    """Demo configurations should generate expected indicator columns."""
    from trading_platform.ai.feature_engineering.pipeline import (
        FeatureEngineeringPipeline,
    )

    dates = pd.date_range("2023-01-01", periods=20, freq="D")
    data = {
        "timestamp": dates,
        "open": [1.0 + i * 0.01 for i in range(20)],
        "high": [1.1 + i * 0.01 for i in range(20)],
        "low": [0.95 + i * 0.01 for i in range(20)],
        "close": [1.05 + i * 0.01 for i in range(20)],
        "volume": [100 + i * 5 for i in range(20)],
    }
    sample_df = pd.DataFrame(data).set_index("timestamp")

    features_to_add_buggy = [
        {"kind": "sma", "length": 2},
        {"kind": "rsi", "length": 2},
    ]

    pipeline_buggy = FeatureEngineeringPipeline(sample_df)
    featured_df_buggy = pipeline_buggy.run(features_to_add_buggy)

    assert "close" in featured_df_buggy.columns
    assert "sma_14" in featured_df_buggy.columns
    assert "rsi_14" in featured_df_buggy.columns

    features_to_add_correct = [
        {"kind": "sma", "params": {"length": 2}},
        {"kind": "rsi", "params": {"length": 2}},
    ]

    pipeline_correct = FeatureEngineeringPipeline(sample_df)
    featured_df_correct = pipeline_correct.run(features_to_add_correct)

    assert not featured_df_correct.empty
    assert "close" in featured_df_correct.columns
    assert "sma_2" in featured_df_correct.columns
    assert "rsi_2" in featured_df_correct.columns
