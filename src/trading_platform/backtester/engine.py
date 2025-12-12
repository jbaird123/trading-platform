from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any, cast

import pandas as pd

from trading_platform.backtester.context import DecisionSnapshotFactory
from trading_platform.backtester.event_loop import EventLoop
from trading_platform.backtester.models import ExecutionIntent
from trading_platform.backtester.portfolio_manager import PortfolioManager
from trading_platform.backtester.post_exit import (
    enrich_trades_with_post_exit_analysis,
)
from trading_platform.backtester.profiler import PerformanceProfiler
from trading_platform.backtester.risk import RiskExitAdapter
from trading_platform.core.config import RunConfig
from trading_platform.core.policy import TradingWindowPolicy
from trading_platform.core.signal import Signal
from trading_platform.data.bar_windows import compute_bar_close_index
from trading_platform.data.resample import timeframe_to_timedelta
from trading_platform.data.session_metadata import (
    ALIGNED_TO_CLOSE_ATTR,
    SESSION_ATTR,
)
from trading_platform.portfolio.trade import Trade
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy, compile_strategy

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity_curve: list[tuple[datetime, float]]
    skipped: list[dict[str, Any]]
    profiler: PerformanceProfiler | None = None


def _infer_minutes(index: pd.Index) -> int | None:
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 2:
        return None
    delta = index[1] - index[0]
    return int(delta.total_seconds() // 60) if delta is not pd.NaT else None


def _merge_strategy_context(
    strategy: CompiledStrategy,
    bar_index: int,
    signal_obj: Signal | str | None,
) -> tuple[str | None, dict[str, Any]]:
    context = {}
    try:
        context = strategy.get_context(bar_index)
    except Exception:
        context = {}

    command: str | None = None
    if isinstance(signal_obj, Signal):
        command = signal_obj.command
        if isinstance(signal_obj.context, dict):
            context = {**context, **signal_obj.context}
    elif isinstance(signal_obj, str):
        command = signal_obj
    return command, context


def _build_bar_payload(
    timestamp: Any,
    row: pd.Series,
    fallback_open_delta: timedelta | None,
) -> dict[str, Any]:
    open_time = row.get("bar_open", row.get("open_time"))
    close_time = row.get("bar_close", row.get("close_time"))
    if open_time is None:
        open_time = timestamp
    if close_time is None:
        if fallback_open_delta is not None:
            close_time = open_time + fallback_open_delta
        else:
            close_time = timestamp
    payload = {
        "open_time": pd.to_datetime(open_time).to_pydatetime(),
        "close_time": pd.to_datetime(close_time).to_pydatetime(),
        "open": float(row.get("open", row.get("close", 0.0))),
        "high": float(row.get("high", row.get("close", 0.0))),
        "low": float(row.get("low", row.get("close", 0.0))),
        "close": float(row.get("close", 0.0)),
        "volume": float(row.get("volume", 0.0)),
        "bar": row,
    }
    return payload


def run_event_loop_backtest(
    *,
    config: RunConfig,
    market_data: pd.DataFrame,
    strategy_config: dict[str, Any] | None = None,
    compiled_strategy: CompiledStrategy | None = None,
    precomputed_signals: Any | None = None,
    strategy_feature_df: pd.DataFrame | None = None,
    data_handler: Any | None = None,
    global_feature_df: pd.DataFrame | None = None,
    rmm_context: dict[datetime, dict[str, Any]] | None = None,
    rem_instance: RiskExitManager | None = None,
    profiler: PerformanceProfiler | None = None,
) -> BacktestResult:
    # Enforce that this function is only called from authorized entry points
    import inspect

    caller_frame = inspect.stack()[1]
    caller_file = caller_frame.filename

    allowed_callers = [
        "backtester/__init__.py",
        "backtester/_testing.py",
    ]

    if not any(allowed in caller_file for allowed in allowed_callers):
        raise RuntimeError(
            "run_event_loop_backtest() cannot be called directly. "
            "Use run_backtest() from trading_platform.backtester for production, "
            "or run_backtest_with_synthetic_data() from "
            "trading_platform.backtester._testing for tests with synthetic data."
        )

    # Normalize market data to tz-aware UTC
    md_idx = market_data.index
    if isinstance(md_idx, pd.DatetimeIndex) and md_idx.tz is None:
        market_data = market_data.copy()
        market_data.index = md_idx.tz_localize("UTC")

    # Normalize RMM context keys to tz-aware UTC
    if rmm_context:
        rmm_context = {
            pd.to_datetime(ts, utc=True): ctx for ts, ctx in rmm_context.items()
        }

    # Initialize profiler if not provided
    if profiler is None:
        profiler = PerformanceProfiler()

    if config.execution_model not in {"next_bar_open", "current_bar_close"}:
        logger.warning(
            "Unsupported execution_model '%s'; proceeding with next_bar_open semantics",
            config.execution_model,
        )

    # Stage 1: Compile strategy
    t_compile_start = perf_counter()
    if compiled_strategy is None:
        if strategy_config is None:
            raise ValueError(
                "strategy_config is required when compiled_strategy is not provided."
            )
        strategy = compile_strategy(strategy_config)
    else:
        strategy = compiled_strategy
    t_compile_ms = (perf_counter() - t_compile_start) * 1000

    # Stage 1.5: Align market data to explicit bar_open/bar_close
    tf_str = (
        (config.instrument or {}).get("timeframe")
        or f"{_infer_minutes(market_data.index)}min"
        if _infer_minutes(market_data.index)
        else "1h"
    )
    tf_delta = timeframe_to_timedelta(tf_str)
    session = market_data.attrs.get(SESSION_ATTR)
    has_bar_times = {"bar_open", "bar_close"}.issubset(market_data.columns)
    if has_bar_times:
        bar_open = pd.DatetimeIndex(pd.to_datetime(market_data["bar_open"], utc=True))
        bar_close = pd.DatetimeIndex(pd.to_datetime(market_data["bar_close"], utc=True))
    else:
        aligned_to_close = bool(market_data.attrs.get(ALIGNED_TO_CLOSE_ATTR, False))
        base_index = pd.DatetimeIndex(market_data.index)
        if aligned_to_close:
            bar_close = base_index
            bar_open = base_index - tf_delta
        else:
            bar_open = base_index
            bar_close = compute_bar_close_index(bar_open, tf_str, session=session)
    close_aligned = market_data.copy()
    close_aligned.index = bar_close
    close_aligned["open_time"] = bar_open
    close_aligned["close_time"] = bar_close
    close_aligned["bar_open"] = bar_open
    close_aligned["bar_close"] = bar_close
    if session is not None:
        close_aligned.attrs[SESSION_ATTR] = session
    close_aligned.attrs[ALIGNED_TO_CLOSE_ATTR] = True

    # Stage 2: Generate/process signals
    t_signals_start = perf_counter()
    if precomputed_signals is not None:
        if isinstance(precomputed_signals, pd.Series):
            signals = precomputed_signals
            if not signals.index.equals(close_aligned.index):
                signals = signals.reindex(close_aligned.index, method="ffill")
            else:
                signals = signals.copy()
        else:
            raw_signals = list(precomputed_signals)
            signals = pd.Series(
                raw_signals, index=close_aligned.index[: len(raw_signals)]
            )
            signals = signals.reindex(close_aligned.index, method="ffill")
    else:
        signals = strategy.generate_signals(close_aligned)
        if len(signals) != len(close_aligned):
            signals = signals.reindex(close_aligned.index, method="ffill")
    t_signals_ms = (perf_counter() - t_signals_start) * 1000

    # Stage 3: Prepare features
    t_features_start = perf_counter()
    aligned_global_features = (
        global_feature_df.reindex(close_aligned.index)
        if global_feature_df is not None
        else None
    )

    strategy_feature_df = (
        strategy_feature_df
        if strategy_feature_df is not None
        else getattr(strategy, "_feature_df", None)
    )
    if isinstance(strategy_feature_df, pd.DataFrame):
        strategy_feature_df = strategy_feature_df.reindex(close_aligned.index)

    t_features_ms = (perf_counter() - t_features_start) * 1000

    # Stage 4: Setup components (REM, portfolio, event loop, policies)
    t_setup_start = perf_counter()
    instrument_dict = config.instrument or {}
    rem = rem_instance or RiskExitManager(
        config=config.rem_config or {},
        instrument=instrument_dict if instrument_dict else None,
        exit_tie_break=config.exit_tie_break,
    )
    execution_minutes = _infer_minutes(close_aligned.index)
    bar_delta = (
        timedelta(minutes=execution_minutes) if execution_minutes is not None else None
    )
    risk_adapter = RiskExitAdapter(
        rem=rem,
        data_handler=data_handler,
        bar_minutes=execution_minutes,
    )
    pm_limits = config.pm_limits or {}
    max_positions = max(
        int(pm_limits.get("max_open_long", 1)),
        int(pm_limits.get("max_open_short", 1)),
    )
    portfolio = PortfolioManager(
        instrument=instrument_dict,
        cost_model=config.cost_model,
        default_position_size=float(config.position_size),
        entry_window_bars=max(1, int(config.entry_window_bars or 1)),
        max_positions_per_side=max_positions,
    )
    event_loop = EventLoop(portfolio=portfolio, risk_adapter=risk_adapter)
    tw_policy = TradingWindowPolicy.from_config(
        blackout_utc=config.blackout_utc or [],
        blackout_events=config.blackout_events or [],
    )
    t_setup_ms = (perf_counter() - t_setup_start) * 1000

    def _extract_take_profit(side: str) -> dict[str, Any] | None:
        """Extract the first take-profit block for the given side."""
        blocks = (
            strategy.long_exit_blocks if side == "long" else strategy.short_exit_blocks
        )
        if not blocks:
            return None
        for block in blocks:
            tp_cfg = block.get("take_profit")
            if isinstance(tp_cfg, dict):
                return tp_cfg
        return None

    def _counterfactual_from_rules(
        side: str, entry_price: float, ts: datetime
    ) -> dict[str, Any]:
        """Heuristic counterfactual info for skipped entries."""
        tp_cfg = _extract_take_profit(side)
        details: dict[str, Any] = {"cf_exit_time": ts.isoformat()}
        if tp_cfg:
            tp_val = float(tp_cfg.get("value", 0.0))
            tp_type = tp_cfg.get("type", "price")
            if tp_type in {"price", "delta", "offset"}:
                target = (
                    entry_price + tp_val if side == "long" else entry_price - tp_val
                )
            else:
                target = entry_price
            pnl_currency = (target - entry_price) * (
                float(config.position_size)
                if side == "long"
                else -float(config.position_size)
            )
            details.update(
                {
                    "cf_exit_price": target,
                    "cf_pnl_currency": pnl_currency,
                    "counterfactual_entry_price": entry_price,
                }
            )
        return details

    def _regime_builder(ctx: dict[str, Any] | None) -> dict[str, Any] | None:
        if ctx is None:
            return None
        payload = dict(ctx)
        if "label" in payload and "raw_label" not in payload:
            payload["raw_label"] = payload["label"]
        if "confidence" in payload and "raw_confidence" not in payload:
            payload["raw_confidence"] = payload["confidence"]
        payload.setdefault(
            "hysteresis",
            {
                "bars_in_state": payload.get("bars_in_state", 0),
                "cooldown_remaining": payload.get("cooldown_remaining", 0),
            },
        )
        return payload

    def _regime_snapshot(ts: datetime) -> dict[str, Any] | None:
        if rmm_context is None:
            return None
        ctx = rmm_context.get(ts)
        if ctx is None:
            return None
        snap = dict(ctx)
        if "label" in snap and "raw_label" not in snap:
            snap["raw_label"] = snap["label"]
        if "confidence" in snap and "raw_confidence" not in snap:
            snap["raw_confidence"] = snap["confidence"]
        snap.setdefault(
            "hysteresis",
            {
                "bars_in_state": snap.get("bars_in_state", 0),
                "cooldown_remaining": snap.get("cooldown_remaining", 0),
            },
        )
        return snap

    def _rmm_allows(side: str, ts: datetime) -> bool:
        if rmm_context is None:
            return True
        ctx = rmm_context.get(ts)
        if ctx is None:
            return True
        allowed = ctx.get("allowed_sides") or []
        return side in allowed

    def _blackout_blocked(ts: datetime) -> bool:
        try:
            return not tw_policy.can_open(ts)
        except Exception:
            return False

    snapshot_factory = DecisionSnapshotFactory(
        rmm_context=rmm_context,
        regime_builder=_regime_builder,
        global_feature_df=aligned_global_features,
        global_feature_keys=[]
        if aligned_global_features is None
        else list(aligned_global_features.columns),
        global_feature_timeframes={},
        execution_tf_minutes=execution_minutes,
    )
    skipped: list[dict[str, Any]] = []

    def has_open(side: str) -> bool:
        return any(
            view.decision.side == side for view in portfolio.active_position_views()
        )

    prior_bar = None

    def _entry_risk_fields(
        side: str,
        entry_price: float,
        bar_series: pd.Series,
        signal_context: dict[str, Any],
        prior_bar_series: pd.Series | None,
    ) -> dict[str, Any]:
        risk_fields: dict[str, Any] = {"entry_price": entry_price}
        if rem is None:
            return risk_fields
        # For initial stop, use signal bar (bar_series) as the "prior bar" because
        # we want the stop based on the bar where the signal occurred. The context
        # contains features (ATR, etc.) from the signal bar, so we need close from
        # the same bar for consistency. Trailing updates use the actual prior bar.
        stop_price = rem.calculate_initial_stop_price(
            entry_price=entry_price,
            side=side,
            entry_bar=bar_series,
            signal_context=signal_context,
            prior_bar=bar_series,  # Use signal bar, not prior bar
        )
        take_profit = rem.calculate_initial_take_profit_price(
            entry_price=entry_price,
            side=side,
            entry_bar=bar_series,
            signal_context=signal_context,
            prior_bar=bar_series,  # Use signal bar, not prior bar
        )
        if stop_price is not None:
            risk_fields["entry_stop_loss"] = stop_price
            risk_fields["initial_risk_ccy"] = abs(
                entry_price - float(stop_price)
            ) * float(config.position_size)
        if take_profit is not None:
            risk_fields["entry_take_profit"] = take_profit
        return risk_fields

    debug_counts = {"enter_long": 0, "enter_short": 0, "exit_long": 0, "exit_short": 0}
    pending_intents: list[ExecutionIntent] = []
    pending_entries: list[dict[str, Any]] = []
    exposure_curve: list[tuple[datetime, float]] = []
    cf_mode = getattr(config, "counterfactual_mode", "fast") or "fast"

    # Stage 4.5: Use aligned view with explicit bar timing
    feature_view = close_aligned
    if isinstance(strategy_feature_df, pd.DataFrame):
        strat_cols = [
            col
            for col in strategy_feature_df.columns
            if col not in feature_view.columns
        ]
        if strat_cols:
            feature_view = feature_view.join(
                strategy_feature_df[strat_cols], how="left"
            )
    if aligned_global_features is not None:
        feature_cols = [
            col
            for col in aligned_global_features.columns
            if col not in feature_view.columns
        ]
        if feature_cols:
            aligned_subset = aligned_global_features[feature_cols]
            feature_view = feature_view.join(aligned_subset, how="left")

    # Stage 5: Main event loop
    t_loop_start = perf_counter()

    # Determine trading window start from config.data_request
    data_request = getattr(config, "data_request", None) or {}
    trading_start_val = data_request.get("start")
    trading_start_idx = 0  # Default to beginning if no start specified
    if trading_start_val is not None:
        trading_start_ts = pd.to_datetime(trading_start_val, utc=True)
        # Find the index position of the trading window start
        idx_positions = feature_view.index.get_indexer(
            [trading_start_ts], method="bfill"
        )
        if idx_positions[0] >= 0:
            trading_start_idx = idx_positions[0]

    # Validate no NaNs in strategy feature columns within the trading window
    # (Global features are already validated in _compute_global_features)
    base_market_cols = {
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_time",
        "close_time",
        "bar_open",
        "bar_close",
    }
    # Only check strategy features (global validated in _compute_global_features)
    global_feature_cols = (
        set(aligned_global_features.columns)
        if aligned_global_features is not None
        else set()
    )
    feature_cols_to_check = [
        col
        for col in feature_view.columns
        if col not in base_market_cols and col not in global_feature_cols
    ]
    if feature_cols_to_check:
        trading_window = feature_view.iloc[trading_start_idx:]
        nan_cols = [
            col for col in feature_cols_to_check if trading_window[col].isna().any()
        ]
        if nan_cols:
            raise ValueError(
                f"Features contain NaNs: {', '.join(sorted(nan_cols))}. "
                "Ensure all features are fully populated before the backtest starts."
            )

    # Start loop at trading window start
    bars_processed = len(feature_view) - trading_start_idx
    # Initialize prior_bar so indicator-based stops can compute on first entry
    if trading_start_idx > 0:
        prior_bar = feature_view.iloc[trading_start_idx - 1]
    for i in range(trading_start_idx, len(feature_view)):
        row = feature_view.iloc[i]
        timestamp = feature_view.index[i]
        if isinstance(timestamp, pd.Timestamp):
            bar_timestamp: datetime = timestamp.to_pydatetime()
        else:
            bar_timestamp = cast(datetime, timestamp)
        close_price = float(row.get("close", 0.0))
        bar_payload = _build_bar_payload(bar_timestamp, row, bar_delta)
        # Process pending entries (e.g., RMM blocked earlier) before new signals
        updated_pending: list[dict[str, Any]] = []
        for pending in pending_entries:
            side = pending["side"]
            expiry = pending["expiry"]
            origin_idx = pending["origin_index"]
            intent = pending["intent"]
            if i > expiry:
                continue
            if _blackout_blocked(bar_timestamp):
                skip_entry = {
                    "entry_time": bar_timestamp.isoformat(),
                    "symbol": instrument_dict.get("symbol")
                    if instrument_dict
                    else None,
                    "side": side,
                    "size": float(config.position_size),
                    "skip_reason": "blackout",
                    "counterfactual_pnl": 0.0,
                    "counterfactual_mfe_currency": 0.0,
                    "counterfactual_mae_currency": 0.0,
                    "cf_mode": cf_mode,
                    "regime": _regime_snapshot(bar_timestamp),
                    "policy_snapshot": {
                        "blackout_utc": config.blackout_utc or [],
                        "blackout_events": config.blackout_events or [],
                    },
                    "notes": None,
                    "entry_index": origin_idx,
                    "entry_price": close_price,
                }
                skip_entry.update(
                    _counterfactual_from_rules(side, close_price, bar_timestamp)
                )
                skipped.append(skip_entry)
                updated_pending.append(pending)
                continue
            if not _rmm_allows(side, bar_timestamp):
                skip_entry = {
                    "entry_time": bar_timestamp.isoformat(),
                    "symbol": instrument_dict.get("symbol")
                    if instrument_dict
                    else None,
                    "side": side,
                    "size": float(config.position_size),
                    "skip_reason": "rmm_block",
                    "counterfactual_pnl": 0.0,
                    "counterfactual_mfe_currency": 0.0,
                    "counterfactual_mae_currency": 0.0,
                    "cf_mode": cf_mode,
                    "regime": _regime_snapshot(bar_timestamp),
                    "policy_snapshot": rmm_context.get(bar_timestamp)
                    if rmm_context
                    else {},
                    "notes": None,
                    "entry_index": origin_idx,
                    "entry_price": close_price,
                }
                skip_entry.update(
                    _counterfactual_from_rules(side, close_price, bar_timestamp)
                )
                skipped.append(skip_entry)
                updated_pending.append(pending)
                continue
            # Allowed now
            if has_open(side):
                continue
            pending_intents.append(intent)
        pending_entries = updated_pending

        if pending_intents and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "bar %s processing %s pending intents",
                i,
                len(pending_intents),
            )
        event_loop.on_bar(bar_payload, intents=pending_intents)
        pending_intents = []

        signal_obj = signals.iloc[i] if i < len(signals) else None
        command, context = _merge_strategy_context(strategy, i, signal_obj)
        if command in debug_counts:
            debug_counts[command] += 1
        if logger.isEnabledFor(logging.DEBUG) and (i < 20 or 90 <= i <= 110):
            logger.debug(
                "bar %s command=%s has_open_long=%s has_open_short=%s",
                i,
                command,
                has_open("long"),
                has_open("short"),
            )
        intents: list[ExecutionIntent] = []

        def build_snapshot(
            side: str, risk_fields: dict[str, Any] | None = None
        ) -> ExecutionIntent:
            risk_fields = risk_fields or {"entry_price": close_price}
            snapshot = snapshot_factory.create(
                timestamp=bar_timestamp,
                price=close_price,
                side=side,
                size=float(config.position_size),
                bar_index=i,
                strategy_context=context or {},
                extra_fields={"risk": risk_fields},
            )
            return ExecutionIntent(
                decision=snapshot,
                intent_type="enter_long" if side == "long" else "enter_short",
                execution_model="next_bar_open",
            )

        def build_exit_snapshot(side: str) -> ExecutionIntent:
            snapshot = snapshot_factory.create(
                timestamp=bar_timestamp,
                price=close_price,
                side=side,
                size=float(config.position_size),
                bar_index=i,
                strategy_context=context or {},
                extra_fields={"risk": {"exit_command": command}},
            )
            return ExecutionIntent(
                decision=snapshot,
                intent_type="exit",
                execution_model="next_bar_open",
            )

        if command == "enter_long":
            risk_fields_long = _entry_risk_fields(
                "long", close_price, row, context or {}, prior_bar
            )
            if _blackout_blocked(bar_timestamp):
                skip_entry = {
                    "entry_time": bar_timestamp.isoformat(),
                    "symbol": instrument_dict.get("symbol")
                    if instrument_dict
                    else None,
                    "side": "long",
                    "size": float(config.position_size),
                    "skip_reason": "blackout",
                    "counterfactual_pnl": 0.0,
                    "counterfactual_mfe_currency": 0.0,
                    "counterfactual_mae_currency": 0.0,
                    "cf_mode": cf_mode,
                    "regime": _regime_snapshot(bar_timestamp),
                    "policy_snapshot": {
                        "blackout_utc": config.blackout_utc or [],
                        "blackout_events": config.blackout_events or [],
                    },
                    "notes": None,
                    "entry_index": i,
                    "entry_price": close_price,
                }
                skip_entry.update(
                    _counterfactual_from_rules("long", close_price, bar_timestamp)
                )
                skipped.append(skip_entry)
                continue
            if not _rmm_allows("long", bar_timestamp):
                skip_entry = {
                    "entry_time": bar_timestamp.isoformat(),
                    "symbol": instrument_dict.get("symbol")
                    if instrument_dict
                    else None,
                    "side": "long",
                    "size": float(config.position_size),
                    "skip_reason": "rmm_block",
                    "counterfactual_pnl": 0.0,
                    "counterfactual_mfe_currency": 0.0,
                    "counterfactual_mae_currency": 0.0,
                    "cf_mode": cf_mode,
                    "regime": _regime_snapshot(bar_timestamp),
                    "policy_snapshot": rmm_context.get(bar_timestamp)
                    if rmm_context
                    else {},
                    "notes": None,
                    "entry_index": i,
                    "entry_price": close_price,
                }
                skip_entry.update(
                    _counterfactual_from_rules("long", close_price, bar_timestamp)
                )
                skipped.append(skip_entry)
                expiry_idx = i + max(0, int(config.entry_window_bars or 0))
                pending_entries.append(
                    {
                        "side": "long",
                        "intent": build_snapshot("long", risk_fields_long),
                        "expiry": expiry_idx,
                        "origin_index": i,
                    }
                )
            else:
                if has_open("long"):
                    continue
                if has_open("short"):
                    logger.debug(
                        "Enqueue exit_short before enter_long at idx %s",
                        i,
                    )
                    intents.append(build_exit_snapshot("short"))
                intents.append(build_snapshot("long", risk_fields_long))
        elif command == "enter_short":
            risk_fields_short = _entry_risk_fields(
                "short", close_price, row, context or {}, prior_bar
            )
            if _blackout_blocked(bar_timestamp):
                skip_entry = {
                    "entry_time": bar_timestamp.isoformat(),
                    "symbol": instrument_dict.get("symbol")
                    if instrument_dict
                    else None,
                    "side": "short",
                    "size": float(config.position_size),
                    "skip_reason": "blackout",
                    "counterfactual_pnl": 0.0,
                    "counterfactual_mfe_currency": 0.0,
                    "counterfactual_mae_currency": 0.0,
                    "cf_mode": cf_mode,
                    "regime": _regime_snapshot(bar_timestamp),
                    "policy_snapshot": {
                        "blackout_utc": config.blackout_utc or [],
                        "blackout_events": config.blackout_events or [],
                    },
                    "notes": None,
                    "entry_index": i,
                    "entry_price": close_price,
                }
                skip_entry.update(
                    _counterfactual_from_rules("short", close_price, bar_timestamp)
                )
                skipped.append(skip_entry)
                continue
            if not _rmm_allows("short", bar_timestamp):
                skip_entry = {
                    "entry_time": bar_timestamp.isoformat(),
                    "symbol": instrument_dict.get("symbol")
                    if instrument_dict
                    else None,
                    "side": "short",
                    "size": float(config.position_size),
                    "skip_reason": "rmm_block",
                    "counterfactual_pnl": 0.0,
                    "counterfactual_mfe_currency": 0.0,
                    "counterfactual_mae_currency": 0.0,
                    "cf_mode": cf_mode,
                    "regime": _regime_snapshot(bar_timestamp),
                    "policy_snapshot": rmm_context.get(bar_timestamp)
                    if rmm_context
                    else {},
                    "notes": None,
                    "entry_index": i,
                    "entry_price": close_price,
                }
                skip_entry.update(
                    _counterfactual_from_rules("short", close_price, bar_timestamp)
                )
                skipped.append(skip_entry)
                expiry_idx = i + max(0, int(config.entry_window_bars or 0))
                pending_entries.append(
                    {
                        "side": "short",
                        "intent": build_snapshot("short", risk_fields_short),
                        "expiry": expiry_idx,
                        "origin_index": i,
                    }
                )
            else:
                if has_open("short"):
                    continue
                if has_open("long"):
                    logger.debug(
                        "Enqueue exit_long before enter_short at idx %s",
                        i,
                    )
                    intents.append(build_exit_snapshot("long"))
                intents.append(build_snapshot("short", risk_fields_short))
        elif command == "exit_long":
            intents.append(build_exit_snapshot("long"))
        elif command == "exit_short":
            intents.append(build_exit_snapshot("short"))

        if logger.isEnabledFor(logging.DEBUG) and (i < 20 or 90 <= i <= 110):
            logger.debug(
                "bar %s queued %s new intents",
                i,
                len(intents),
            )

        pending_intents = intents

        # Track exposure per bar (gross notional)
        exposure_val = 0.0
        if portfolio.active_positions:
            exposure_val = sum(
                abs(view.position.size) * close_price
                for view in portfolio.active_positions
            )
        exposure_curve.append((bar_timestamp, exposure_val))
        prior_bar = row

    # Force-close any remaining open positions at end of data
    if portfolio.active_positions:
        last_time = cast(datetime, market_data.index[-1])
        last_close = float(market_data.iloc[-1]["close"])
        from trading_platform.backtester.models import FillEvent

        for view in list(portfolio.active_positions):
            exit_ctx = snapshot_factory.create(
                timestamp=last_time,
                price=last_close,
                side=view.decision.side,
                size=view.decision.size,
                bar_index=len(feature_view) - 1,
                strategy_context={},
                extra_fields={
                    "risk": view.decision.context.get("risk", {})
                    if view.decision.context
                    else {}
                },
            ).context
            forced_decision = replace(
                view.decision,
                context=exit_ctx,
            )
            fill = FillEvent(
                intent=None,
                timestamp=last_time,
                price=last_close,
                size=view.decision.size,
                decision=forced_decision,
                costs={"spread": 0.0, "commission": 0.0, "slippage": 0.0},
                reason="end_of_data",
            )
            portfolio.apply_fill(fill)
        exposure_curve.append((last_time, 0.0))
    t_loop_ms = (perf_counter() - t_loop_start) * 1000

    # Build equity curve
    # Exposure curve is returned as equity_curve for compatibility with callers
    equity_curve: list[tuple[datetime, float]] = (
        exposure_curve if exposure_curve else []
    )

    # Stage 6: Post-exit analysis
    t_post_exit_start = perf_counter()
    post_exit_cfg = getattr(config, "post_exit_analysis", None)
    if post_exit_cfg and post_exit_cfg.get("enabled"):
        horizons = post_exit_cfg.get("horizons", [10, 20, 50])
        enrich_trades_with_post_exit_analysis(
            portfolio.trades,
            market_data,
            horizons,
        )
    t_post_exit_ms = (perf_counter() - t_post_exit_start) * 1000

    # Record all timing data to profiler
    if profiler.enabled:
        # Record individual stages (without using context managers, just set directly)
        from trading_platform.backtester.profiler import StageMetrics

        profiler._stages["compile_strategy"] = StageMetrics(
            duration_ms=t_compile_ms,
            metadata={"strategy_type": type(strategy).__name__},
        )

        profiler._stages["generate_signals"] = StageMetrics(
            duration_ms=t_signals_ms, metadata={"signal_count": len(signals)}
        )

        profiler._stages["prepare_features"] = StageMetrics(
            duration_ms=t_features_ms,
            metadata={
                "total_bars": len(feature_view),
                "trading_start_idx": trading_start_idx,
            },
        )

        profiler._stages["setup_components"] = StageMetrics(
            duration_ms=t_setup_ms, metadata={}
        )

        # Record backtest metrics with bars/sec
        profiler.record_backtest_metrics(
            duration_ms=t_loop_ms,
            bars_processed=bars_processed,
        )

        profiler._stages["post_exit_analysis"] = StageMetrics(
            duration_ms=t_post_exit_ms,
            metadata={
                "enabled": post_exit_cfg.get("enabled") if post_exit_cfg else False
            },
        )

        # Calculate total duration (sum of all stages)
        profiler._total_duration = (
            t_compile_ms
            + t_signals_ms
            + t_features_ms
            + t_setup_ms
            + t_loop_ms
            + t_post_exit_ms
        ) / 1000.0

    if not portfolio.trades:
        open_summaries = [
            {
                "position_id": getattr(view, "position_id", "unknown"),
                "side": view.decision.side,
                "entry_time": getattr(view.position, "entry_time", None),
            }
            for view in portfolio.active_positions
        ]
        logging.getLogger(__name__).warning(
            "run_event_loop_backtest produced zero trades; "
            "commands=%s pending_entries=%s active_positions=%s "
            "bars=%s range=[%s -> %s] "
            "config.entry_window_bars=%s config.position_size=%s open_positions=%s",
            debug_counts,
            getattr(portfolio, "pending_entry_count", None),
            len(portfolio.active_positions),
            len(market_data),
            market_data.index[0] if len(market_data) else None,
            market_data.index[-1] if len(market_data) else None,
            config.entry_window_bars,
            config.position_size,
            open_summaries,
        )
    return BacktestResult(
        trades=list(portfolio.trades),
        equity_curve=equity_curve,
        skipped=skipped,
        profiler=profiler,
    )
