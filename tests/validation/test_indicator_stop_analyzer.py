"""Unit tests for IndicatorStopAnalyzer zoom detection."""

import pandas as pd

from tests.validation.analyzers.indicator_stop import IndicatorStopAnalyzer


def _minute_bars(start: pd.Timestamp, low_hits_stop: bool) -> pd.DataFrame:
    lows = [1.0980 if low_hits_stop else 1.0992, 1.0995, 1.0998]
    highs = [1.1005, 1.1002, 1.1001]
    opens = [1.1000, 1.0998, 1.0999]
    closes = [1.0994, 1.0997, 1.1000]
    index = pd.date_range(start, periods=3, freq="T")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes},
        index=index,
    )


def test_indicator_stop_zoom_detects_intrabar_stop() -> None:
    entry_time = pd.Timestamp("2023-01-01 10:00:00", tz="UTC")
    exit_time = pd.Timestamp("2023-01-01 11:00:00", tz="UTC")

    analyzer = IndicatorStopAnalyzer(
        indicator_type="atr",
        indicator_params={"length": 14},
        multiplier=2.0,
        tolerance=1e-5,
    )

    platform_trade = pd.Series(
        {
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry_price": 1.1000,
            "exit_price": 1.0980,
            "side": "long",
            "exit_reason": "stop-loss",
        }
    )

    tv_trade = pd.Series(
        {
            "entry_time": entry_time,
            "exit_time": exit_time + pd.Timedelta(hours=1),
            "entry_price": 1.1000,
            "exit_price": 1.1010,
            "side": "long",
            "exit_reason": "stop-loss",
        }
    )

    ohlcv_data = pd.DataFrame(
        {
            "close": [1.1000, 1.0995],
            "ATR_14": [0.0010, 0.0010],
        },
        index=[entry_time, exit_time],
    )

    ohlcv_1min = _minute_bars(exit_time, low_hits_stop=True)

    result = analyzer.analyze_discrepancy(
        platform_trade,
        tv_trade,
        ohlcv_data,
        ohlcv_1min=ohlcv_1min,
    )

    assert result.category == "PLATFORM_ZOOM_INTRABAR_STOP"
    assert result.is_acceptable
    assert "1-minute zoom" in result.explanation.lower()
