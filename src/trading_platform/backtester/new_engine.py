from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, cast

import pandas as pd

from trading_platform.backtester.context import DecisionSnapshotFactory
from trading_platform.backtester.event_loop import EventLoop
from trading_platform.backtester.models import ExecutionIntent
from trading_platform.backtester.portfolio_manager import PortfolioManager
from trading_platform.backtester.risk import RiskExitAdapter
from trading_platform.core.config import RunConfig
from trading_platform.core.signal import Signal
from trading_platform.portfolio.trade import Trade
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy, compile_strategy

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity_curve: list[tuple[datetime, float]]
    skipped: list[dict[str, Any]]


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
    open_time = row.get("open_time")
    close_time = row.get("close_time")
    if open_time is None:
        open_time = timestamp
    if close_time is None:
        if fallback_open_delta is not None:
            close_time = open_time + fallback_open_delta
        else:
            close_time = timestamp
    payload = {
        "open_time": open_time,
        "close_time": close_time,
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
) -> BacktestResult:
    if config.execution_model != "next_bar_open":
        raise ValueError(
            "The new backtester currently supports only "
            "execution_model='next_bar_open'."
        )

    if compiled_strategy is None:
        if strategy_config is None:
            raise ValueError(
                "strategy_config is required when compiled_strategy is not provided."
            )
        strategy = compile_strategy(strategy_config)
    else:
        strategy = compiled_strategy

    if precomputed_signals is not None:
        if isinstance(precomputed_signals, pd.Series):
            signals = precomputed_signals
            if not signals.index.equals(market_data.index):
                signals = signals.reindex(market_data.index, method="ffill")
            else:
                signals = signals.copy()
        else:
            raw_signals = list(precomputed_signals)
            signals = pd.Series(
                raw_signals, index=market_data.index[: len(raw_signals)]
            )
            signals = signals.reindex(market_data.index, method="ffill")
    else:
        signals = strategy.generate_signals(market_data)
        if len(signals) != len(market_data):
            signals = signals.reindex(market_data.index, method="ffill")

    aligned_global_features = (
        global_feature_df.reindex(market_data.index)
        if global_feature_df is not None
        else None
    )

    strategy_feature_df = (
        strategy_feature_df
        if strategy_feature_df is not None
        else getattr(strategy, "_feature_df", None)
    )
    if strategy_feature_df is not None:
        bad_cols = []
        for col in strategy_feature_df.columns:
            if col in market_data.columns:
                continue
            series = strategy_feature_df[col]
            if series.isna().any():
                bad_cols.append(col)
        if bad_cols:
            raise ValueError(
                f"Strategy features contain NaNs: {', '.join(sorted(bad_cols))}"
            )
    if isinstance(strategy_feature_df, pd.DataFrame):
        strategy_feature_df = strategy_feature_df.reindex(market_data.index)

    instrument_dict = config.instrument or {}
    rem = RiskExitManager(
        config=config.rem_config or {},
        instrument=instrument_dict if instrument_dict else None,
        exit_tie_break=config.exit_tie_break,
    )
    execution_minutes = _infer_minutes(market_data.index)
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
    snapshot_factory = DecisionSnapshotFactory(
        rmm_context=rmm_context,
        regime_builder=None,  # Not yet supported in this path
        global_feature_df=aligned_global_features,
        global_feature_keys=[]
        if aligned_global_features is None
        else list(aligned_global_features.columns),
        global_feature_timeframes={},
        execution_tf_minutes=execution_minutes,
    )
    skipped: list[dict[str, Any]] = []

    feature_view = market_data
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
        aligned_subset = aligned_global_features
        if feature_cols:
            aligned_subset = aligned_global_features[feature_cols]
        feature_view = feature_view.join(aligned_subset, how="left")

    def has_open(side: str) -> bool:
        return any(
            view.decision.side == side for view in portfolio.active_position_views()
        )

    debug_counts = {"enter_long": 0, "enter_short": 0, "exit_long": 0, "exit_short": 0}
    pending_intents: list[ExecutionIntent] = []
    exposure_curve: list[tuple[datetime, float]] = []
    for idx, (timestamp, row) in enumerate(feature_view.iterrows()):
        if isinstance(timestamp, pd.Timestamp):
            bar_timestamp: datetime = timestamp.to_pydatetime()
        else:
            bar_timestamp = cast(datetime, timestamp)
        bar_payload = _build_bar_payload(bar_timestamp, row, bar_delta)
        if pending_intents and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "bar %s processing %s pending intents",
                idx,
                len(pending_intents),
            )
        event_loop.on_bar(bar_payload, intents=pending_intents)
        pending_intents = []

        signal_obj = signals.iloc[idx] if idx < len(signals) else None
        command, context = _merge_strategy_context(strategy, idx, signal_obj)
        if command in debug_counts:
            debug_counts[command] += 1
        if logger.isEnabledFor(logging.DEBUG) and (idx < 20 or 90 <= idx <= 110):
            logger.debug(
                "bar %s command=%s has_open_long=%s has_open_short=%s",
                idx,
                command,
                has_open("long"),
                has_open("short"),
            )
        intents: list[ExecutionIntent] = []

        def build_snapshot(side: str) -> ExecutionIntent:
            risk_fields = {"entry_price": float(row.get("close", 0.0))}
            snapshot = snapshot_factory.create(
                timestamp=bar_timestamp,
                price=float(row.get("close", 0.0)),
                side=side,
                size=float(config.position_size),
                bar_index=idx,
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
                price=float(row.get("close", 0.0)),
                side=side,
                size=float(config.position_size),
                bar_index=idx,
                strategy_context=context or {},
                extra_fields={"risk": {"exit_command": command}},
            )
            return ExecutionIntent(
                decision=snapshot,
                intent_type="exit",
                execution_model="next_bar_open",
            )

        def _rmm_allows(side: str) -> bool:
            if rmm_context is None:
                return True
            ctx = rmm_context.get(bar_timestamp)
            if ctx is None:
                return True
            allowed = ctx.get("allowed_sides") or []
            return side in allowed

        if command == "enter_long":
            if not _rmm_allows("long"):
                skipped.append(
                    {
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
                        "regime": rmm_context.get(bar_timestamp)
                        if rmm_context
                        else None,
                        "policy_snapshot": (
                            rmm_context.get(bar_timestamp) or {}
                            if rmm_context is not None
                            else {}
                        ),
                        "notes": None,
                        "entry_index": idx,
                        "entry_price": float(row.get("close", 0.0)),
                    }
                )
            else:
                if has_open("long"):
                    continue
                if has_open("short"):
                    logger.debug(
                        "Enqueue exit_short before enter_long at idx %s",
                        idx,
                    )
                    intents.append(build_exit_snapshot("short"))
                intents.append(build_snapshot("long"))
        elif command == "enter_short":
            if not _rmm_allows("short"):
                skipped.append(
                    {
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
                        "regime": rmm_context.get(bar_timestamp)
                        if rmm_context
                        else None,
                        "policy_snapshot": (
                            rmm_context.get(bar_timestamp) or {}
                            if rmm_context is not None
                            else {}
                        ),
                        "notes": None,
                        "entry_index": idx,
                        "entry_price": float(row.get("close", 0.0)),
                    }
                )
            else:
                if has_open("short"):
                    continue
                if has_open("long"):
                    logger.debug(
                        "Enqueue exit_long before enter_short at idx %s",
                        idx,
                    )
                    intents.append(build_exit_snapshot("long"))
                intents.append(build_snapshot("short"))
        elif command == "exit_long":
            intents.append(build_exit_snapshot("long"))
        elif command == "exit_short":
            intents.append(build_exit_snapshot("short"))

        if logger.isEnabledFor(logging.DEBUG) and (idx < 20 or 90 <= idx <= 110):
            logger.debug(
                "bar %s queued %s new intents",
                idx,
                len(intents),
            )

        pending_intents = intents

        # Track exposure per bar (gross notional)
        exposure_val = 0.0
        if portfolio.active_positions:
            exposure_val = sum(
                abs(view.position.size) * float(row.get("close", 0.0))
                for view in portfolio.active_positions
            )
        exposure_curve.append((bar_timestamp, exposure_val))

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

    # Build equity curve
    # Exposure curve is returned as equity_curve for compatibility with callers
    equity_curve: list[tuple[datetime, float]] = (
        exposure_curve if exposure_curve else []
    )

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
    )
