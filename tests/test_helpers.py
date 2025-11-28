"""Test helpers for creating warmup-aware test data.

This module provides utilities to automatically generate test data with sufficient
warmup periods for indicators to initialize properly.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, TypeAlias, cast

import pandas as pd
from trading_platform.backtester import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy

BacktestResult: TypeAlias = Any


def run_backtest_simulation(
    market_data: pd.DataFrame,
    signals: pd.Series,
    strategy: CompiledStrategy,
    config: RunConfig,
    rem: RiskExitManager | None = None,
    *,
    rmm_context: dict[datetime, dict[str, Any]] | None = None,
    return_exposure: bool = False,
    return_skips: bool = False,
    data_handler: Any | None = None,
    global_features_config_path: Path | str | None = None,
) -> BacktestResult:
    """Backtest helper that mirrors the legacy core simulation semantics."""

    def _to_utc_index(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
        if idx.tz is None:
            return idx.tz_localize("UTC")
        return idx.tz_convert("UTC")

    # Normalize all time axes to UTC to avoid naive/aware comparison errors.
    md_idx = cast(pd.DatetimeIndex, market_data.index)
    if not md_idx.tz:
        market_data = market_data.copy()
        market_data.index = _to_utc_index(md_idx)
    else:
        market_data = market_data.tz_convert("UTC")

    if getattr(signals, "index", None) is not None:
        sig_idx = cast(pd.DatetimeIndex, signals.index)
        if sig_idx.tz is None:
            signals = signals.copy()
            signals.index = _to_utc_index(sig_idx)
        else:
            signals = signals.tz_convert("UTC")

    normalized_rmm: dict[datetime, dict[str, Any]] | None = None
    if rmm_context is not None:
        normalized_rmm = {}
        for k, v in rmm_context.items():
            ts = pd.Timestamp(k)
            ts = ts.tz_localize("UTC") if ts.tz is None else ts.tz_convert("UTC")
            normalized_rmm[ts.to_pydatetime()] = v
    else:
        normalized_rmm = rmm_context

    # All data must be bar-close aligned - no backward compatibility for bar-open data.
    feature_df = getattr(strategy, "_feature_df", None)
    if feature_df is not None:
        feature_df = feature_df.copy()
        feature_df.index = _to_utc_index(cast(pd.DatetimeIndex, feature_df.index))
    result = cast(
        BacktestResult,
        run_backtest(
            config=config,
            market_data=market_data,
            compiled_strategy=strategy,
            precomputed_signals=signals,
            feature_enriched_df=feature_df,
            data_handler=data_handler,
            global_features_config_path=global_features_config_path,
            rmm_context=normalized_rmm,
            return_exposure=return_exposure,
            return_skips=return_skips,
            rem_instance=rem,
        ),
    )

    if return_exposure:
        return result
    if return_skips:
        if isinstance(result, dict):
            trades_out = cast(list[Any], result.get("trades", []))
            skipped = cast(list[dict[str, Any]], result.get("skipped", []))
        else:
            trades_out = cast(list[Any], result)
            skipped = []
        empty_curve: list[tuple[datetime, float]] = []
        return (trades_out, empty_curve, skipped)
    if isinstance(result, dict):
        return cast(list[Any], result.get("trades", []))
    return result


def create_market_data_with_warmup(
    start_date: datetime,
    end_date: datetime,
    freq: str = "1H",
    execution_timeframe: str = "1H",
    strategy_features: list[dict[str, Any]] | None = None,
    include_global_features: bool = True,
    ohlcv_values: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Create test market data with automatic warmup buffer for indicators.

    This function calculates the required warmup period based on the strategy features
    and global features, then generates data starting earlier to ensure all indicators
    can initialize properly.

    Args:
        start_date: Desired backtest start date (warmup will be added before this)
        end_date: End date for the data
        freq: Frequency of the bars (e.g., "1H", "15min", "1D")
        execution_timeframe: Execution timeframe for the backtest
        strategy_features: List of strategy feature definitions (optional)
        include_global_features: Whether to include global features from
            config/features/global.yaml
        ohlcv_values: Default OHLCV values to use
            (default: {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0,
            "volume": 100})

    Returns:
        DataFrame with OHLCV data starting from (start_date - warmup_buffer) to end_date
    """
    from pathlib import Path

    from trading_platform.backtester.warmup import calculate_warmup_start_date

    # Default OHLCV values
    if ohlcv_values is None:
        ohlcv_values = {
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
            "volume": 100,
        }

    # Load global features if requested
    global_features: list[dict[str, Any]] = []
    if include_global_features:
        try:
            from trading_platform.core.feature_resolver import (
                resolve_global_features,
            )

            config_path = (
                Path(__file__).parent.parent / "config" / "features" / "global.yaml"
            )
            resolved = resolve_global_features(
                execution_timeframe, config_path=config_path
            )
            global_features = [
                {
                    "name": f.name,
                    "type": f.type,
                    "params": f.params,
                    "source": f.source,
                    **(
                        {}
                        if f.timeframe == execution_timeframe
                        else {"timeframe": f.timeframe}
                    ),
                }
                for f in resolved
            ]
        except Exception:
            # If global features can't be loaded, skip them
            pass

    # Create initial data from start to end (we'll extend it backwards later)
    # We need at least some data to calculate the warmup requirement
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    freq_alias = freq.replace("H", "h") if isinstance(freq, str) else freq
    initial_index = pd.date_range(start_ts, end_ts, freq=freq_alias)
    temp_df = pd.DataFrame(
        {
            "open": ohlcv_values["open"],
            "high": ohlcv_values["high"],
            "low": ohlcv_values["low"],
            "close": ohlcv_values["close"],
            "volume": ohlcv_values["volume"],
        },
        index=initial_index,
    )

    # Calculate the warmup start date
    try:
        warmup_start, _ = calculate_warmup_start_date(
            strategy_features=strategy_features or [],
            global_features=global_features,
            execution_timeframe=execution_timeframe,
            market_data=temp_df,
            backtest_start_date=start_ts,
        )

        warmup_ts = pd.Timestamp(warmup_start)
        # Generate the full data range including warmup
        full_index = pd.date_range(warmup_ts, end_ts, freq=freq_alias)
    except (ValueError, KeyError):
        # If warmup calculation fails (e.g., insufficient data), use a
        # conservative buffer. Most tests use 1h_ema_50, 1d_ema_50 which
        # need 50 bars at 1D = ~60 days
        warmup_ts = start_ts - pd.Timedelta(days=100)
        full_index = pd.date_range(warmup_ts, end_ts, freq=freq_alias)

    # Create the full DataFrame
    df = pd.DataFrame(
        {
            "open": ohlcv_values["open"],
            "high": ohlcv_values["high"],
            "low": ohlcv_values["low"],
            "close": ohlcv_values["close"],
            "volume": ohlcv_values["volume"],
        },
        index=full_index,
    )

    return df


