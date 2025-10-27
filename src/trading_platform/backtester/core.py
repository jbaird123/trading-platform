from __future__ import annotations

import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd

from trading_platform.core.config import RunConfig
from trading_platform.core.policy import TradingWindowPolicy
from trading_platform.core.signal import Signal
from trading_platform.core.types import SignalCommand
from trading_platform.core.utils import normalize_symbol
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.portfolio.trade import Trade
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy

"""Backtester core loop with optional exposure capture.

When `return_exposure` is True, returns `(trades, exposure_curve)`; otherwise
returns just `trades`.
"""

logger = logging.getLogger(__name__)


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


def run_backtest(
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
) -> (
    list[Trade]
    | tuple[list[Trade], list[tuple[datetime, float]]]
    | tuple[list[Trade], list[tuple[datetime, float]], list[dict[str, Any]]]
):
    """
    Runs a simple, iterative (bar-by-bar) backtest to generate trades from signals.

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

    # Compute global features from config/features/global.yaml
    data_with_global_features = market_data
    global_features_list = []
    try:
        from trading_platform.core.feature_resolver import resolve_global_features
        from trading_platform.strategy.features import compute_features

        # Get execution timeframe from config
        instrument_cfg = config.instrument or {}
        execution_timeframe = instrument_cfg.get("timeframe", "1H")

        # Resolve global features (filtered by timeframe)
        resolved_features = resolve_global_features(
            execution_timeframe, config_path=global_features_config_path
        )

        # Convert ResolvedFeature objects to dict format for compute_features
        # NOTE: Only include timeframe if it's HIGHER than execution timeframe
        # to trigger resampling. If timeframe == execution_timeframe, omit it
        # to compute directly on market_data (matching old behavior)
        global_features_list = [
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
            for f in resolved_features
        ]

        if global_features_list:
            data_with_global_features = compute_features(
                market_data, global_features_list, strategy_parameters={}
            )
            logger.info(
                f"Computed {len(global_features_list)} global features: "
                f"{[f['name'] for f in global_features_list]}"
            )

            # Validate: Check first bar for NaN values in global features
            # If any indicators are NaN at backtest start, warmup is insufficient
            def _validate_no_nan_features():
                if len(data_with_global_features) > 0:
                    first_bar = data_with_global_features.iloc[0]
                    nan_features = []
                    for feature in global_features_list:
                        feature_name = feature.get("name")
                        if (
                            feature_name
                            and isinstance(feature_name, str)
                            and feature_name in first_bar.index
                        ):
                            val = first_bar[feature_name]
                            if pd.isna(val):
                                nan_features.append(feature_name)

                    if nan_features:
                        raise ValueError(  # noqa: TRY301
                            f"Insufficient warmup: The following global features "
                            f"have NaN values at backtest start ({first_bar.name}): "
                            f"{nan_features}. Indicators are not fully initialized. "
                            f"Load data from an earlier start date to allow warmup."
                        )

            _validate_no_nan_features()

    except FileNotFoundError:
        # global.yaml doesn't exist - this is okay, just log it
        logger.info("No global.yaml found - proceeding without global features")
    except ValueError:
        # Re-raise ValueError (e.g., insufficient warmup) - should fail backtest
        raise
    except Exception as e:
        # Log but don't fail the backtest if global features fail (other errors)
        logger.warning(f"Failed to load global features: {e}")

    from typing import cast

    global_feature_names: set[str] = {
        cast(str, f["name"]) for f in global_features_list
    }

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

    warmup_threshold = max(0, config.warmup_bars)

    # Pending actions for next_bar_open execution model
    pending_exit: dict[str, Any] | None = None
    pending_entry: dict[str, Any] | None = None

    for i in range(len(market_data)):
        signal = signals.iloc[i]
        current_bar = market_data.iloc[i]
        prior_bar = market_data.iloc[i - 1] if i > 0 else None

        # === EXECUTION PHASE: Execute pending actions ===
        # Execute pending exit from previous bar (next_bar_open model)
        if pending_exit is not None:
            portfolio.close_position(
                exit_price=current_bar["open"],
                exit_time=cast(datetime, current_bar.name),
                exit_reason=pending_exit["reason"],
                context_at_exit=pending_exit.get("context"),
            )
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
                    "context": pending_exit.get("context"),
                }
            pending_exit = None

        # Execute pending entry from previous bar (next_bar_open model)
        if pending_entry is not None:
            # Calculate initial stop loss price for r_multiple calculation
            entry_price = current_bar["open"]
            initial_risk_ccy = None
            if rem is not None:
                stop_price = rem.calculate_initial_stop_price(
                    entry_price=entry_price,
                    side=pending_entry["side"],
                    entry_bar=current_bar,
                    signal_context=pending_entry.get("context", {}),
                    prior_bar=prior_bar,
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
                entry_time=cast(datetime, current_bar.name),
                instrument=pending_entry["instrument"],
                context_at_entry=pending_entry.get("context"),
                initial_risk_ccy=initial_risk_ccy,
            )
            # Mark that we've entered on this entry window
            portfolio._entry_windows[pending_entry["side"]] = (
                portfolio._entry_windows[pending_entry["side"]][0],
                i,
            )
            pending_entry = None

        # Extract command and context from Signal object (or use legacy format)
        if isinstance(signal, Signal):
            command = signal.command
            # Merge signal context with strategy context
            strategy_context = strategy.get_context(i)
            strategy_features = {**strategy_context, **signal.context}
        else:
            # Legacy format: signal is just a command string
            command = signal
            strategy_features = strategy.get_context(i)

        # Build global features dict separately from strategy features
        global_features: dict[str, Any] = {}
        if global_feature_names and data_with_global_features is not market_data:
            for feature_name in global_feature_names:
                if feature_name in data_with_global_features.columns:
                    val = data_with_global_features[feature_name].iloc[i]
                    # Convert NaN to None for JSON serialization
                    if isinstance(val, float) and math.isnan(val):
                        global_features[feature_name] = None
                    else:
                        global_features[feature_name] = val

        # Always include raw volume in global features (market context)
        global_features["volume"] = current_bar["volume"]

        # Build consistent nested context structure
        # Separate strategy_features and global_features for semantic clarity
        regime_data = None
        if rmm_context is not None:
            rmm_ctx = rmm_context.get(cast(datetime, current_bar.name))
            regime_data = _build_regime_data(rmm_ctx)

        context = {
            "strategy_features": strategy_features,
            "global_features": global_features,
        }
        if regime_data is not None:
            context["regime"] = regime_data

        # === REM EXIT PHASE: Check risk-based exits ===
        # REM exits (stop-loss, take-profit) are ALWAYS executed immediately
        # at the intra-bar price when hit, regardless of execution_model.
        # This is realistic behavior - protective orders execute intra-bar.
        # The execution_model setting only applies to signal-based entries/exits.
        if portfolio.current_position and rem is not None:
            rem_result = rem.check_exits_intrabar(
                portfolio.current_position,
                current_bar,
                data_handler=data_handler,
                prior_bar=prior_bar,
            )

            if rem_result is not None and rem_result["action"] == "should_close":
                # ALWAYS execute REM exits immediately at intra-bar price
                # Stop-loss and take-profit orders don't wait for bar close
                portfolio.close_position(
                    exit_price=rem_result["exit_price"],
                    exit_time=cast(datetime, current_bar.name),
                    exit_reason=rem_result["reason"],
                    context_at_exit=context,
                )
                if return_exposure:
                    exposure_curve.append((cast(datetime, current_bar.name), 0.0))
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
                    exit_time=cast(datetime, current_bar.name),
                    exit_reason=result["reason"],
                    context_at_exit=context,
                )
                if return_exposure:
                    exposure_curve.append((cast(datetime, current_bar.name), 0.0))

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
                and policy.can_open(cast(datetime, current_bar.name))
            ):
                # Enforce RMM side gating if provided
                if rmm_context is not None:
                    ctx = rmm_context.get(cast(datetime, current_bar.name))
                    if ctx is not None:
                        allowed_sides = list(ctx.get("allowed_sides") or [])
                        regime_snapshot = _build_regime_data(ctx)
                        if side not in allowed_sides:
                            skipped.append(
                                {
                                    "entry_time": _fmt_ts(current_bar.name),
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
                    now = cast(datetime, current_bar.name)
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
                            "entry_time": _fmt_ts(current_bar.name),
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
                        if rem is not None:
                            stop_price = rem.calculate_initial_stop_price(
                                entry_price=entry_price,
                                side=side,
                                entry_bar=current_bar,
                                signal_context=context,
                                prior_bar=prior_bar,
                            )
                            if stop_price is not None:
                                # initial_risk_ccy = distance * size
                                initial_risk_ccy = abs(entry_price - stop_price) * size

                        portfolio.create_new_position(
                            symbol=symbol,
                            side=side,
                            entry_price=entry_price,
                            size=size,
                            entry_time=cast(datetime, current_bar.name),
                            instrument=instrument_dict,
                            context_at_entry=context,
                            initial_risk_ccy=initial_risk_ccy,
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
                        }

            elif not policy.can_open(
                cast(datetime, current_bar.name)
            ):  # pragma: no cover
                # Entry window open but blackout period active
                # pragma: no cover - Defensive: blackout blocks entry at line 269
                reason = (
                    policy.reason(cast(datetime, current_bar.name)) or "blackout"
                )  # pragma: no cover
                snap = {
                    "blackout_utc": config.blackout_utc or [],
                    "blackout_events": config.blackout_events or [],
                }
                skipped.append(
                    {
                        "entry_time": _fmt_ts(current_bar.name),
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
            exposure_curve.append((cast(datetime, current_bar.name), exposure_val))

    # Force-close any remaining open position at end of backtest
    if portfolio.current_position:
        last_bar = market_data.iloc[-1]
        portfolio.close_position(
            exit_price=last_bar["close"],
            exit_time=cast(datetime, market_data.index[-1]),
            exit_reason="end_of_data",
            context_at_exit=None,
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
                )
            s.update(cf)

    # Post-exit analysis: track price movement after each trade closes
    post_exit_cfg = getattr(config, "post_exit_analysis", None)
    if post_exit_cfg and post_exit_cfg.get("enabled"):
        _enrich_trades_with_post_exit_analysis(
            portfolio.trades, market_data, post_exit_cfg.get("horizons", [10, 20, 50])
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
    if rem is not None:
        stop_price = rem.calculate_initial_stop_price(
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
            exit_details = rem.check_exits(
                pm.current_position, cb, data_handler=data_handler, prior_bar=prior_bar
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
