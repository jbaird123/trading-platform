from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def _trade(
    pnl: float,
    exit_reason: str,
    *,
    mfe: float | None,
    mae: float | None,
) -> Trade:
    entry = datetime(2024, 1, 1, 0, 0, 0)
    return Trade(
        symbol="EURUSD",
        entry_time=entry,
        exit_time=entry + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason=exit_reason,
        mfe_currency=mfe,
        mae_currency=mae,
    )


def test_generate_brief_handles_signal_dataframe_and_artifacts(monkeypatch, tmp_path):
    trades = [
        _trade(12.5, "take_profit", mfe=20.0, mae=None),
        _trade(-7.2, "stop_loss", mfe=None, mae=9.0),
    ]

    def fake_exists(path: str) -> bool:
        return path.endswith("signals.parquet")

    def fake_read_parquet(path: str) -> pd.DataFrame:
        assert path.endswith("signals.parquet")
        return pd.DataFrame({"signal": ["long", "long", "flat", "short", "short"]})

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", fake_read_parquet)

    brief_data = generate_brief(
        meta={},
        params={},
        trades=trades,
        initial_cash=10_000.0,
        signals_path=str(tmp_path / "signals.parquet"),
        rmm_spans_path="/tmp/rmm.parquet",
        processed_data_path="/tmp/data.parquet",
        skipped_trades=[{"reason_code": "blackout", "cf_pnl_currency": 12.3456}],
    )

    sq = brief_data["signal_quality_analysis"]
    assert sq["signal_persistence_pct"] > 0.0
    assert sq["avg_signal_duration_bars"] > 0.0
    assert "signals_path" in brief_data["artifacts"]
    assert "checksums" not in brief_data
    filt = brief_data["filter_impact"]["blackout"]
    assert filt["total_cf_pnl"] == 12.35


def test_generate_brief_handles_signal_series_with_flat_values(monkeypatch, tmp_path):
    trade = _trade(5.0, "take_profit", mfe=6.0, mae=None)

    def fake_exists(_: str) -> bool:
        return True

    def fake_read_parquet(_: str) -> pd.Series:
        return pd.Series(["flat", "flat", "flat"])

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", fake_read_parquet)

    brief_data = generate_brief(
        meta={},
        params={},
        trades=[trade],
        initial_cash=1_000.0,
        signals_path=str(tmp_path / "signals.parquet"),
    )

    sq = brief_data["signal_quality_analysis"]
    assert sq["signal_persistence_pct"] == 0.0
    assert sq["avg_signal_duration_bars"] == 0.0


def test_generate_brief_errors_when_signal_column_missing(monkeypatch, tmp_path):
    trade = _trade(1.0, "take_profit", mfe=2.0, mae=None)

    def fake_exists(_: str) -> bool:
        return True

    def fake_read_parquet(_: str) -> pd.DataFrame:
        return pd.DataFrame({"price": [1, 2, 3]})

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", fake_read_parquet)

    with pytest.raises(ValueError):
        generate_brief(
            meta={},
            params={},
            trades=[trade],
            initial_cash=500.0,
            signals_path=str(tmp_path / "signals.parquet"),
        )


def test_generate_brief_errors_for_invalid_signal_object(monkeypatch, tmp_path):
    trade = _trade(1.0, "take_profit", mfe=2.0, mae=None)

    def fake_exists(_: str) -> bool:
        return True

    class BadSignals:
        pass

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", lambda _: BadSignals())

    with pytest.raises(ValueError):
        generate_brief(
            meta={},
            params={},
            trades=[trade],
            initial_cash=500.0,
            signals_path=str(tmp_path / "signals.parquet"),
        )


def test_generate_brief_ignores_io_errors_when_loading_signals(monkeypatch, tmp_path):
    trade = _trade(1.0, "take_profit", mfe=2.0, mae=None)

    def fake_exists(_: str) -> bool:
        return True

    def fake_reader(_: str) -> pd.DataFrame:
        raise pd.errors.ParserError("bad file")

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", fake_reader)

    brief_data = generate_brief(
        meta={},
        params={},
        trades=[trade],
        initial_cash=500.0,
        signals_path=str(tmp_path / "signals.parquet"),
    )

    assert brief_data["signal_quality_analysis"] == {
        "signal_persistence_pct": 0.0,
        "avg_signal_duration_bars": 0.0,
    }


def test_generate_brief_handles_null_signal_column(monkeypatch, tmp_path):
    trade = _trade(1.0, "take_profit", mfe=2.0, mae=None)

    class NullSignals(pd.DataFrame):
        @property
        def _constructor(self) -> type[NullSignals]:
            return NullSignals

        def __getitem__(self, key: str):  # type: ignore[override]
            if key == "signal":
                return None
            return super().__getitem__(key)

    def fake_exists(_: str) -> bool:
        return True

    def fake_reader(_: str) -> NullSignals:
        return NullSignals({"signal": ["flat", "long"]})

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", fake_reader)

    brief_data = generate_brief(
        meta={},
        params={},
        trades=[trade],
        initial_cash=500.0,
        signals_path=str(tmp_path / "signals.parquet"),
    )

    assert brief_data["signal_quality_analysis"] == {
        "signal_persistence_pct": 0.0,
        "avg_signal_duration_bars": 0.0,
    }
