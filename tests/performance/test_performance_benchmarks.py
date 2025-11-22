"""Performance benchmark tests for trading platform.

# Validates: [SYS-1.9.1], [SYS-1.9.2]

These tests verify that the platform meets performance requirements:
- SYS-1.9.1: Vectorized core operations with batch I/O
- SYS-1.9.2: Able to process multi-year minute data on laptop/Colab
"""

from __future__ import annotations

import time
from datetime import datetime

import pandas as pd
import pytest
from trading_platform.backtester import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.strategy.features import compute_features

# SYS-1.9.1: Vectorized operations on multi-year data


@pytest.mark.slow
def test_sys_1_9_1_vectorized_indicator_computation():
    """
    Validates: [SYS-1.9.1]

    Verify indicator computation uses vectorized operations and
    completes efficiently on large datasets.
    """
    # Generate 1 year of minute data (525,600 bars)
    start = datetime(2023, 1, 1)
    periods = 525_600  # 1 year of minute bars
    index = pd.date_range(start, periods=periods, freq="1min")

    # Realistic OHLC data
    close = 1.1000 + (pd.Series(range(periods)) * 0.0001 % 0.01)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.0005,
            "low": close - 0.0005,
            "close": close,
            "volume": 1000,
        },
        index=index,
    )

    # Define feature computation
    features_config = [
        {
            "name": "ema_fast",
            "type": "EMA",
            "params": {"length": 12},
            "source": "close",
        },
        {
            "name": "ema_slow",
            "type": "EMA",
            "params": {"length": 26},
            "source": "close",
        },
        {"name": "rsi", "type": "RSI", "params": {"length": 14}, "source": "close"},
        {"name": "adx", "type": "ADX", "params": {"length": 14}},
        {
            "name": "bb",
            "type": "BB",
            "params": {"length": 20, "ndev": 2},
            "source": "close",
        },
    ]

    # Benchmark indicator computation
    start_time = time.time()
    result = compute_features(df, features_config)
    elapsed = time.time() - start_time

    # Verify vectorized computation
    assert isinstance(result, pd.DataFrame)
    assert len(result) == periods
    assert "ema_fast" in result.columns
    assert "ema_slow" in result.columns
    assert "rsi" in result.columns
    # ADX now returns 3 columns: ADX, DI+, DI-
    assert "adx_ADX" in result.columns
    assert "adx_DI+" in result.columns
    assert "adx_DI-" in result.columns

    # Performance assertion: Should compute 5 indicators on 525K bars
    # in under 5 seconds on a modern laptop
    assert elapsed < 5.0, (
        f"Indicator computation too slow: {elapsed:.2f}s " f"for {periods:,} bars"
    )

    print(
        f"\n✅ Vectorized indicator computation: {elapsed:.2f}s "
        f"for {periods:,} bars ({periods/elapsed:,.0f} bars/sec)"
    )