def extend_test_data_for_warmup(
    df: pd.DataFrame,
    backtest_start: datetime,
    execution_timeframe: str = "1H",
    strategy_features: list[dict[str, Any]] | None = None,
    include_global_features: bool = True,
) -> pd.DataFrame:
    """Extend existing test DataFrame backwards to include warmup period.

    This is useful when you have existing test data but need to add warmup buffer.

    Args:
        df: Existing DataFrame with OHLCV data
        backtest_start: The desired backtest start date (should be in df.index)
        execution_timeframe: Execution timeframe for the backtest
        strategy_features: List of strategy feature definitions (optional)
        include_global_features: Whether to include global features

    Returns:
        Extended DataFrame with warmup period prepended
    """
    from pathlib import Path

    from trading_platform.backtester.warmup import calculate_warmup_start_date

    # Load global features if requested
    global_features: list[dict[str, Any]] = []
    if include_global_features:
        try:
            from trading_platform.core.feature_resolver import (
                resolve_global_features,
            )

            config_path = (
                Path(__file__).parent.parent / "config" / "features" / "global.yaml"
            )
            resolved = resolve_global_features(
                execution_timeframe, config_path=config_path
            )
            global_features = [
                {
                    "name": f.name,
                    "type": f.type,
                    "params": f.params,
                    "source": f.source,
                    **(
                        {}
                        if f.timeframe == execution_timeframe
                        else {"timeframe": f.timeframe}
                    ),
                }
                for f in resolved
            ]
        except Exception:
            pass

    # Calculate warmup start
    try:
        warmup_start, _ = calculate_warmup_start_date(
            strategy_features=strategy_features or [],
            global_features=global_features,
            execution_timeframe=execution_timeframe,
            market_data=df,
            backtest_start_date=pd.Timestamp(backtest_start),
        )
    except (ValueError, KeyError):
        # Conservative fallback (ensure enough history for weekly features)
        warmup_start = pd.Timestamp(backtest_start) - pd.Timedelta(days=730)

    warmup_ts = pd.Timestamp(warmup_start)

    # If data already extends before warmup_start, return as-is
    if df.index[0] <= warmup_ts:
        return df

    # Infer frequency from existing data
    freq = pd.infer_freq(pd.DatetimeIndex(df.index))
    if freq is None:
        freq = df.index[1] - df.index[0]

    # Create warmup bars by repeating the first bar's values
    freq_alias = freq.replace("H", "h") if isinstance(freq, str) else freq
    warmup_index = pd.date_range(
        warmup_ts, df.index[0], freq=freq_alias, inclusive="left"
    )

    if len(warmup_index) == 0:
        return df

    # Create warmup data with same values as first bar
    first_bar = df.iloc[0]
    warmup_df = pd.DataFrame(
        {col: first_bar[col] for col in df.columns}, index=warmup_index
    )

    # Concatenate warmup and original data
    extended_df = pd.concat([warmup_df, df])

    return extended_df


def get_empty_global_features_path() -> Any:
    """Get path to empty global features config for unit tests.

    Unit tests should use this to avoid loading production global features
    which require significant warmup data. This returns a path to an empty
    global features config file.

    Returns:
        Path to tests/fixtures/global_empty.yaml
    """
    from pathlib import Path

    return Path(__file__).parent / "fixtures" / "global_empty.yaml"
