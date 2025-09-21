import pandas as pd
import pytest

from src.trading_platform.ai.data_connectors import AIDataConnector, DataCatalog


class MockDataCatalog(DataCatalog):
    """A mock DataCatalog for testing purposes."""

    def __init__(self, data_to_return: pd.DataFrame = None, empty_data: bool = False):
        self._data_to_return = data_to_return
        self._empty_data = empty_data

    def get_historical_data(
        self, symbol: str, timeframe: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        if self._empty_data:
            return pd.DataFrame()
        if self._data_to_return is not None:
            return self._data_to_return
        # Default valid data
        data = {
            "timestamp": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "open": [1.0, 1.1, 1.2],
            "high": [1.1, 1.2, 1.3],
            "low": [0.9, 1.0, 1.1],
            "close": [1.05, 1.15, 1.25],
            "volume": [100, 110, 120],
        }
        return pd.DataFrame(data).set_index("timestamp")


@pytest.fixture
def mock_data_catalog():
    return MockDataCatalog()


@pytest.fixture
def ai_data_connector(mock_data_catalog):
    return AIDataConnector(mock_data_catalog)


def test_aidataconnector_init(mock_data_catalog):
    """
    Validates that AIDataConnector initializes correctly, assigning the
    data catalog and initializing data lineage.
    """
    connector = AIDataConnector(mock_data_catalog)
    assert connector.data_catalog == mock_data_catalog
    assert connector.data_lineage == {}


def test_load_training_data_success(ai_data_connector):
    """
    Verifies successful data loading and lineage recording when valid data
    is returned by the data catalog.
    """
    symbol = "EURUSD"
    timeframe = "1D"
    start_date = "2023-01-01"
    end_date = "2023-01-03"

    df = ai_data_connector.load_training_data(symbol, timeframe, start_date, end_date)

    assert not df.empty
    assert isinstance(df, pd.DataFrame)
    assert symbol in ai_data_connector.get_data_lineage()


def test_load_training_data_empty_dataframe_raises_error():
    """
    Ensures a ValueError is raised when the data catalog returns an empty
    DataFrame.
    """
    mock_catalog = MockDataCatalog(empty_data=True)
    connector = AIDataConnector(mock_catalog)

    with pytest.raises(ValueError, match="No data found"):
        connector.load_training_data("EURUSD", "1D", "2023-01-01", "2023-01-03")


def test_load_training_data_non_datetime_index_raises_error():
    """
    Confirms a TypeError is raised if the loaded DataFrame's index is not
    a datetime type.
    """
    invalid_data = pd.DataFrame({"col": [1, 2, 3]}, index=[1, 2, 3])
    mock_catalog = MockDataCatalog(data_to_return=invalid_data)
    connector = AIDataConnector(mock_catalog)

    with pytest.raises(TypeError, match="index must be datetime type"):
        connector.load_training_data("EURUSD", "1D", "2023-01-01", "2023-01-03")


def test_load_training_data_non_monotonic_index_raises_error():
    """
    Verifies a ValueError is raised if the loaded DataFrame's index is not
    monotonically increasing.
    """
    non_monotonic_data = pd.DataFrame(
        {"col": [1, 2, 3]},
        index=pd.to_datetime(["2023-01-02", "2023-01-01", "2023-01-03"]),
    )
    mock_catalog = MockDataCatalog(data_to_return=non_monotonic_data)
    connector = AIDataConnector(mock_catalog)

    with pytest.raises(ValueError, match="index is not monotonically increasing"):
        connector.load_training_data("EURUSD", "1D", "2023-01-01", "2023-01-03")


def test_load_training_data_missing_values_prints_warning(ai_data_connector, capsys):
    """
    Checks that a warning is printed to stderr when missing values are
    detected in the loaded data.
    """
    data_with_nan = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "open": [1.0, 1.1, None],
            "close": [1.05, 1.15, 1.25],
        }
    ).set_index("timestamp")
    mock_catalog = MockDataCatalog(data_to_return=data_with_nan)
    connector = AIDataConnector(mock_catalog)

    connector.load_training_data("EURUSD", "1D", "2023-01-01", "2023-01-03")
    captured = capsys.readouterr()
    assert "Warning: Missing values detected" in captured.out


def test_get_data_lineage(ai_data_connector):
    """
    Ensures that get_data_lineage returns the current data lineage dictionary.
    """
    assert ai_data_connector.get_data_lineage() == {}

    symbol = "EURUSD"
    timeframe = "1D"
    start_date = "2023-01-01"
    end_date = "2023-01-03"
    ai_data_connector.load_training_data(symbol, timeframe, start_date, end_date)

    lineage = ai_data_connector.get_data_lineage()
    assert symbol in lineage
    assert "source" in lineage[symbol]
    assert "row_count" in lineage[symbol]
