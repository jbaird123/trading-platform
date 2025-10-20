"""Task 37: Performance profiling and benchmarking for adaptive trend features.

This test profiles the integration test from Task 36 to measure the runtime
cost of new features, particularly multi-timeframe data handling.
"""

from __future__ import annotations

import cProfile
import pstats
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest
from trading_platform.regime_market_manager.engine import RMMEngine
from trading_platform.risk_manager.dynamic_rem import DynamicREM
from trading_platform.strategy.features import compute_features
from trading_platform.strategy.yaml_strategy import compile_strategy


@pytest.fixture
def test_data():
    """Create test data for profiling."""
    dates = pd.date_range("2024-01-01", periods=1000, freq="h")
    close_prices = []
    for i in range(1000):
        if i < 500:
            close_prices.append(100.0 + i * 0.1 + (i % 10) * 0.05)
        else:
            close_prices.append(110.0 + (i % 20) * 0.1)

    return pd.DataFrame(
        {
            "open": close_prices,
            "high": [c * 1.002 for c in close_prices],
            "low": [c * 0.998 for c in close_prices],
            "close": close_prices,
            "volume": [1000.0 + i * 5 for i in range(1000)],
        },
        index=dates,
    )


def profile_strategy_features(ohlc: pd.DataFrame) -> tuple[pd.DataFrame, pstats.Stats]:
    """Profile Epic 1 strategy features computation."""
    strategy_config = {
        "strategy_name": "ProfileStrategy",
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
                    {"condition": "is_above", "left": {"ref": "ema_fast"}, "right": {"value": 100}}
                ]
            }
        ],
    }

    profiler = cProfile.Profile()
    profiler.enable()

    _strategy = compile_strategy(strategy_config)
    features_list: list[dict] = strategy_config["features"]  # type: ignore[assignment]
    strategy_df = compute_features(ohlc, features_list)

    profiler.disable()

    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    return strategy_df, ps


def profile_rmm_features(ohlc: pd.DataFrame) -> tuple[pd.DataFrame, pstats.Stats]:
    """Profile Epic 3 RMM features computation."""
    rmm_config = {
        "features": [
            {
                "name": "atr_pct",
                "type": "ATRPercentile",
                "params": {"atr_length": 14, "lookback": 50},
            },
            {"name": "rvol", "type": "RealizedVolatility", "params": {"length": 20}},
            {"name": "vol_z", "type": "VolumeZScore", "params": {"length": 30}},
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
                        }
                    ]
                },
            }
        ],
    }

    profiler = cProfile.Profile()
    profiler.enable()

    rmm_engine = RMMEngine(config=rmm_config)
    rmm_result = rmm_engine.classify_regime(
        ohlc, timeframe="1D", already_resampled=False
    )

    profiler.disable()

    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    return rmm_result, ps


def test_profile_adaptive_trend_features(
    test_data: pd.DataFrame, tmp_path: Path
) -> None:
    """Task 37: Profile all adaptive trend features and document performance."""

    print("\n" + "=" * 80)
    print("TASK 37: ADAPTIVE TREND PERFORMANCE PROFILING")
    print("=" * 80)

    # Profile strategy features (Epic 1)
    print("\n📊 Profiling Epic 1: Strategy Features " "(EMASlope + Higher-Timeframe)")
    strategy_df, strategy_stats = profile_strategy_features(test_data)
    strategy_stats.print_stats(20)

    # Profile RMM features (Epic 3)
    print(
        "\n📊 Profiling Epic 3: RMM Features "
        "(ATRPercentile, RealizedVolatility, VolumeZScore)"
    )
    rmm_df, rmm_stats = profile_rmm_features(test_data)
    rmm_stats.print_stats(20)

    # Get timing summaries
    strategy_total = sum(stat[3] for stat in strategy_stats.stats.values())  # type: ignore[attr-defined]
    rmm_total = sum(stat[3] for stat in rmm_stats.stats.values())  # type: ignore[attr-defined]

    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"Epic 1 (Strategy Features) Total Time: {strategy_total:.4f}s")
    print(f"Epic 3 (RMM Features) Total Time: {rmm_total:.4f}s")
    print(f"Combined Total Time: {strategy_total + rmm_total:.4f}s")

    # Write detailed report
    report_path = tmp_path / "performance_report.txt"
    with report_path.open("w") as f:
        f.write("ADAPTIVE TREND PERFORMANCE PROFILING REPORT\n")
        f.write("=" * 80 + "\n\n")

        f.write("Epic 1: Strategy Features\n")
        f.write("-" * 40 + "\n")
        strategy_stats.stream = f  # type: ignore[attr-defined]
        strategy_stats.print_stats(30)

        f.write("\n\nEpic 3: RMM Features\n")
        f.write("-" * 40 + "\n")
        rmm_stats.stream = f  # type: ignore[attr-defined]
        rmm_stats.print_stats(30)

        f.write("\n\nSUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Epic 1 Total Time: {strategy_total:.4f}s\n")
        f.write(f"Epic 3 Total Time: {rmm_total:.4f}s\n")
        f.write(f"Combined Total: {strategy_total + rmm_total:.4f}s\n")

        # Check for 20% threshold
        total_time = strategy_total + rmm_total
        if strategy_total / total_time > 0.2:
            pct = strategy_total / total_time * 100
            f.write(
                f"\n⚠️  WARNING: Epic 1 features take {pct:.1f}% "
                f"of total time (>20%)\n"
            )
        if rmm_total / total_time > 0.2:
            pct = rmm_total / total_time * 100
            f.write(
                f"\n⚠️  WARNING: Epic 3 features take {pct:.1f}% "
                f"of total time (>20%)\n"
            )

    print(f"\n✅ Detailed report saved to: {report_path}")
    print("=" * 80)

    # Assertions
    assert len(strategy_df) == len(test_data)
    assert len(rmm_df) > 0  # RMM resamples to 1D, so fewer rows expected
    assert "ema_slope_fast" in strategy_df.columns
    # ADX now returns 3 columns: ADX, DI+, DI-
    assert "adx_4h_ADX" in strategy_df.columns
    assert "adx_4h_DI+" in strategy_df.columns
    assert "adx_4h_DI-" in strategy_df.columns
    assert "atr_pct" in rmm_df.columns
    assert "rvol" in rmm_df.columns
    assert "vol_z" in rmm_df.columns


def test_dynamic_rem_performance_overhead() -> None:
    """Test that DynamicREM config validation has minimal overhead."""
    # Simply test that DynamicREM can be instantiated quickly
    import time

    config = {
        "stop_loss": {"atr_multiple": 2.0, "atr_length": 14},
        "breakeven_threshold": 0.5,
        "partial_exits": [
            {"r_multiple": 1.0, "reduction_pct": 50},
            {"r_multiple": 2.0, "reduction_pct": 25},
        ],
        "trailing_stop": {
            "atr_multiple": 1.5,
            "atr_length": 14,
            "activate_after_partial": True,
        },
        "volatility_tightening": {"adx_threshold": 20, "tighten_multiplier": 0.75},
    }

    start = time.perf_counter()
    for _ in range(1000):
        _rem = DynamicREM(config=config)
    elapsed = time.perf_counter() - start

    print("\n" + "=" * 80)
    print("DYNAMICREM INSTANTIATION PERFORMANCE (1000 iterations)")
    print("=" * 80)
    print(f"Total time: {elapsed:.4f}s")
    print(f"Average time per instantiation: {elapsed/1000*1000:.4f}ms")
    print("=" * 80)

    # Should be very fast
    assert elapsed < 0.1  # Less than 0.1s for 1000 instantiations
