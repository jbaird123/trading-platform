from __future__ import annotations

import logging
import math
from collections.abc import Mapping as MappingABC
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator, cast

import numpy as np
import pandas as pd

from trading_platform.backtester.context import (
    build_context_snapshot,
    normalize_global_feature_key,
    realign_context_snapshot,
)
from trading_platform.core import paths
from trading_platform.core.config import RunConfig
from trading_platform.core.global_features_cache import load_cached_global_features
from trading_platform.core.policy import TradingWindowPolicy
from trading_platform.core.signal import Signal
from trading_platform.core.types import BarData, SignalCommand
from trading_platform.core.utils import normalize_symbol
from trading_platform.data.timeframe_aliases import canonicalize_column_name
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.portfolio.trade import Trade
from trading_platform.regime_market_manager.gating import (
    GatingDecision,
    ProfitabilityGatingEngine,
)
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy

"""Backtester core loop with optional exposure capture.

When `return_exposure` is True, returns `(trades, exposure_curve)`; otherwise
returns just `trades`.
"""

logger = logging.getLogger(__name__)

SimulationReturn = (
    list[Trade]
    | tuple[list[Trade], list[tuple[datetime, float]]]
    | tuple[list[Trade], list[tuple[datetime, float]], list[dict[str, Any]]]
)


def _enrich_trades_with_post_exit_analysis(
    trades: list[Trade],
    market_data: pd.DataFrame,
    horizons: list[int],
) -> None:
    """
    Enrich trades with realistic post-exit simulations.

    For each trade, simulates holding the position for N additional bars
    after exit, accounting for stop-loss and take-profit triggers.
    This provides realistic "what-if" analysis instead of misleading
    raw MFE/MAE values.

    Args:
        trades: List of Trade objects to enrich (modified in-place)
        market_data: DataFrame with OHLCV data indexed by datetime
        horizons: List of bar counts to simulate (e.g., [10, 20, 50])
    """
    from trading_platform.backtester.analysis.exit_simulation import (
        run_single_trade_simulation,
    )
    from trading_platform.reporting.models.exit_analysis import (
        PostExitAnalysis,
    )

    if not trades or not horizons:
        return

    # Build a datetime index lookup
    dt_index = market_data.index.tolist()

    for trade in trades:
        exit_time = trade.exit_time
        try:
            exit_idx = dt_index.index(exit_time)
        except ValueError:
            # Exit time not found in data - skip this trade
            continue

        # Get the slice of data after exit for simulations
        post_exit_data = market_data.iloc[exit_idx + 1 :]

        if len(post_exit_data) == 0:
            # No data available after exit - create empty PostExitAnalysis
            post_exit_analysis = PostExitAnalysis(simulated_holds=[])
            object.__setattr__(trade, "post_exit_analysis", post_exit_analysis)
            continue

        # Run simulations for each horizon
        simulated_holds = []
        for horizon in horizons:
            simulation = run_single_trade_simulation(
                trade=trade, price_data=post_exit_data, hold_bars=horizon
            )
            simulated_holds.append(simulation)

        # Create PostExitAnalysis object
        post_exit_analysis = PostExitAnalysis(simulated_holds=simulated_holds)

        # Mutate the trade object by creating a new one with updated data
        # Since Trade is frozen, we need to use object.__setattr__
        object.__setattr__(trade, "post_exit_analysis", post_exit_analysis)


def resolve_instrument_symbol(instrument: Any) -> str:
    """
    Resolve and normalize the instrument symbol from various input formats.

    Args:
        instrument: Can be None, a dict with 'symbol' key, or object with
                   'symbol' attribute

    Returns:
        str: Normalized symbol in canonical format

    Raises:
        ValueError: If instrument is None, missing symbol, or has empty symbol
    """
    if instrument is None:
        raise ValueError("instrument with symbol is required")

    # Handle dict format (config snapshot)
    if isinstance(instrument, dict):
        symbol = instrument.get("symbol", "")
    # Handle object with symbol attribute
    elif hasattr(instrument, "symbol"):
        symbol = getattr(instrument, "symbol", "")
    else:
        raise ValueError("instrument with symbol is required")

    # Check for empty or whitespace-only symbol
    if not symbol or not str(symbol).strip():
        raise ValueError("instrument with symbol is required")

    result: str = normalize_symbol(str(symbol))
    return result


