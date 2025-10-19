# Validates: [DH-2.3], [DH-2.6]
from __future__ import annotations

import pandas as pd
import pytest
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def _instrument(symbol: str = "EURUSD") -> dict[str, str]:
    """Helper to create instrument dict for RunConfig."""
    return {"symbol": symbol}


def _dummy_strategy() -> CompiledStrategy:
    return CompiledStrategy(
        name="dummy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )


def _mdf(n: int = 3) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=n, freq="min")
    df = pd.DataFrame(
        {
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
            "volume": 100,
        },
        index=idx,
    )
    return df


def _signals(n: int = 3, value=None) -> pd.Series:
    idx = pd.date_range("2023-01-01", periods=n, freq="min")
    return pd.Series([value] * n, index=idx, dtype=object)


def test_validation_missing_columns():
    df = _mdf().drop(columns=["volume"])  # missing required column
    sig = _signals()
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config={})
    with pytest.raises(ValueError, match="missing required columns"):
        run_backtest(df, sig, strategy=_dummy_strategy(), config=config, rem=rem)


def test_validation_close_has_nans():
    df = _mdf()
    df.loc[df.index[1], "close"] = pd.NA
    sig = _signals()
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config={})
    with pytest.raises(ValueError, match="close has NaNs"):
        run_backtest(df, sig, strategy=_dummy_strategy(), config=config, rem=rem)


def test_validation_length_mismatch():
    df = _mdf(3)
    sig = _signals(2)
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config={})
    with pytest.raises(ValueError, match="signals length "):
        run_backtest(df, sig, strategy=_dummy_strategy(), config=config, rem=rem)


def test_validation_invalid_signal_value():
    df = _mdf(2)
    sig = _signals(2)
    sig.iloc[1] = "hold"  # invalid
    config = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        instrument=_instrument(),
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
    )
    rem = RiskExitManager(config={})
    with pytest.raises(ValueError, match="invalid command values"):
        run_backtest(df, sig, strategy=_dummy_strategy(), config=config, rem=rem)
