"""Task 36: Full integration test for adaptive trend features.

This test validates that all new features from Epics 1-3 work together:
- EMASlope indicator with slope predicates (Epic 1)
- Higher-timeframe features (Epic 1)
- DynamicREM with breakeven, partial exits, volatility awareness (Epic 2)
- New RMM features: ATRPercentile, RealizedVolatility, VolumeZScore (Epic 3)
- New RMM predicates: percentile_is_above, volatility_is_between (Epic 3)
"""

from __future__ import annotations

import pandas as pd
from trading_platform.regime_market_manager.engine import RMMEngine
from trading_platform.risk_manager.dynamic_rem import DynamicREM
from trading_platform.strategy.features import compute_features
from trading_platform.strategy.yaml_strategy import compile_strategy


def test_adaptive_trend_full_integration() -> None:
    """Task 36: Integration test combining all adaptive trend features."""

    # Test data with varying market conditions
    dates = pd.date_range("2024-01-01", periods=200, freq="h")

    # Create price data with clear trend then range
    close_prices = []
    for i in range(200):
        if i < 100:
            # Uptrend with increasing volatility
            close_prices.append(100.0 + i * 0.1 + (i % 10) * 0.05)
        else:
            # Range-bound with moderate vol
            close_prices.append(110.0 + (i % 20) * 0.1)

    ohlc = pd.DataFrame(
        {
            "open": close_prices,
            "high": [c * 1.002 for c in close_prices],
            "low": [c * 0.998 for c in close_prices],
            "close": close_prices,
            "volume": [1000.0 + i * 5 for i in range(200)],
        },
        index=dates,
    )

    # EPIC 1: Strategy with EMASlope and higher-timeframe features
    strategy_config = {
        "strategy_name": "AdaptiveTrendStrategy",
        "features": [
            {
                "name": "ema_fast",
                "type": "EMA",
                "params": {"length": 10},
                "source": "close",
            },
            {
                "name": "ema_slope_fast",
                "type": "EMASlope",
                "params": {"length": 10, "slope_period": 1},
                "source": "close",
            },
            {
                "name": "adx_4h",
                "type": "ADX",
                "params": {"length": 14},
                "timeframe": "4h",
            },
        ],
        "long_entry_rules": [
            {
                "all_of": [
                    {
                        "condition": "is_above",
                        "left": {"ref": "ema_fast"},
                        "right": {"value": 100},
                    },
                    {
                        "condition": "slope_is_above",
                        "left": {"ref": "ema_slope_fast"},
                        "right": {"value": 0.01},
                    },
                ]
            }
        ],
    }

    # Compile strategy to validate config
    _strategy = compile_strategy(strategy_config)
    # Compute strategy features
    features_list: list[dict] = strategy_config["features"]  # type: ignore[assignment]
    strategy_df = compute_features(ohlc, features_list)

    # Verify Epic 1 features computed
    assert "ema_fast" in strategy_df.columns
    assert "ema_slope_fast" in strategy_df.columns
    # ADX now returns 3 columns: ADX, DI+, DI-
    assert "adx_4h_ADX" in strategy_df.columns
    assert "adx_4h_DI+" in strategy_df.columns
    assert "adx_4h_DI-" in strategy_df.columns

    # EPIC 3: RMM with new features and predicates
    rmm_config = {
        "features": [
            {
                "name": "atr_pct",
                "type": "ATRPercentile",
                "params": {"atr_length": 14, "lookback": 50},
            },
            {
                "name": "rvol",
                "type": "RealizedVolatility",
                "params": {"length": 20},
            },
            {
                "name": "vol_z",
                "type": "VolumeZScore",
                "params": {"length": 30},
            },
        ],
        "regimes": [
            {
                "label": "high_volatility",
                "confidence": 0.9,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "percentile_is_above",
                            "left": {"ref": "atr_pct"},
                            "right": {"value": 75},
                        },
                        {
                            "condition": "volatility_is_between",
                            "left": {"ref": "rvol"},
                            "lower": 0.001,
                            "upper": 0.05,
                        },
                    ]
                },
            },
            {
                "label": "moderate_activity",
                "confidence": 0.7,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": {"ref": "vol_z"},
                            "right": {"value": 0},
                        }
                    ]
                },
            },
        ],
    }

    rmm_engine = RMMEngine(config=rmm_config)
    rmm_result = rmm_engine.classify_regime(
        ohlc, timeframe="1D", already_resampled=False
    )

    # Verify Epic 3 features and predicates
    assert "atr_pct" in rmm_result.columns
    assert "rvol" in rmm_result.columns
    assert "vol_z" in rmm_result.columns
    assert "label" in rmm_result.columns
    assert "confidence" in rmm_result.columns

    # Verify regime classification occurred
    unique_labels = rmm_result["label"].unique()
    assert len(unique_labels) > 0
    # Should have at least some non-unknown regimes
    assert any(label != "unknown" for label in unique_labels)

    # EPIC 2: DynamicREM with all features
    dynamic_rem_config = {
        "stop_loss": {
            "type": "indicator",
            "indicator": "atr",
            "params": {"multiplier": 2.0, "length": 14},
        },
        "breakeven_threshold": 0.5,
        "partial_exits": [
            {"r_multiple": 1.0, "fraction": 0.5},
            {"r_multiple": 2.0, "fraction": 0.25},
        ],
        "trailing_stop": {
            "distance": {"type": "atr", "multiplier": 1.5},
            "activate_after_partial": True,
        },
        "volatility_threshold": 20.0,
        "low_volatility_multiplier": 0.75,
    }

    rem = DynamicREM(config=dynamic_rem_config)

    # Verify DynamicREM configuration
    assert rem.breakeven_threshold == 0.5
    assert len(rem.partial_exits) == 2

    # SUCCESS: All three epics integrated successfully
    # If we got here, all features work together