def _execute_backtest_loop(
    market_data: pd.DataFrame,
    signals: pd.Series,
    strategy: CompiledStrategy,
    config: RunConfig,
    rem: RiskExitManager,
    rmm_context: dict[datetime, dict[str, Any]] | None = None,
    return_exposure: bool = False,
    return_skips: bool = False,
    data_handler: Any = None,
    global_features_config_path: Path | str | None = None,
    global_feature_defs: list[dict[str, Any]] | None = None,
    gating_engine: ProfitabilityGatingEngine | None = None,
    gating_metadata: dict[str, Any] | None = None,
    cache_root_override: Path | None = None,
) -> SimulationReturn:
    """INTERNAL: Bar-by-bar backtest simulation engine.

    DO NOT CALL DIRECTLY. Use orchestrator.run_backtest() instead.

    This is the low-level simulation engine that executes trades bar-by-bar.
    All backtest entry points should go through the orchestrator, which handles
    data loading, warmup calculation, and validation before calling this function.

    Args:
        market_data: DataFrame with OHLCV data.
        signals: Series with 'long', 'short', and 'flat' signals.
        config: The unified run configuration object.
        rem: The Risk & Exit Manager instance.
        return_exposure: If True, returns the exposure curve.
        return_skips: If True, returns a list of skipped trades.
        data_handler: Optional DataHandler for 1-minute resolution zoom.

    Returns:
        A list of completed Trade objects, and optionally other artifacts.
    """
    # --- Input validation (fail fast) ---
    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols.difference(set(market_data.columns))
    if missing:
        raise ValueError(f"market_data missing required columns: {sorted(missing)}")

    if len(signals) != len(market_data):
        msg = (
            f"signals length ({len(signals)}) must equal "
            f"market_data length ({len(market_data)})"
        )
        raise ValueError(msg)

    # Extract commands from Signal objects for validation
    commands = []
    for sig in signals:
        if isinstance(sig, Signal):
            commands.append(sig.command)
        else:
            commands.append(sig)

    allowed = {"enter_long", "enter_short", "exit_long", "exit_short", "None", "nan"}
    invalid_values = set(pd.Series(commands).astype(str).unique()) - allowed
    if invalid_values:
        raise ValueError(
            f"signals contain invalid command values: {sorted(invalid_values)}"
        )

    if market_data["close"].isna().any():
        first_bad = market_data[market_data["close"].isna()].index[0]
        raise ValueError(f"market_data.close has NaNs; first at index: {first_bad}")

    symbol = resolve_instrument_symbol(config.instrument)
    strategy_archetype = (gating_metadata or {}).get(
        "strategy_archetype"
    ) or "trend_following"
    instrument_timeframe = (gating_metadata or {}).get("instrument_timeframe")
    if instrument_timeframe is None:
        instrument = config.instrument
        if isinstance(instrument, dict):
            instrument_timeframe = instrument.get("timeframe")
        else:
            instrument_timeframe = getattr(instrument, "timeframe", None)

    def _timeframe_to_minutes(timeframe: str) -> int:
        """Convert timeframe string (e.g., '1H', '15min') to minutes."""
        normalized = str(timeframe).strip()
        candidates = (normalized.lower(), normalized)
        for candidate in candidates:
            try:
                delta = pd.to_timedelta(candidate)
            except ValueError:
                continue
            minutes = int(delta.total_seconds() // 60)
            if minutes > 0:
                return minutes
        raise ValueError(f"Unsupported timeframe string: {timeframe!r}")

    def _first_valid_timestamp(
        df_obj: pd.DataFrame | None, feature_names: list[str]
    ) -> pd.Timestamp | None:
        """Return the first timestamp where every feature is non-null."""
        if df_obj is None or df_obj.empty:
            return None
        if not feature_names:
            return pd.Timestamp(df_obj.index[0])

        present = [name for name in feature_names if name in df_obj.columns]
        if not present:
            return pd.Timestamp(df_obj.index[0])

        mask = df_obj[present].notna().all(axis=1)
        valid_index = df_obj.index[mask]
        if len(valid_index) == 0:
            return None
        return pd.Timestamp(valid_index[0])

    def _resolve_symbol_from_config() -> str | None:
        instrument_cfg = getattr(config, "instrument", None)
        symbol_val = None
        if isinstance(instrument_cfg, dict):
            symbol_val = instrument_cfg.get("symbol")
        elif instrument_cfg is not None:
            symbol_val = getattr(instrument_cfg, "symbol", None)
        if symbol_val:
            return str(symbol_val)

        data_req_cfg = getattr(config, "data_request", None) or {}
        symbol_val = data_req_cfg.get("symbol")
        if symbol_val:
            return str(symbol_val)
        return None

    # Compute global features from config/features/global.yaml
    data_with_global_features = market_data
    global_features_list: list[dict[str, Any]] = []
    global_valid_start: pd.Timestamp | None = None
    global_validation_error: str | None = None
    global_feature_timeframes: dict[str, int] = {}
    guard_feature_names: set[str] = set()
    guard_feature_valid_start: dict[str, pd.Timestamp | None] = {}
    execution_tf_minutes: int | None = None
    try:
        from trading_platform.strategy.features import compute_features

        instrument_cfg = config.instrument or {}
        execution_timeframe = instrument_cfg.get("timeframe", "1H")
        try:
            execution_tf_minutes = _timeframe_to_minutes(execution_timeframe)
        except ValueError as exc:  # pragma: no cover - validated upstream
            raise ValueError(
                "Unsupported execution timeframe in instrument config: "
                f"{execution_timeframe!r}"
            ) from exc

        bar_close_timedelta = (
            pd.to_timedelta(f"{execution_tf_minutes}min")
            if execution_tf_minutes
            else pd.Timedelta(0)
        )

        def _decision_timestamp(ts: datetime) -> datetime:
            return ts

        def _decision_index_for(idx: pd.Index) -> pd.DatetimeIndex | None:
            if not isinstance(idx, pd.DatetimeIndex):
                return None
            return idx

        def _shift_to_decision_index(
            obj: pd.DataFrame | pd.Series,
        ) -> pd.DataFrame | pd.Series:
            if bar_close_timedelta == pd.Timedelta(0):
                return obj
            if not isinstance(obj.index, pd.DatetimeIndex):
                return obj
            shifted = obj.copy()
            shifted.index = obj.index + cast(pd.Timedelta, bar_close_timedelta)
            return shifted

        data_with_global_features = market_data
        decision_feature_frame: pd.DataFrame | None = None
        decision_feature_frame_source: pd.DataFrame | None = None
        decision_index = _decision_index_for(market_data.index)

        if global_feature_defs is not None:
            global_features_list.extend(global_feature_defs)
        elif global_features_config_path is not None:
            from trading_platform.core.feature_resolver import resolve_global_features

            resolved_features = resolve_global_features(
                execution_timeframe, config_path=global_features_config_path
            )
            for resolved in resolved_features:
                feature_dict: dict[str, Any] = {
                    "name": resolved.name,
                    "type": resolved.type,
                    "params": resolved.params,
                    "source": resolved.source,
                }
                feature_tf = resolved.timeframe or execution_timeframe
                if resolved.timeframe and resolved.timeframe != execution_timeframe:
                    feature_dict["timeframe"] = resolved.timeframe
                global_features_list.append(feature_dict)

        for feature_dict in list(global_features_list):
            name_str = str(feature_dict.get("name"))
            if not name_str:
                continue
            feature_tf = feature_dict.get("timeframe") or execution_timeframe
            try:
                global_feature_timeframes[name_str] = _timeframe_to_minutes(feature_tf)
            except ValueError as exc:
                raise ValueError(
                    "Unsupported timeframe for global feature "
                    f"{name_str!r}: {feature_tf!r}"
                ) from exc

        global_names: list[str] = []
        if global_features_list:
            requested_names = [
                str(feature.get("name"))
                for feature in global_features_list
                if isinstance(feature.get("name"), str)
            ]
            cache_loaded = False
            if requested_names and global_features_config_path is not None:
                symbol_for_cache = _resolve_symbol_from_config()
                config_path = Path(global_features_config_path)
                cache_root = (
                    Path(cache_root_override).expanduser().resolve()
                    if cache_root_override is not None
                    else paths.GLOBAL_FEATURE_CACHE_DIR
                )
                if symbol_for_cache:
                    cache_result = load_cached_global_features(
                        symbol=symbol_for_cache,
                        cache_root=cache_root,
                        config_path=config_path,
                        timeframe=execution_timeframe,
                        feature_names=requested_names,
                    )
                    if cache_result is not None:
                        cache_frame, mapping = cache_result
                        required = set(requested_names)
                        if required.issubset(mapping.keys()):
                            cache_index = cache_frame.index
                            market_index = market_data.index
                            if isinstance(cache_index, pd.DatetimeIndex) and isinstance(
                                market_index, pd.DatetimeIndex
                            ):
                                if (
                                    cache_index.tz is not None
                                    and market_index.tz is None
                                ):
                                    cache_frame.index = cache_index.tz_convert(
                                        "UTC"
                                    ).tz_localize(None)
                                elif (
                                    cache_index.tz is None
                                    and market_index.tz is not None
                                ):
                                    cache_frame.index = cache_index.tz_localize(
                                        market_index.tz
                                    )
                            aligned_to_close = False
                            if (
                                bar_close_timedelta != pd.Timedelta(0)
                                and isinstance(cache_frame.index, pd.DatetimeIndex)
                                and isinstance(market_data.index, pd.DatetimeIndex)
                                and len(cache_frame.index) > 0
                                and len(market_data.index) > 0
                            ):
                                market_start = market_data.index[0]
                                overlapping = cache_frame.index[
                                    cache_frame.index >= market_start
                                ]
                                cache_start = (
                                    overlapping[0]
                                    if len(overlapping) > 0
                                    else cache_frame.index[0]
                                )
                                diff = cache_start - market_start
                                aligned_to_close = diff == cast(
                                    pd.Timedelta, bar_close_timedelta
                                ) or diff == pd.Timedelta(0)

                            join_frame = cache_frame.copy()
                            if aligned_to_close:
                                join_frame.index = cache_frame.index - cast(
                                    pd.Timedelta, bar_close_timedelta
                                )

                            data_with_global_features = market_data.join(
                                join_frame, how="left"
                            )
                            decision_feature_frame = (
                                cast(
                                    pd.DataFrame,
                                    _shift_to_decision_index(cache_frame.copy()),
                                )
                                if aligned_to_close
                                else cache_frame.copy()
                            )
                            decision_feature_frame_source = cache_frame.copy()
                            cache_loaded = True

                            # DEBUG: Check first few rows
                            if (
                                "15min_ema_50" in cache_frame.columns
                                and len(market_data) > 5
                            ):
                                test_idx = 3
                                test_ts = market_data.index[test_idx]
                                decision_test_ts = (
                                    _decision_timestamp(cast(datetime, test_ts))
                                    if isinstance(test_ts, pd.Timestamp)
                                    else _decision_timestamp(
                                        cast(datetime, market_data.index[test_idx])
                                    )
                                )
                                if decision_test_ts in cache_frame.index:
                                    cache_val = cache_frame.loc[decision_test_ts][
                                        "15min_ema_50"
                                    ]
                                    joined_val = data_with_global_features.loc[
                                        market_data.index[test_idx]
                                    ]["15min_ema_50"]
                                    print(
                                        "DEBUG: "
                                        f"At index {test_idx} ({test_ts}) "
                                        f"decision {decision_test_ts}:"
                                    )
                                    cache_msg = "  Cache value: " f"{cache_val:.8f}"
                                    joined_msg = "  Joined value: " f"{joined_val:.8f}"
                                    print(cache_msg)
                                    print(joined_msg)
                                    is_match = abs(cache_val - joined_val) < 1e-10
                                    print(f"  Match: {is_match}")

                            msg = (
                                f"Global feature cache HIT ("
                                f"{execution_timeframe} timeframe): "
                                f"{len(cache_frame.columns)} columns from {cache_root}"
                            )
                            logger.info(msg)
                            print(msg)
            if not cache_loaded:
                miss_msg = (
                    f"Global feature cache MISS ("
                    f"{execution_timeframe} timeframe): "
                    f"computing {len(global_features_list)} features"
                )
                logger.info(miss_msg)
                print(miss_msg)
                data_with_global_features = compute_features(
                    market_data, global_features_list, strategy_parameters={}
                )
                decision_feature_frame = data_with_global_features.copy()
                decision_feature_frame_source = decision_feature_frame.copy()
                logger.info(
                    f"Computed {len(global_features_list)} global features: "
                    f"{[f['name'] for f in global_features_list]}"
                )

            for feature in global_features_list:
                raw_name = feature.get("name")
                if not isinstance(raw_name, str):
                    continue
                global_names.append(raw_name)

                derived_columns = [
                    column
                    for column in data_with_global_features.columns
                    if column == raw_name or column.startswith(f"{raw_name}_")
                ]

                minutes = global_feature_timeframes.get(raw_name)
                for column in derived_columns:
                    if column not in global_feature_timeframes and minutes is not None:
                        global_feature_timeframes[column] = minutes

            decision_valid_start: pd.Timestamp | None = None
            source_view = (
                decision_feature_frame_source
                if decision_feature_frame_source is not None
                else decision_feature_frame
            )
            if source_view is not None:
                trimmed_view = source_view
                if (
                    isinstance(trimmed_view.index, pd.DatetimeIndex)
                    and len(market_data.index) > 0
                ):
                    trimmed_view = trimmed_view.loc[
                        trimmed_view.index >= market_data.index[0]
                    ]
                decision_valid_start = _first_valid_timestamp(
                    trimmed_view, global_names
                )
            global_valid_start = decision_valid_start
            if global_valid_start is not None and bar_close_timedelta != pd.Timedelta(
                0
            ):
                adjusted = global_valid_start - cast(pd.Timedelta, bar_close_timedelta)
                earliest = (
                    market_data.index[0]
                    if isinstance(market_data.index, pd.DatetimeIndex)
                    else adjusted
                )
                global_valid_start = max(adjusted, earliest)
            if global_valid_start is None:
                global_validation_error = (
                    "Insufficient warmup: Global features never fully initialize. "
                    "Load additional history before the backtest start."
                )

    except FileNotFoundError:
        logger.info("No global.yaml found - proceeding without global features")
    except ValueError:
        raise
    except Exception as exc:
        logger.warning(f"Failed to load global features: {exc}")

    if global_validation_error is not None:
        raise ValueError(global_validation_error)

    strategy_valid_start: pd.Timestamp | None = None
    strategy_features = strategy.features or []
    if strategy._feature_df is not None and len(strategy._feature_df) > 0:
        strategy_names = [
            str(feature.get("name"))
            for feature in strategy_features
            if isinstance(feature.get("name"), str)
        ]
        strategy_valid_start = _first_valid_timestamp(
            strategy._feature_df, strategy_names
        )
        if strategy_names and strategy_valid_start is None:
            raise ValueError(
                "Insufficient warmup: Strategy features never fully initialize. "
                "Load additional history or reduce indicator lookback."
            )

    if len(market_data) > 0:
        run_start_candidates: list[pd.Timestamp] = [market_data.index[0]]
        if global_valid_start is not None:
            run_start_candidates.append(global_valid_start)
        if strategy_valid_start is not None:
            run_start_candidates.append(strategy_valid_start)

        run_start = max(run_start_candidates)

        def _trim_indexed(data_obj: pd.DataFrame | pd.Series) -> Any:
            return data_obj.loc[data_obj.index >= run_start]

        market_data = _trim_indexed(market_data)
        signals = _trim_indexed(signals)

        if len(market_data) == 0:
            raise ValueError(
                "Insufficient warmup: No data remains after removing " "warmup bars."
            )

        if isinstance(signals, pd.Series) and len(signals) == 0:
            raise ValueError(
                "Insufficient warmup: Signals are empty after removing " "warmup bars."
            )

        if strategy._feature_df is not None and len(strategy._feature_df) > 0:
            trimmed_features = _trim_indexed(strategy._feature_df)
            object.__setattr__(strategy, "_feature_df", trimmed_features)

        if (
            data_with_global_features is not market_data
            and len(data_with_global_features) > 0
        ):
            data_with_global_features = _trim_indexed(data_with_global_features)
            # DEBUG: Verify indices match after trim
            if len(market_data) != len(data_with_global_features):
                print("WARNING: Length mismatch after trim!")
                print(f"  market_data: {len(market_data)} rows")
                feature_rows_msg = (
                    "  data_with_global_features: "
                    f"{len(data_with_global_features)} rows"
                )
                print(feature_rows_msg)
            elif not market_data.index.equals(data_with_global_features.index):
                print("WARNING: Index mismatch after trim!")
                print(f"  First market_data: {market_data.index[0]}")
                first_feature_msg = (
                    "  First data_with_global_features: "
                    f"{data_with_global_features.index[0]}"
                )
                print(first_feature_msg)
    decision_index = _decision_index_for(market_data.index)
    if (
        decision_feature_frame_source is not None
        and decision_index is not None
        and isinstance(decision_feature_frame_source.index, pd.DatetimeIndex)
    ):
        decision_feature_frame = decision_feature_frame_source.reindex(
            decision_index, method=None
        )
        added_mask = ~decision_index.isin(decision_feature_frame_source.index)
        if added_mask.any():
            filled = decision_feature_frame_source.reindex(
                decision_index, method="ffill"
            )
            decision_feature_frame.loc[added_mask] = filled.loc[added_mask]
        aligned_valid_start = _first_valid_timestamp(
            decision_feature_frame, global_names
        )
        if aligned_valid_start is not None:
            global_valid_start = aligned_valid_start
    warmup_threshold = 0

    base_columns = set(market_data.columns)
    global_feature_columns: list[str] = []
    if any(col not in base_columns for col in data_with_global_features.columns):
        for feature in global_features_list:
            raw_name = feature.get("name")
            if not isinstance(raw_name, str):
                continue
            canonical_name = canonicalize_column_name(raw_name)
            candidate_columns: list[str] = []
            for column in data_with_global_features.columns:
                if column == raw_name or column.startswith(f"{raw_name}_"):
                    candidate_columns.append(column)
                elif canonical_name != raw_name and (
                    column == canonical_name or column.startswith(f"{canonical_name}_")
                ):
                    candidate_columns.append(column)

            for column in candidate_columns:
                if column not in global_feature_columns:
                    global_feature_columns.append(column)
                feature_minutes = (
                    global_feature_timeframes.get(column)
                    if execution_tf_minutes is not None
                    else None
                )
                if (
                    feature_minutes is not None
                    and execution_tf_minutes is not None
                    and feature_minutes >= execution_tf_minutes
                ):
                    guard_feature_names.add(column)
                    source_frame = (
                        decision_feature_frame_source
                        if decision_feature_frame_source is not None
                        else data_with_global_features
                    )
                    guard_feature_valid_start[column] = cast(
                        pd.Timestamp | None,
                        source_frame[column].first_valid_index()
                        if column in source_frame.columns
                        else None,
                    )

    if guard_feature_names:
        aligned_guard = data_with_global_features.loc[
            market_data.index, global_feature_columns
        ]
        for feature_name in guard_feature_names:
            if feature_name not in aligned_guard.columns:
                continue
            series = aligned_guard.loc[:, feature_name]
            valid_start = guard_feature_valid_start.get(feature_name)
            if valid_start is not None:
                series = series.loc[series.index >= valid_start]
            first_valid = series.first_valid_index()
            if first_valid is not None:
                series = series.loc[series.index >= first_valid]
            bad = series[series.isna()]
            if not bad.empty:
                first_bad = bad.index[0]
                raise ValueError(
                    "Global feature "
                    f"{feature_name!r} is NaN at {first_bad}. "
                    "Features at or above the execution timeframe "
                    "must be fully populated."
                )

    # Keep global features as DataFrame for direct timestamp lookups
    global_feature_df: pd.DataFrame | None = None
    global_feature_normalized_keys: list[str] = []
    if global_feature_columns and decision_feature_frame is not None:
        global_feature_df = decision_feature_frame.loc[:, global_feature_columns]
        global_feature_normalized_keys = [
            normalize_global_feature_key(column) for column in global_feature_columns
        ]

    # Use the complete instrument definition from config
    # (RunConfig validator ensures it has all required fields)
    instrument_dict: dict[str, Any] = config.instrument or {}

    portfolio = PortfolioManager(
        base_currency="USD",
        initial_cash=config.initial_cash,
        instrument=instrument_dict,
        cost_model=config.cost_model,
    )

    policy = TradingWindowPolicy.from_config(
        blackout_utc=config.blackout_utc, blackout_events=config.blackout_events
    )

    exposure_curve: list[tuple[datetime, float]] = []
    skipped: list[dict[str, Any]] = []
    limits = config.pm_limits or {"max_open_long": 1, "max_open_short": 1}
    # Use the provided RiskExitManager instance; do not override it here.

    def _safe_float(val: Any, default: float = 0.0) -> float:
        if isinstance(val, (int, float)):
            if isinstance(val, float) and math.isnan(val):
                return default
            return float(val)
        return default

    def _safe_int(val: Any, default: int = 0) -> int:
        if isinstance(val, (int, float)):
            if isinstance(val, float) and math.isnan(val):
                return default
            return int(val)
        return default

    def _build_regime_data(ctx: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(ctx, dict):
            return None

        label = ctx.get("label")
        raw_label = ctx.get("raw_label", label)
        if not isinstance(label, str):
            label = "unknown"
        if not isinstance(raw_label, str):
            raw_label = label

        hyst_src = ctx.get("hysteresis")
        bars = _safe_int(
            hyst_src.get("bars_in_state")
            if isinstance(hyst_src, dict)
            else ctx.get("bars_in_state")
        )
        cooldown = _safe_int(
            hyst_src.get("cooldown_remaining")
            if isinstance(hyst_src, dict)
            else ctx.get("cooldown_remaining")
        )

        regime_data = {
            "label": label,
            "raw_label": raw_label,
            "confidence": _safe_float(ctx.get("confidence")),
            "raw_confidence": _safe_float(
                ctx.get("raw_confidence"), _safe_float(ctx.get("confidence"))
            ),
            "allowed_sides": list(ctx.get("allowed_sides") or []),
            "policy": ctx.get("policy", {}),
            "features": ctx.get("features", {}),
            "timeframe": ctx.get("timeframe", "daily"),
            "hysteresis": {
                "bars_in_state": bars,
                "cooldown_remaining": cooldown,
            },
        }
        return regime_data

    def _fmt_ts(val: Any) -> str:
        return val.isoformat() if isinstance(val, datetime) else str(val)

    # Pending actions for next_bar_open execution model
    pending_exit: dict[str, Any] | None = None
    pending_entry: dict[str, Any] | None = None
    last_context_at_exit: dict[str, Any] | None = None

    use_fast_rows = True
    try:
        market_bar_factory = _make_bar_factory(market_data)
        if data_with_global_features is market_data:
            feature_bar_factory = market_bar_factory
        else:
            feature_bar_factory = _make_bar_factory(data_with_global_features)
    except Exception:
        # Fallback to Pandas rows if conversion fails (e.g., sparse frames)
        use_fast_rows = False

    gating_total = 0
    gating_allowed = 0

    for i in range(len(market_data)):
        signal = signals.iat[i] if hasattr(signals, "iat") else signals.iloc[i]
        current_bar: BarData
        prior_bar: BarData | None
        feature_bar: BarData
        feature_prior_bar: BarData | None

        if use_fast_rows:
            current_bar = market_bar_factory(i)
            prior_bar = market_bar_factory(i - 1) if i > 0 else None
            if feature_bar_factory is market_bar_factory:
                feature_bar = current_bar
                feature_prior_bar = prior_bar
            else:
                feature_bar = feature_bar_factory(i)
                feature_prior_bar = feature_bar_factory(i - 1) if i > 0 else None
        else:
            current_bar = market_data.iloc[i]
            prior_bar = market_data.iloc[i - 1] if i > 0 else None
            if data_with_global_features is market_data:
                feature_bar = current_bar
                feature_prior_bar = prior_bar
            else:
                feature_bar = data_with_global_features.iloc[i]
                feature_prior_bar = (
                    data_with_global_features.iloc[i - 1] if i > 0 else None
                )

        bar_close_ts = cast(datetime, current_bar.name)
        decision_ts = _decision_timestamp(bar_close_ts)

        # === EXECUTION PHASE: Execute pending actions ===
        # Execute pending exit from previous bar (next_bar_open model)
        if pending_exit is not None:
            exit_decision_ts = cast(
                datetime,
                pending_exit.get("decision_time", decision_ts),
            )
            exit_context = realign_context_snapshot(
                base_context=pending_exit.get("context"),
                timestamp=exit_decision_ts,
                rmm_context=rmm_context,
                regime_builder=_build_regime_data,
                global_feature_df=global_feature_df,
                global_feature_normalized_keys=global_feature_normalized_keys,
                global_feature_timeframes=global_feature_timeframes,
                execution_tf_minutes=execution_tf_minutes,
            )
            portfolio.close_position(
                exit_price=current_bar["open"],
                exit_time=decision_ts,
                exit_reason=pending_exit["reason"],
                context_at_exit=exit_context,
            )
            last_context_at_exit = exit_context
            # Handle flip: if exit was for opposite signal, open entry window
            # and immediately execute entry at same bar open
            if "entry_side" in pending_exit:
                portfolio.complete_pending_exit_and_open_entry_window(
                    pending_exit["entry_side"], i
                )
                # Create pending_entry for immediate execution below
                # (will be executed right after this block)
                pending_entry = {
                    "symbol": symbol,
                    "side": pending_exit["entry_side"],
                    "size": float(config.position_size),
                    "instrument": instrument_dict,
                    "context": exit_context,
                    "decision_time": exit_decision_ts,
                }
            pending_exit = None

        # Execute pending entry from previous bar (next_bar_open model)
        if pending_entry is not None:
            entry_decision_ts = cast(
                datetime,
                pending_entry.get("decision_time", decision_ts),
            )
            entry_context = realign_context_snapshot(
                base_context=pending_entry.get("context"),
                timestamp=entry_decision_ts,
                rmm_context=rmm_context,
                regime_builder=_build_regime_data,
                global_feature_df=global_feature_df,
                global_feature_normalized_keys=global_feature_normalized_keys,
                global_feature_timeframes=global_feature_timeframes,
                execution_tf_minutes=execution_tf_minutes,
            )

            # Calculate initial stop loss price for r_multiple calculation
            entry_price = current_bar["open"]
            initial_risk_ccy = None
            stop_price = None
            tp_price = None
            if rem is not None:
                signal_ctx = entry_context.get("strategy_features", {})
                stop_price = rem.calculate_initial_stop_price(
                    entry_price=entry_price,
                    side=pending_entry["side"],
                    entry_bar=feature_bar,
                    signal_context=signal_ctx,
                    prior_bar=feature_prior_bar or feature_bar,
                )
                tp_price = rem.calculate_initial_take_profit_price(
                    entry_price=entry_price,
                    side=pending_entry["side"],
                    entry_bar=feature_bar,
                    signal_context=signal_ctx,
                    prior_bar=feature_prior_bar or feature_bar,
                )
                if stop_price is not None:
                    # initial_risk_ccy = distance * size
                    initial_risk_ccy = (
                        abs(entry_price - stop_price) * pending_entry["size"]
                    )

            portfolio.create_new_position(
                symbol=pending_entry["symbol"],
                side=pending_entry["side"],
                entry_price=entry_price,
                size=pending_entry["size"],
                entry_time=decision_ts,
                instrument=pending_entry["instrument"],
                context_at_entry=entry_context,
                initial_risk_ccy=initial_risk_ccy,
                stop_loss=stop_price,
                take_profit=tp_price,
            )
            # Mark that we've entered on this entry window
            portfolio._entry_windows[pending_entry["side"]] = (
                portfolio._entry_windows[pending_entry["side"]][0],
                i,
            )
            pending_entry = None

        # Extract command and context from Signal object (or use legacy format)
        strategy_context = strategy.get_context(i)
        command: SignalCommand | None
        if isinstance(signal, Signal):
            command = cast(SignalCommand | None, signal.command)
            # Merge signal context with strategy context
            strategy_feature_context = {
                **strategy_context,
                **signal.context,
            }
        else:
            # Legacy format: signal is just a command string
            command = cast(SignalCommand | None, signal)
            strategy_feature_context = strategy_context

        is_no_command = False
        if command is None:
            is_no_command = True
        elif isinstance(command, str):
            lowered = command.lower()
            if lowered in {"none", "nan"}:
                command = None
                is_no_command = True

        need_context = bool(portfolio.current_position) or not is_no_command
        context: dict[str, Any] | None = None
        if need_context:
            context = build_context_snapshot(
                timestamp=decision_ts,
                strategy_context=strategy_feature_context,
                rmm_context=rmm_context,
                regime_builder=_build_regime_data,
                global_feature_df=global_feature_df,
                global_feature_normalized_keys=global_feature_normalized_keys,
                global_feature_timeframes=global_feature_timeframes,
                execution_tf_minutes=execution_tf_minutes,
            )
            last_context_at_exit = context

        gating_decision: GatingDecision | None = None
        if gating_engine and command in ["enter_long", "enter_short"]:
            side = "long" if command == "enter_long" else "short"
            tf_value = instrument_timeframe
            if tf_value is None and isinstance(config.instrument, dict):
                tf_value = config.instrument.get("timeframe")
            if context is None:
                context = {
                    "strategy_features": strategy_feature_context,
                    "global_features": {},
                }
            entry_price_gate = float(current_bar["close"])
            risk_ctx = context.setdefault("risk", {})
            risk_ctx["entry_price"] = entry_price_gate
            stop_price_gate = None
            tp_price_gate = None
            if rem is not None:
                stop_price_gate = rem.calculate_initial_stop_price(
                    entry_price=entry_price_gate,
                    side=side,
                    entry_bar=feature_bar,
                    signal_context=context.get("strategy_features", {}),
                    prior_bar=feature_prior_bar or feature_bar,
                )
                tp_price_gate = rem.calculate_initial_take_profit_price(
                    entry_price=entry_price_gate,
                    side=side,
                    entry_bar=feature_bar,
                    signal_context=context.get("strategy_features", {}),
                    prior_bar=feature_prior_bar or feature_bar,
                )
            risk_ctx["initial_stop_loss_price"] = stop_price_gate
            if tp_price_gate is not None:
                risk_ctx["initial_take_profit_price"] = tp_price_gate

            gating_total += 1
            gating_decision = gating_engine.should_allow(
                timeframe=str(tf_value or "1H"),
                archetype=strategy_archetype,
                side=side,
                symbol=symbol,
                entry_time=decision_ts,
                context=context,
            )
            context["gating"] = gating_decision.as_dict()
            if not gating_decision.allowed:
                if return_skips:
                    skipped.append(
                        {
                            "entry_time": _fmt_ts(decision_ts),
                            "symbol": symbol,
                            "side": side,
                            "size": float(config.position_size),
                            "skip_reason": "profitability_gate",
                            "entry_index": i,
                            "entry_price": float(current_bar["close"]),
                            "notes": gating_decision.reason,
                            "gating": gating_decision.as_dict(),
                        }
                    )
                continue
            gating_allowed += 1
        elif gating_engine and context is not None:
            context["gating"] = None

        # === REM EXIT PHASE: Check risk-based exits ===
        # REM exits (stop-loss, take-profit) are ALWAYS executed immediately
        # at the intra-bar price when hit, regardless of execution_model.
        # This is realistic behavior - protective orders execute intra-bar.
        # The execution_model setting only applies to signal-based entries/exits.
        if portfolio.current_position and rem is not None:
            rem_kwargs = {}
            if execution_tf_minutes is not None:
                rem_kwargs["bar_minutes"] = execution_tf_minutes
            try:
                rem_result = rem.check_exits_intrabar(
                    portfolio.current_position,
                    feature_bar,
                    data_handler=data_handler,
                    prior_bar=feature_prior_bar or feature_bar,
                    **rem_kwargs,
                )
            except TypeError:
                rem_result = rem.check_exits_intrabar(
                    portfolio.current_position,
                    feature_bar,
                    data_handler=data_handler,
                    prior_bar=feature_prior_bar or feature_bar,
                )

            if rem_result is not None and rem_result["action"] == "should_close":
                # ALWAYS execute REM exits immediately at intra-bar price
                # Stop-loss and take-profit orders don't wait for bar close
                portfolio.close_position(
                    exit_price=rem_result["exit_price"],
                    exit_time=decision_ts,
                    exit_reason=rem_result["reason"],
                    context_at_exit=context,
                )
                if return_exposure:
                    exposure_curve.append((decision_ts, 0.0))
                # Don't continue - allow entry signals to be processed on same bar
                # after stop loss exit (realistic: stop hits early in bar, signal
                # triggers later in bar)

        # === STRATEGY COMMAND PHASE: Process strategy signals ===
        result = portfolio.process_command(
            command=cast(SignalCommand, command),
            bar_index=i,
            warmup_threshold=warmup_threshold,
            entry_window_bars=config.entry_window_bars,
            allow_flip=config.allow_flip_on_bar,
            min_hold_bars=config.min_hold_bars,
            current_bar=current_bar,
            context=context,
        )

        # Handle should_close descriptor (signal-based exit)
        if result["action"] == "should_close":
            if config.execution_model == "current_bar_close":
                # Immediate execution at bar close
                portfolio.close_position(
                    exit_price=current_bar["close"],
                    exit_time=decision_ts,
                    exit_reason=result["reason"],
                    context_at_exit=context,
                )
                if return_exposure:
                    exposure_curve.append((decision_ts, 0.0))

                # For flips: open entry window for opposite side (don't continue)
                # This allows the entry logic below to process the flip on same bar
                if "entry_side" in result:
                    portfolio.complete_pending_exit_and_open_entry_window(
                        result["entry_side"], i
                    )
                    # Update result to reflect the open entry window
                    result = {
                        "action": "open_entry_window",
                        "side": result["entry_side"],
                        "bar_index": i,
                    }
                    # Don't continue - fall through to entry logic
                else:
                    # Not a flip - just a regular exit, skip rest of bar
                    continue
            else:  # next_bar_open
                # Defer execution to next bar's open
                pending_exit = {
                    "reason": result["reason"],
                    "context": context,
                    "decision_time": decision_ts,
                }
                # For flip: include entry_side and bar_index
                if "entry_side" in result:
                    pending_exit["entry_side"] = result["entry_side"]
                    pending_exit["bar_index"] = result.get("bar_index", i)
                # Don't continue - allow processing to continue for flip

        # Update position metrics if we have an open position
        if portfolio.current_position:
            portfolio._update_position_metrics(current_bar)

        # Attempt entry if PM indicates a window is open
        if result["action"] in ["open_entry_window", "window_active"]:
            side = result["side"]

            # Check if we can attempt entry for this side
            if (
                not portfolio.current_position
                and portfolio.can_attempt_entry(side, i, config.entry_window_bars)
                and policy.can_open(decision_ts)
            ):
                # Enforce RMM side gating if provided
                if rmm_context is not None:
                    ctx = rmm_context.get(decision_ts)
                    if ctx is not None:
                        allowed_sides = list(ctx.get("allowed_sides") or [])
                        regime_snapshot = _build_regime_data(ctx)
                        if side not in allowed_sides:
                            skipped.append(
                                {
                                    "entry_time": _fmt_ts(decision_ts),
                                    "symbol": symbol,
                                    "side": side,
                                    "size": float(config.position_size),
                                    "skip_reason": "rmm_block",
                                    "counterfactual_pnl": 0.0,
                                    "counterfactual_mfe_currency": 0.0,
                                    "counterfactual_mae_currency": 0.0,
                                    "regime": regime_snapshot,
                                    "policy_snapshot": {
                                        "allowed_sides": allowed_sides,
                                        "min_confidence": (
                                            (ctx.get("policy") or {}).get(
                                                "min_confidence"
                                            )
                                        ),
                                    },
                                    "notes": None,
                                    "entry_index": i,
                                    "entry_price": float(current_bar["close"]),
                                }
                            )
                            continue

                # Check daily loss cap
                if config.daily_loss_cap is not None and config.daily_loss_cap > 0:
                    now = decision_ts
                    if portfolio.hit_daily_loss_cap(now, float(config.daily_loss_cap)):
                        skipped.append(
                            {
                                "entry_time": _fmt_ts(now),
                                "symbol": symbol,
                                "side": side,
                                "size": float(config.position_size),
                                "skip_reason": "risk_cap",
                                "counterfactual_pnl": 0.0,
                                "counterfactual_mfe_currency": 0.0,
                                "counterfactual_mae_currency": 0.0,
                                "policy_snapshot": {
                                    "daily_loss_cap": float(config.daily_loss_cap)
                                },
                                "notes": None,
                                "entry_index": i,
                                "entry_price": float(current_bar["close"]),
                            }
                        )
                        continue

                # Check position cap
                cap = (
                    limits.get("max_open_long", 1)
                    if side == "long"
                    else limits.get("max_open_short", 1)
                )
                open_ct = 1 if portfolio.current_position else 0
                if open_ct >= cap:
                    skipped.append(
                        {
                            "entry_time": _fmt_ts(decision_ts),
                            "symbol": symbol,
                            "side": side,
                            "size": float(config.position_size),
                            "skip_reason": "position_cap",
                            "counterfactual_pnl": 0.0,
                            "counterfactual_mfe_currency": 0.0,
                            "counterfactual_mae_currency": 0.0,
                            "policy_snapshot": {"cap": cap},
                            "notes": None,
                            "entry_index": i,
                            "entry_price": float(current_bar["close"]),
                        }
                    )
                else:
                    # All filters passed - execute entry
                    size = float(config.position_size)

                    if config.execution_model == "current_bar_close":
                        # Immediate execution at bar close
                        # Calculate initial stop loss price for r_multiple calculation
                        entry_price = current_bar["close"]
                        initial_risk_ccy = None
                        stop_price = None
                        tp_price = None
                        if rem is not None:
                            stop_price = rem.calculate_initial_stop_price(
                                entry_price=entry_price,
                                side=side,
                                entry_bar=feature_bar,
                                signal_context=context or {},
                                prior_bar=feature_prior_bar or feature_bar,
                            )
                            tp_price = rem.calculate_initial_take_profit_price(
                                entry_price=entry_price,
                                side=side,
                                entry_bar=feature_bar,
                                signal_context=context or {},
                                prior_bar=feature_prior_bar or feature_bar,
                            )
                            if stop_price is not None:
                                # initial_risk_ccy = distance * size
                                initial_risk_ccy = abs(entry_price - stop_price) * size

                        portfolio.create_new_position(
                            symbol=symbol,
                            side=side,
                            entry_price=entry_price,
                            size=size,
                            entry_time=decision_ts,
                            instrument=instrument_dict,
                            context_at_entry=context,
                            initial_risk_ccy=initial_risk_ccy,
                            stop_loss=stop_price,
                            take_profit=tp_price,
                        )
                        # Mark that we've entered on this entry window
                        portfolio._entry_windows[side] = (
                            portfolio._entry_windows[side][0],
                            i,
                        )
                    else:  # next_bar_open
                        # Defer execution to next bar's open
                        pending_entry = {
                            "symbol": symbol,
                            "side": side,
                            "size": size,
                            "instrument": instrument_dict,
                            "context": context,
                            "decision_time": decision_ts,
                        }

            elif not policy.can_open(decision_ts):  # pragma: no cover
                # Entry window open but blackout period active
                # pragma: no cover - Defensive: blackout blocks entry at line 269
                reason = policy.reason(decision_ts) or "blackout"  # pragma: no cover
                snap = {
                    "blackout_utc": config.blackout_utc or [],
                    "blackout_events": config.blackout_events or [],
                }
                skipped.append(
                    {
                        "entry_time": _fmt_ts(decision_ts),
                        "symbol": symbol,
                        "side": side,
                        "size": float(config.position_size),
                        "skip_reason": reason,
                        "counterfactual_pnl": 0.0,
                        "counterfactual_mfe_currency": 0.0,
                        "counterfactual_mae_currency": 0.0,
                        "policy_snapshot": snap,
                        "notes": None,
                        "entry_index": i,
                        "entry_price": float(current_bar["close"]),
                    }
                )

        if return_exposure:
            pos = portfolio.current_position
            exposure_val = 0.0
            if pos is not None:
                exposure_val = float(abs(pos.size) * float(current_bar["close"]))
            exposure_curve.append((decision_ts, exposure_val))

    # Force-close any remaining open position at end of backtest
    if portfolio.current_position:
        last_bar = market_data.iloc[-1]
        if last_context_at_exit is None:
            raise ValueError(
                "End-of-data exit detected without recorded context. "
                "Ensure context is captured before closing open positions."
            )
        portfolio.close_position(
            exit_price=last_bar["close"],
            exit_time=cast(datetime, market_data.index[-1]),
            exit_reason="end_of_data",
            context_at_exit=last_context_at_exit,
        )
        # Update the last exposure entry to reflect the closed position
        if return_exposure and exposure_curve:
            # Replace the last entry's exposure value with 0.0
            last_time = exposure_curve[-1][0]
            exposure_curve[-1] = (last_time, 0.0)

    if skipped:
        # Choose counterfactual mode
        mode = getattr(config, "counterfactual_mode", "fast") or "fast"
        use_fast = True if mode == "fast" else False

        for s in skipped:
            val = s.get("entry_index")
            if not isinstance(val, int):
                # entry_index is always set to loop index (int)
                # Non-int here means corrupted data structure - fail fast
                raise ValueError(
                    f"Corrupted skipped entry: entry_index must be int, "
                    f"got {type(val).__name__}: {val}"
                )
            si = val
            side = str(s.get("side", "long"))
            entry_px = float(s.get("entry_price", market_data.iloc[si]["close"]))
            if use_fast:
                cf = _simulate_counterfactual_fast(
                    market_data,
                    strategy,
                    start_index=si,
                    side=side,
                    entry_price=entry_px,
                    size=float(config.position_size),
                    instrument=instrument_dict,
                    cost_model=config.cost_model,
                )
            else:
                cf = _simulate_counterfactual_exact(
                    market_data,
                    strategy,
                    start_index=si,
                    side=side,
                    entry_price=entry_px,
                    size=float(config.position_size),
                    instrument=instrument_dict,
                    cost_model=config.cost_model,
                    rem=rem,
                    symbol=symbol,
                    data_handler=data_handler,
                    bar_minutes=execution_tf_minutes,
                )
            s.update(cf)

    # Post-exit analysis: track price movement after each trade closes
    post_exit_cfg = getattr(config, "post_exit_analysis", None)
    if post_exit_cfg and post_exit_cfg.get("enabled"):
        _enrich_trades_with_post_exit_analysis(
            portfolio.trades, market_data, post_exit_cfg.get("horizons", [10, 20, 50])
        )

    if gating_engine and gating_total:
        coverage = gating_allowed / gating_total if gating_total else 0.0
        logger.info(
            "Gating coverage: allowed %s/%s (%.2f%%)",
            gating_allowed,
            gating_total,
            coverage * 100.0,
        )

    if return_exposure and return_skips:
        return (portfolio.trades, exposure_curve, skipped)
    if return_exposure:
        return (portfolio.trades, exposure_curve)
    if return_skips:
        empty_exposure: list[tuple[datetime, float]] = []
        return (portfolio.trades, empty_exposure, skipped)
    trades_result: list[Trade] = portfolio.trades
    return trades_result


def _simulate_counterfactual_fast(
    market_data: pd.DataFrame,
    strategy: CompiledStrategy,  # kept for signature compatibility
    *,
    start_index: int,
    side: str,
    entry_price: float,
    size: float,
    instrument: dict | None,
    cost_model: dict | None,
) -> dict[str, Any]:
    """Fast counterfactual: hold to end, compute extremes vectorially.

    Matches the previous behavior where the counterfactual did not apply REM
    exits and simply updated MFE/MAE each bar, then exited on the last close.
    """
    if start_index < 0 or start_index >= len(market_data):
        return {}

    idx = market_data.index
    last_idx = len(market_data) - 1

    # Exit at the final bar's close
    exit_time = cast(datetime, idx[last_idx])
    exit_price = float(market_data.iloc[last_idx]["close"])

    # Compute MFE/MAE via extremes across the holding window
    window = market_data.iloc[start_index:]
    high_max = float(window["high"].max()) if "high" in window else entry_price
    low_min = float(window["low"].min()) if "low" in window else entry_price

    if side == "long":
        favorable = max(0.0, (high_max - entry_price) * size)
        adverse = max(0.0, (entry_price - low_min) * size)
        pnl_gross = (exit_price - entry_price) * size
    else:  # short
        favorable = max(0.0, (entry_price - low_min) * size)
        adverse = max(0.0, (high_max - entry_price) * size)
        pnl_gross = (entry_price - exit_price) * size

    # Apply costs using the same CostModel as PortfolioManager
    from trading_platform.core.costs import CostModel

    cm = CostModel.from_dict(cost_model)
    cost_entry, _ = cm.compute_entry_cost(
        size, price=entry_price, instrument=instrument
    )
    cost_exit, _ = cm.compute_exit_cost(size, price=exit_price, instrument=instrument)
    total_cost = float(cost_entry + cost_exit)

    pnl_net = float(pnl_gross) - total_cost

    bars_held = int(len(market_data) - start_index)

    return {
        "cf_exit_time": exit_time.isoformat(),
        "cf_exit_price": exit_price,
        "counterfactual_pnl": pnl_net,  # Keep full precision - rounding in brief.py
        "cf_pnl_currency": pnl_net,  # Alias for brief generation compatibility
        "counterfactual_mfe_currency": float(favorable),
        "counterfactual_mae_currency": float(adverse),
        "cf_bars_held": bars_held,
        "cf_mode": "fast",
    }


def _simulate_counterfactual_exact(
    market_data: pd.DataFrame,
    strategy: CompiledStrategy,  # kept for signature compatibility
    *,
    start_index: int,
    side: str,
    entry_price: float,
    size: float,
    instrument: dict | None,
    cost_model: dict | None,
    rem: RiskExitManager,
    symbol: str,
    data_handler: Any = None,
    bar_minutes: int | None = None,
) -> dict[str, Any]:
    """Exact counterfactual: bar-by-bar re-simulation with REM."""
    if start_index < 0 or start_index >= len(market_data):
        return {}

    pm = PortfolioManager(
        base_currency="USD",
        initial_cash=0.0,
        instrument=instrument,
        cost_model=cost_model,
    )
    entry_time = cast(datetime, market_data.index[start_index])

    # Calculate initial stop loss price for r_multiple calculation
    entry_bar = market_data.iloc[start_index]
    prior_bar = market_data.iloc[start_index - 1] if start_index > 0 else None
    initial_risk_ccy = None
    stop_price = None
    tp_price = None
    if rem is not None:
        stop_price = rem.calculate_initial_stop_price(
            entry_price=entry_price,
            side=side,
            entry_bar=entry_bar,
            signal_context={},  # Counterfactual uses config-based stops
            prior_bar=prior_bar,
        )
        tp_price = rem.calculate_initial_take_profit_price(
            entry_price=entry_price,
            side=side,
            entry_bar=entry_bar,
            signal_context={},  # Counterfactual uses config-based stops
            prior_bar=prior_bar,
        )
        if stop_price is not None:
            # initial_risk_ccy = distance * size
            initial_risk_ccy = abs(entry_price - stop_price) * size

    pm.create_new_position(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        size=size,
        entry_time=entry_time,
        instrument=instrument,
        initial_risk_ccy=initial_risk_ccy,
        stop_loss=stop_price,
        take_profit=tp_price,
    )

    bars_touched = 0
    rem_exit = False
    for i in range(start_index, len(market_data)):
        cb = market_data.iloc[i]
        bars_touched += 1
        # Apply REM exits first for fidelity
        if pm.current_position:
            # Get prior bar for indicator-based stop calculations
            # Stops are set when a bar closes, so use prior bar's data
            prior_bar = market_data.iloc[i - 1] if i > 0 else None
            rem_kwargs = {"data_handler": data_handler, "prior_bar": prior_bar}
            if bar_minutes is not None:
                rem_kwargs["bar_minutes"] = bar_minutes
            try:
                exit_details = rem.check_exits(
                    pm.current_position,
                    cb,
                    **rem_kwargs,
                )
            except TypeError:
                rem_kwargs.pop("bar_minutes", None)
                exit_details = rem.check_exits(
                    pm.current_position,
                    cb,
                    **rem_kwargs,
                )
            if exit_details:
                pm.close_position(
                    exit_price=exit_details["exit_price"],
                    exit_time=cast(datetime, cb.name),
                    exit_reason=exit_details["reason"],
                )
                rem_exit = True
                break

        if not pm.current_position:
            break

        # Update metrics; force the same side so no flips occur
        pm.on_bar(current_bar=cb, current_signal=side)

    if pm.current_position:
        last_idx = len(market_data) - 1
        pm.close_position(
            exit_price=float(market_data.iloc[last_idx]["close"]),
            exit_time=cast(datetime, market_data.index[last_idx]),
        )
    if not pm.trades:
        return {}
    t = pm.trades[0]
    # Derive a consistent bars_touched from observed holding in case
    # loop early-break logic changes.
    derived_bars_touched = int(max(1, t.bars_held or 0))
    # Prefer the measured loop count when it's larger
    # (e.g., when on_bar increments differ).
    bars_touched = int(max(bars_touched, derived_bars_touched))
    last_index = len(market_data) - 1
    exit_kind = "rem" if rem_exit else "end"
    return {
        "cf_exit_time": t.exit_time.isoformat(),
        "cf_exit_price": float(t.exit_price),
        "counterfactual_pnl": float(
            t.pnl
        ),  # Keep full precision - rounding in brief.py
        "cf_pnl_currency": float(t.pnl),  # Alias for brief generation compatibility
        "counterfactual_mfe_currency": float(t.mfe_currency or 0.0),
        "counterfactual_mae_currency": float(t.mae_currency or 0.0),
        "cf_bars_held": int(t.bars_held or 0),
        "cf_bars_touched": bars_touched,
        "cf_start_index": int(start_index),
        "cf_last_index": int(last_index),
        "cf_exit_kind": exit_kind,
        "cf_mode": "exact",
    }


class _BarView(MappingABC[str, Any]):
    """Lightweight mapping view over a DataFrame row backed by NumPy memory."""

    __slots__ = ("_values", "_col_map", "_index", "_row", "name")

    def __init__(
        self,
        values: np.ndarray,
        col_map: dict[str, int],
        index: pd.Index,
        row: int,
    ) -> None:
        self._values = values
        self._col_map = col_map
        self._index = index
        self._row = row
        self.name = index[row]

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self._col_map

    def __getitem__(self, key: str) -> Any:
        pos = self._col_map.get(key)
        if pos is None:
            raise KeyError(key)
        return self._values[self._row, pos]

    def __iter__(self) -> Iterator[str]:
        return iter(self._col_map)

    def __len__(self) -> int:
        return len(self._col_map)

    def get(self, key: str, default: Any = None) -> Any:
        pos = self._col_map.get(key)
        if pos is None:
            return default
        return self._values[self._row, pos]


def _make_bar_factory(df: pd.DataFrame) -> Callable[[int], _BarView]:
    """Return a callable that builds fast row views for the given DataFrame."""
    values = df.to_numpy(copy=False)
    col_map = {col: idx for idx, col in enumerate(df.columns)}
    index = df.index

    def _factory(row: int) -> _BarView:
        return _BarView(values, col_map, index, row)

    return _factory