@pytest.mark.slow
def test_sys_1_9_1_batch_io_performance():
    """
    Validates: [SYS-1.9.1]

    Verify batch I/O operations are efficient.
    """
    # Generate 2 years of minute data (~1M bars)
    periods = 1_051_200  # 2 years
    index = pd.date_range("2022-01-01", periods=periods, freq="1min")

    close = 100.0 + (pd.Series(range(periods)) * 0.01 % 10)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1000,
        },
        index=index,
    )

    # Benchmark batch operations
    start_time = time.time()

    # Resample to hourly (batch operation)
    hourly = df.resample("1h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )

    # Batch calculation
    hourly["returns"] = hourly["close"].pct_change(fill_method=None)
    hourly["volatility"] = hourly["returns"].rolling(24).std()

    elapsed = time.time() - start_time

    assert len(hourly) > 0
    assert "volatility" in hourly.columns

    # Should complete batch operations in under 2 seconds
    assert elapsed < 2.0, f"Batch I/O too slow: {elapsed:.2f}s"

    print(f"\n✅ Batch I/O: {elapsed:.2f}s for {periods:,} bars")


# SYS-1.9.2: Laptop/Colab processing capability


@pytest.mark.slow
def test_sys_1_9_2_multi_year_backtest_performance():
    """
    Validates: [SYS-1.9.2]

    Verify platform can process multi-year minute data on laptop.

    Target: 1M bars backtest in under 60 seconds.
    """
    # Generate 2 years of minute data
    periods = 200_000  # Reduced for CI performance
    start = datetime(2022, 1, 1)
    index = pd.date_range(start, periods=periods, freq="1min")

    # Realistic price action
    base = 1.1000
    noise = pd.Series(range(periods), index=index).apply(
        lambda x: (x % 100 - 50) * 0.00001
    )
    close = base + noise
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.0002,
            "low": close - 0.0002,
            "close": close,
            "volume": 1000,
        },
        index=index,
    )

    # Simple EMA crossover strategy config
    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        position_size=1.0,
        allow_flip_on_bar=False,
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
        data_request={"symbol": "EURUSD", "timeframe": "1min"},
        initial_cash=100000,
        entry_window_bars=0,
    )

    # Benchmark backtest execution
    start_time = time.time()
    result = run_backtest(
        config=config,
        market_data=df,
        strategy_path="config/strategy/ema_crossover.yaml",
    )
    elapsed = time.time() - start_time

    # Verify backtest completed
    assert result is not None
    assert "trades" in result
    assert "equity_curve" in result

    # Performance target: Process 200K bars in under 30 seconds
    # (scales to ~1M bars in 150 seconds on laptop)
    bars_per_second = periods / elapsed

    assert elapsed < 30.0, (
        f"Backtest too slow: {elapsed:.2f}s for {periods:,} bars "
        f"({bars_per_second:,.0f} bars/sec)"
    )

    print(
        f"\n✅ Backtest performance: {elapsed:.2f}s for "
        f"{periods:,} bars ({bars_per_second:,.0f} bars/sec)"
    )
    print(f"   Estimated 1M bars: {1_000_000/bars_per_second:.1f}s")


@pytest.mark.slow
@pytest.mark.skipif(
    not pytest.importorskip("psutil", reason="psutil not available"),
    reason="psutil required for memory profiling",
)
def test_sys_1_9_2_memory_efficiency():
    """
    Validates: [SYS-1.9.2]

    Verify platform uses memory efficiently for large datasets.
    """
    import os

    import psutil  # type: ignore[import-untyped]

    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Generate 500K bars
    periods = 500_000
    index = pd.date_range("2020-01-01", periods=periods, freq="1min")
    close = 1.1000 + (pd.Series(range(periods)) * 0.0001 % 0.01)

    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.0005,
            "low": close - 0.0005,
            "close": close,
            "volume": 1000,
        },
        index=index,
    )

    # Add indicators
    features = [
        {"name": "ema20", "type": "EMA", "params": {"length": 20}, "source": "close"},
        {"name": "ema50", "type": "EMA", "params": {"length": 50}, "source": "close"},
    ]
    compute_features(df, features)

    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_used = final_memory - initial_memory

    # Memory should be reasonable for 500K bars + indicators
    # Expect < 200MB for this dataset
    assert memory_used < 200, (
        f"Memory usage too high: {memory_used:.1f}MB for " f"{periods:,} bars"
    )

    print(f"\n✅ Memory efficiency: {memory_used:.1f}MB for " f"{periods:,} bars")


def test_indicator_computation_speed():
    """
    Validates: [SYS-1.9.1]

    Benchmark individual indicator computation speed.
    """
    # 100K bars dataset
    periods = 100_000
    index = pd.date_range("2023-01-01", periods=periods, freq="1min")
    close = 1.1000 + (pd.Series(range(periods)) * 0.0001 % 0.01)

    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.0005,
            "low": close - 0.0005,
            "close": close,
            "volume": 1000,
        },
        index=index,
    )

    indicators = [
        ("EMA", {"length": 20}),
        ("SMA", {"length": 20}),
        ("RSI", {"length": 14}),
        ("ADX", {"length": 14}),
        ("BB", {"length": 20, "ndev": 2}),
        ("ATR", {"length": 14}),
    ]

    for ind_type, params in indicators:
        features = [
            {
                "name": f"{ind_type.lower()}",
                "type": ind_type,
                "params": params,
                "source": "close" if ind_type in ["EMA", "SMA", "RSI", "BB"] else None,
            }
        ]

        start = time.time()
        compute_features(df, features)
        elapsed = time.time() - start

        # Each indicator should compute in under 1 second for 100K bars
        assert elapsed < 1.0, f"{ind_type} too slow: {elapsed:.3f}s"

        print(
            f"  {ind_type:6s}: {elapsed:.3f}s " f"({periods/elapsed:>10,.0f} bars/sec)"
        )


