from __future__ import annotations

import pandas as pd
from trading_platform.backtester.orchestrator import ensure_market_data_with_warmup


class DummyHandler:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def get_data(
        self,
        timeframe: str | None = None,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        data = self.df
        if start is not None:
            start_ts = pd.to_datetime(start, utc=True)
            start_idx = int(data.index.get_indexer([start_ts], method="bfill")[0])
            if start_idx != -1:
                start_slice = slice(start_idx, None)
                data = data.iloc[start_slice]
        if end is not None:
            end_ts = pd.to_datetime(end, utc=True)
            end_idx = int(data.index.get_indexer([end_ts], method="ffill")[0])
            if end_idx != -1:
                end_bound = end_idx + 1
                end_slice = slice(None, end_bound)
                data = data.iloc[end_slice]
        return data


def test_ensure_market_data_with_warmup_extends_history():
    idx = pd.date_range("2020-12-01", periods=2000, freq="h", tz="UTC")
    df_full = pd.DataFrame({"open": list(range(len(idx)))}, index=idx)
    df_trimmed = df_full.loc[pd.Timestamp("2021-01-30", tz="UTC") :].copy()

    strategy_features = [{"name": "ema_fast", "type": "EMA", "params": {"length": 20}}]
    global_features: list[dict[str, object]] = []
    handler = DummyHandler(df_full)
    result = ensure_market_data_with_warmup(
        market_data=df_trimmed,
        execution_timeframe="1H",
        strategy_features=strategy_features,
        global_features=global_features,
        data_request={"start": "2021-01-30 00:00:00", "end": "2021-01-31 00:00:00"},
        data_handler=handler,
    )
    assert result.index.min() == pd.Timestamp("2021-01-29 04:00:00+00:00")
    assert result.index.max() == pd.Timestamp("2021-01-31 00:00:00+00:00")


def test_ensure_market_data_with_warmup_falls_back_when_history_missing():
    idx = pd.date_range("2021-01-30", periods=10, freq="h", tz="UTC")
    df_trimmed = pd.DataFrame({"open": range(10)}, index=idx)
    strategy_features = [{"name": "ema_fast", "type": "EMA", "params": {"length": 20}}]
    handler = DummyHandler(df_trimmed)
    result = ensure_market_data_with_warmup(
        market_data=df_trimmed,
        execution_timeframe="1H",
        strategy_features=strategy_features,
        global_features=[],
        data_request={"start": "2021-01-30 00:00:00", "end": "2021-01-30 09:00:00"},
        data_handler=handler,
    )
    assert result.index.min() == pd.Timestamp("2021-01-30 00:00:00+00:00")
    assert result.index.max() == pd.Timestamp("2021-01-30 09:00:00+00:00")
