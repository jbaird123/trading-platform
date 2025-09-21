import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from src.trading_platform.ai.data_connectors import AIDataConnector, DataCatalog
from src.trading_platform.ai.feature_engineering.pipeline import FeatureEngineeringPipeline
from src.trading_platform.ai.data_labeling import DataLabeler

@pytest.fixture
def mock_raw_data():
    # Create a sample DataFrame that resembles raw OHLCV data
    data = {
        "timestamp": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05"]),
        "open": [100, 101, 102, 103, 104],
        "high": [102, 103, 104, 105, 106],
        "low": [99, 100, 101, 102, 103],
        "close": [101, 102, 103, 104, 105],
        "volume": [1000, 1100, 1200, 1300, 1400],
    }
    df = pd.DataFrame(data).set_index("timestamp")
    return df

@pytest.fixture
def mock_feature_config():
    # A simplified feature config for testing
    return [
        {"kind": "sma", "length": 2, "source": "close"},
        {"kind": "rsi", "length": 2, "source": "close"},
    ]

@pytest.fixture
def mock_labeling_config():
    # A simplified labeling config for testing
    return {"look_ahead_bars": 1, "price_change_threshold": 0.001}

@patch("src.trading_platform.ai.data_connectors.DataCatalog")
def test_data_preparation_integration_flow(
    mock_data_catalog_cls,
    mock_raw_data,
    mock_feature_config,
    mock_labeling_config,
):
    # Mock the DataCatalog to return our predefined raw data
    mock_data_catalog_instance = mock_data_catalog_cls.return_value
    mock_data_catalog_instance.get_data.return_value = mock_raw_data

    # 1. Load raw data using AIDataConnector
    connector = AIDataConnector(mock_data_catalog_instance)
    # Assuming load_training_data calls get_data internally
    raw_data_loaded = connector.load_training_data(symbol="TEST", timeframe="1D", start_date="2023-01-01", end_date="2023-01-05")
    pd.testing.assert_frame_equal(raw_data_loaded, mock_raw_data)

    # 2. Generate features using FeatureEngineeringPipeline
    feature_pipeline = FeatureEngineeringPipeline(raw_data_loaded)
    featured_data = feature_pipeline.run(mock_feature_config)

    # Basic assertions for featured_data
    assert "SMA_2_close" in featured_data.columns
    assert "RSI_2_close" in featured_data.columns
    assert len(featured_data) == len(raw_data_loaded) # Length might change due to NaNs from indicator calculation
    assert not featured_data.isnull().any().any() # Ensure no NaNs after feature engineering

    # 3. Generate labels using DataLabeler
    labeler = DataLabeler(**mock_labeling_config)
    labels = labeler.generate_future_price_direction(featured_data)

    # Basic assertions for labels
    assert isinstance(labels, pd.Series)
    assert labels.name == "signal"
    assert labels.isin([-1, 0, 1]).all() # Check if labels are -1, 0, or 1
    assert len(labels) <= len(featured_data) # Labels might be shorter due to look_ahead_bars
    assert not labels.isnull().any()

    # 4. Final alignment (as done in AITrainingPipeline)
    # This part is crucial for integration, simulating how the pipeline would align X and y
    X_aligned = featured_data.loc[labels.index]
    y_aligned = labels

    assert X_aligned.index.equals(y_aligned.index)
    assert X_aligned.shape[0] == y_aligned.shape[0]
    assert not X_aligned.isnull().any().any()
    assert not y_aligned.isnull().any()