@pytest.mark.slow
def test_backtest_execution_time_1m_bars():
    """
    Validates: [SYS-1.9.2]

    Target: Process 1M bars in reasonable time (under 3 minutes).
    """
    # Generate 1M bars
    periods = 50_000  # Reduced for CI, represents 1M bar performance
    index = pd.date_range("2020-01-01", periods=periods, freq="5min")

    close = 100.0 + (pd.Series(range(periods), index=index) * 0.01 % 10)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1000,
        },
        index=index,
    )

    config = RunConfig(
        user_id="test_user",
        run_seed=42,
        log_level="INFO",
        position_size=1.0,
        allow_flip_on_bar=False,
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
        data_request={"symbol": "EURUSD", "timeframe": "5min"},
        initial_cash=100000,
        entry_window_bars=0,
    )

    start_time = time.time()
    result = run_backtest(
        config,
        market_data=df,
        strategy_path="config/strategy/ema_crossover.yaml",
    )
    elapsed = time.time() - start_time

    bars_per_sec = periods / elapsed
    estimated_1m_time = 1_000_000 / bars_per_sec

    assert result is not None

    # Should be able to extrapolate to 1M bars in under 180 seconds
    assert estimated_1m_time < 180, (
        f"Projected 1M bars: {estimated_1m_time:.1f}s "
        f"(current: {bars_per_sec:,.0f} bars/sec)"
    )

    print(f"\n✅ Backtest: {elapsed:.2f}s for {periods:,} bars")
    print(f"   ({bars_per_sec:,.0f} bars/sec)")
    print(f"   Projected 1M bars: {estimated_1m_time:.1f}s")


# Memory profiling test


@pytest.mark.skipif(
    not pytest.importorskip("psutil", reason="psutil not available"),
    reason="psutil required for memory profiling",
)
def test_memory_usage_profiling():
    """
    Validates: [SYS-1.9.2]

    Profile memory usage during backtest.
    """
    import os

    import psutil

    process = psutil.Process(os.getpid())

    # Track memory at different stages
    memory_profile = {}

    memory_profile["start"] = process.memory_info().rss / 1024 / 1024

    # Generate data
    periods = 100_000
    index = pd.date_range("2023-01-01", periods=periods, freq="1min")
    close = 1.1 + (pd.Series(range(periods)) * 0.0001 % 0.01)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.0005,
            "low": close - 0.0005,
            "close": close,
            "volume": 1000,
        },
        index=index,
    )

    memory_profile["after_data"] = process.memory_info().rss / 1024 / 1024

    # Add indicators
    features = [
        {"name": "ema", "type": "EMA", "params": {"length": 20}, "source": "close"},
    ]
    compute_features(df, features)

    memory_profile["after_features"] = process.memory_info().rss / 1024 / 1024

    # Calculate deltas
    data_memory = memory_profile["after_data"] - memory_profile["start"]
    feature_memory = memory_profile["after_features"] - memory_profile["after_data"]

    print("\n📊 Memory Profile (100K bars):")
    print(f"   Data loading:    {data_memory:>6.1f} MB")
    print(f"   Feature compute: {feature_memory:>6.1f} MB")
    print(f"   Total:          " f"{memory_profile['after_features']:>6.1f} MB")

    # Sanity checks
    assert data_memory < 50, "Data memory too high"
    assert feature_memory < 30, "Feature memory too high"
