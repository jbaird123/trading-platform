"""Integration tests for the chandelier stop REM indicator."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.risk_manager.models import REMConfig
from trading_platform.risk_manager.rem_indicators import (
    REM_INDICATORS_REGISTRY,
)
from trading_platform.strategy.features import compute_features


def _build_market_data(periods: int = 40) -> pd.DataFrame:
    """Create deterministic OHLC data with a gentle up-trend."""
    index = pd.date_range(start=datetime(2024, 1, 1), periods=periods, freq="D")
    base = np.linspace(100.0, 120.0, periods)
    data = {
        "open": base + 0.2,
        "high": base + 0.6,
        "low": base - 0.6,
        "close": base + 0.1,
        "volume": np.full(periods, 1_000.0),
    }
    return pd.DataFrame(data, index=index)


@pytest.fixture()
def chandelier_features() -> pd.DataFrame:
    """DataFrame with ATR, HHV, and LLV columns required by chandelier stop."""
    df = _build_market_data()
    atr_lengths = [10, 14, 21]
    swing_lengths = [20, 22, 30]
    feature_defs = []
    for atr_len in atr_lengths:
        feature_defs.append(
            {"name": f"atr_{atr_len}", "type": "ATR", "params": {"length": atr_len}}
        )
    for length in swing_lengths:
        feature_defs.extend(
            [
                {
                    "name": f"hhv_{length}",
                    "type": "HHV",
                    "params": {"length": length},
                    "source": "high",
                },
                {
                    "name": f"llv_{length}",
                    "type": "LLV",
                    "params": {"length": length},
                    "source": "low",
                },
            ]
        )
    return compute_features(df, feature_defs)


def _make_position(side: str, entry_price: float) -> Position:
    """Helper to create a simple Position instance for integration tests."""
    return Position(
        symbol="TEST",
        entry_time=datetime(2024, 1, 1),
        entry_price=entry_price,
        entry_mid_price=entry_price,
        side=side,
        size=1.0,
    )


def test_chandelier_stop_matches_indicator_math(chandelier_features: pd.DataFrame):
    """Ensure the chandelier stop equals HHV/LLV +/- ATR * multiplier."""
    spec = REM_INDICATORS_REGISTRY["chandelier"]
    params = {"multiplier": 3.0, "length": 22, "atr_length": 14}

    df_valid = chandelier_features.dropna(subset=["atr_14", "hhv_22", "llv_22"])
    assert not df_valid.empty, "Test data should produce valid indicator rows."

    for _, bar in df_valid.iterrows():
        atr_val = float(bar["atr_14"])
        expected_long = float(bar["hhv_22"]) - atr_val * params["multiplier"]
        expected_short = float(bar["llv_22"]) + atr_val * params["multiplier"]

        actual_long = spec.stop_calculator(  # type: ignore[call-arg]
            entry_price=bar["close"],
            side="long",
            current_bar=bar,
            params=params,
        )
        actual_short = spec.stop_calculator(  # type: ignore[call-arg]
            entry_price=bar["close"],
            side="short",
            current_bar=bar,
            params=params,
        )

        assert actual_long == pytest.approx(expected_long, abs=1e-9)
        assert actual_short == pytest.approx(expected_short, abs=1e-9)


@pytest.mark.parametrize(
    "multiplier,length,atr_length",
    [
        (3.0, 22, 14),  # classic defaults
        (2.0, 20, 10),  # tighter chandelier
        (4.0, 30, 21),  # wider chandelier with longer windows
    ],
)
def test_chandelier_stop_used_by_risk_exit_manager(
    chandelier_features: pd.DataFrame,
    multiplier: float,
    length: int,
    atr_length: int,
) -> None:
    """Verify RiskExitManager applies chandelier stop using prior bar data."""
    params = {
        "multiplier": multiplier,
        "length": length,
        "atr_length": atr_length,
    }
    rem_config = REMConfig(
        stop_loss={  # type: ignore[arg-type]
            "type": "indicator",
            "indicator": "chandelier",
            "params": params,
        }
    )
    rem = RiskExitManager(config=rem_config)
    spec = REM_INDICATORS_REGISTRY["chandelier"]

    hhv_col = f"hhv_{length}"
    llv_col = f"llv_{length}"
    atr_col = f"atr_{atr_length}"

    df_valid = chandelier_features.dropna(subset=[hhv_col, llv_col, atr_col])
    assert len(df_valid) >= 2

    # Use the last two fully valid bars to ensure indicators are warmed up
    prior_bar = df_valid.iloc[-2]
    current_bar = df_valid.iloc[-1].copy()

    expected_stop = spec.stop_calculator(  # type: ignore[call-arg]
        entry_price=prior_bar["close"],
        side="long",
        current_bar=prior_bar,
        params=params,
    )

    # Force current bar's low below the expected stop so the exit triggers.
    current_bar["low"] = min(current_bar["low"], expected_stop - 1e-6)

    position = _make_position(side="long", entry_price=float(prior_bar["close"]))

    exit_details = rem.check_exits(
        position=position,
        current_bar=current_bar,
        prior_bar=prior_bar,
    )

    assert exit_details is not None
    assert exit_details["reason"] == "stop-loss"
    assert exit_details["exit_price"] == pytest.approx(expected_stop, abs=1e-9)


def test_chandelier_stop_triggers_short_exit(chandelier_features: pd.DataFrame):
    """Ensure short positions exit when support chandelier is breached."""
    params = {"multiplier": 3.0, "length": 22, "atr_length": 14}
    rem_config = REMConfig(
        stop_loss={  # type: ignore[arg-type]
            "type": "indicator",
            "indicator": "chandelier",
            "params": params,
        }
    )
    rem = RiskExitManager(config=rem_config)
    spec = REM_INDICATORS_REGISTRY["chandelier"]

    df_valid = chandelier_features.dropna(subset=["atr_14", "hhv_22", "llv_22"])
    assert len(df_valid) >= 3

    prior_bar = df_valid.iloc[-3]
    current_bar = df_valid.iloc[-2].copy()
    expected_stop = spec.stop_calculator(  # type: ignore[call-arg]
        entry_price=prior_bar["close"],
        side="short",
        current_bar=prior_bar,
        params=params,
    )

    # Force current bar's high above the chandelier stop to trigger exit.
    current_bar["high"] = max(current_bar["high"], expected_stop + 1e-6)

    position = _make_position(side="short", entry_price=float(prior_bar["close"]))

    exit_details = rem.check_exits(
        position=position,
        current_bar=current_bar,
        prior_bar=prior_bar,
    )

    assert exit_details is not None
    assert exit_details["reason"] == "stop-loss"
    assert exit_details["exit_price"] == pytest.approx(expected_stop, abs=1e-9)
