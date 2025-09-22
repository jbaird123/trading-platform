import pandas as pd
import pytest

from src.trading_platform.ai.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
)


@pytest.fixture
def sample_dataframe():
    """
    Provides a sample DataFrame with enough data for indicator calculations.
    """
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
                "2023-01-09",
                "2023-01-10",
                "2023-01-11",
                "2023-01-12",
                "2023-01-13",
                "2023-01-14",
                "2023-01-15",
            ]
        ),
        "open": [
            100,
            101,
            102,
            103,
            104,
            105,
            106,
            107,
            108,
            109,
            110,
            111,
            112,
            113,
            114,
        ],
        "high": [
            102,
            103,
            104,
            105,
            106,
            107,
            108,
            109,
            110,
            111,
            112,
            113,
            114,
            115,
            116,
        ],
        "low": [
            99,
            100,
            101,
            102,
            103,
            104,
            105,
            106,
            107,
            108,
            109,
            110,
            111,
            112,
            113,
        ],
        "close": [
            101,
            102,
            103,
            104,
            105,
            106,
            107,
            108,
            109,
            110,
            111,
            112,
            113,
            114,
            115,
        ],
        "volume": [
            100,
            110,
            105,
            120,
            115,
            130,
            125,
            110,
            100,
            110,
            105,
            120,
            115,
            130,
            125,
        ],
    }
    return pd.DataFrame(data).set_index("timestamp")


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
    # Basic value check for SMA(3) on [101, 102, 103] should be 102
    assert pipeline.df["sma_3"].iloc[2] == (101 + 102 + 103) / 3


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
    Verifies NotImplementedError for unsupported feature kinds.
    """
    pipeline = FeatureEngineeringPipeline(sample_dataframe)
    feature_config = {"kind": "unsupported_feature", "params": {"length": 10}}
    with pytest.raises(
        NotImplementedError, match="Feature 'unsupported_feature' is not supported yet."
    ):
        pipeline.add_feature(feature_config)


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

    # No new columns should be added, and original data should be returned (after dropna if any)
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
