from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pandas as pd

from trading_platform.core.config import RunConfig
from trading_platform.core.policy import TradingWindowPolicy
from trading_platform.core.utils import normalize_symbol
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.portfolio.trade import Trade
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy

"""Backtester core loop with optional exposure capture.

When `return_exposure` is True, returns `(trades, exposure_curve)`; otherwise
returns just `trades`.
"""


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

    return normalize_symbol(str(symbol))


def run_backtest(
    market_data: pd.DataFrame,
    signals: pd.Series,
    strategy: CompiledStrategy,
    config: RunConfig,
    rem: RiskExitManager,
    rmm_context: dict[datetime, dict[str, Any]] | None = None,
    return_exposure: bool = False,
    return_skips: bool = False,
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

    allowed = {"long", "short", "flat"}
    invalid_values = set(pd.Series(signals).astype(str).unique()) - allowed
    if invalid_values:
        raise ValueError(f"signals contain invalid values: {sorted(invalid_values)}")

    if market_data["close"].isna().any():
        first_bad = market_data[market_data["close"].isna()].index[0]
        raise ValueError(f"market_data.close has NaNs; first at index: {first_bad}")

    symbol = resolve_instrument_symbol(config.instrument)

    portfolio = PortfolioManager(
        initial_cash=config.initial_cash,
        instrument=config.instrument,
        cost_model=config.cost_model,
    )

    policy = TradingWindowPolicy.from_config(
        blackout_utc=config.blackout_utc, blackout_events=config.blackout_events
    )

    exposure_curve: list[tuple[datetime, float]] = []
    skipped: list[dict[str, Any]] = []
    limits = config.pm_limits or {"max_open_long": 1, "max_open_short": 1}
    # Use the provided RiskExitManager instance; do not override it here.

    def _fmt_ts(val: Any) -> str:
        return val.isoformat() if isinstance(val, datetime) else str(val)

    prev_signal = "flat"  # Track previous signal for transition detection
    warmup_threshold = max(0, config.warmup_bars)
    for i in range(len(market_data)):
        current_signal = signals.iloc[i]
        current_bar = market_data.iloc[i]
        context = strategy.get_context(i)

        # Detect signal transitions
        # Treat first bar after warmup as a transition to allow entry
        signal_changed = (current_signal != prev_signal) or (i == warmup_threshold and current_signal in ["long", "short"])
        
        # Enrich context with regime information from RMM if available
        if rmm_context is not None:
            rmm_ctx = rmm_context.get(cast(datetime, current_bar.name))
            if rmm_ctx is not None:
                # Create a copy to avoid modifying the original strategy context
                context = dict(context or {})
                context["regime_label"] = rmm_ctx.get("label")

        # Evaluate risk-based exits using the Risk & Exit Manager (REM)
        # This is evaluated before strategic exits, per the Exit Precedence Policy.
        if portfolio.current_position:
            exit_details = rem.check_exits(portfolio.current_position, current_bar)

            if exit_details:
                portfolio.close_position(
                    exit_price=exit_details["exit_price"],
                    exit_time=cast(datetime, current_bar.name),
                    exit_reason=exit_details["reason"],
                    context_at_exit=context,
                )
                # Update exposure only if requested
                if return_exposure:
                    exposure_curve.append((cast(datetime, current_bar.name), 0.0))
                continue

        # Process signal-based exits and update position metrics
        portfolio.on_bar(
            current_bar=current_bar,
            current_signal=current_signal,
            allow_flip_on_bar=config.allow_flip_on_bar,
            context=context,
        )

        # If trying to add in same direction while already open, enforce cap
        if portfolio.current_position and current_signal in ["long", "short"]:
            cap_now = (
                limits.get("max_open_long", 1)
                if current_signal == "long"
                else limits.get("max_open_short", 1)
            )
            open_ct = 1
            if open_ct >= cap_now:
                skipped.append(
                    {
                        "entry_time": _fmt_ts(current_bar.name),
                        "symbol": symbol,
                        "side": current_signal,
                        "size": float(config.position_size),
                        "skip_reason": "position_cap",
                        "counterfactual_pnl": 0.0,
                        "counterfactual_mfe_currency": 0.0,
                        "counterfactual_mae_currency": 0.0,
                        "policy_snapshot": {"cap": cap_now},
                        "notes": None,
                    }
                )

        # Potentially open a new position based on signal and policy
        # Only enter on signal transitions to prevent re-entry on persistent signals
        if (
            not portfolio.current_position
            and current_signal in ["long", "short"]
            and signal_changed  # NEW: Only enter when signal changes
            and policy.can_open(cast(datetime, current_bar.name))
            and i >= max(0, config.warmup_bars)
        ):
            # Enforce RMM side gating if provided
            if rmm_context is not None:
                ctx = rmm_context.get(cast(datetime, current_bar.name))
                if ctx is not None:
                    allowed_sides = list(ctx.get("allowed_sides") or [])
                    if current_signal not in allowed_sides:
                        skipped.append(
                            {
                                "entry_time": _fmt_ts(current_bar.name),
                                "symbol": symbol,
                                "side": current_signal,
                                "size": float(config.position_size),
                                "skip_reason": "rmm_block",
                                "counterfactual_pnl": 0.0,
                                "counterfactual_mfe_currency": 0.0,
                                "counterfactual_mae_currency": 0.0,
                                "regime": {
                                    "label": ctx.get("label"),
                                    "confidence": ctx.get("confidence"),
                                },
                                "policy_snapshot": {
                                    "allowed_sides": allowed_sides,
                                    "min_confidence": (
                                        (ctx.get("policy") or {}).get("min_confidence")
                                    ),
                                },
                                "notes": None,
                                "entry_index": i,
                                "entry_price": float(current_bar["close"]),
                            }
                        )
                        continue
            if config.daily_loss_cap is not None and config.daily_loss_cap > 0:
                now = cast(datetime, current_bar.name)
                if portfolio.hit_daily_loss_cap(now, float(config.daily_loss_cap)):
                    skipped.append(
                        {
                            "entry_time": _fmt_ts(now),
                            "symbol": symbol,
                            "side": current_signal,
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
            cap = (
                limits.get("max_open_long", 1)
                if current_signal == "long"
                else limits.get("max_open_short", 1)
            )
            open_ct = 1 if portfolio.current_position else 0
            if open_ct >= cap:
                skipped.append(
                    {
                        "entry_time": _fmt_ts(current_bar.name),
                        "symbol": symbol,
                        "side": current_signal,
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
                entry_price = current_bar["close"]
                size = float(config.position_size)

                portfolio.create_new_position(
                    symbol=symbol,
                    side=current_signal,
                    entry_price=entry_price,
                    size=size,
                    entry_time=cast(datetime, current_bar.name),
                    instrument=config.instrument,
                    context_at_entry=context,
                    initial_risk_ccy=None,  # This is now handled by REM
                )
        elif (
            not portfolio.current_position
            and current_signal in ["long", "short"]
            and not policy.can_open(cast(datetime, current_bar.name))
        ):
            reason = policy.reason(cast(datetime, current_bar.name)) or "blackout"
            snap = {
                "blackout_utc": config.blackout_utc or [],
                "blackout_events": config.blackout_events or [],
            }
            skipped.append(
                {
                    "entry_time": _fmt_ts(current_bar.name),
                    "symbol": symbol,
                    "side": current_signal,
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

        # Update previous signal for next iteration
        prev_signal = current_signal

    if skipped:
        # Choose counterfactual mode
        mode = getattr(config, "counterfactual_mode", "fast") or "fast"
        use_fast = True if mode == "fast" else False

        for s in skipped:
            val = s.get("entry_index")
            if isinstance(val, int):
                si = val
            else:
                try:
                    si = int(str(val))
                except Exception:
                    continue
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
                    instrument=config.instrument,
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
                    instrument=config.instrument,
                    cost_model=config.cost_model,
                    rem=rem,
                    symbol=symbol,
                )
            s.update(cf)

    if return_exposure and return_skips:
        return (portfolio.trades, exposure_curve, skipped)
    if return_exposure:
        return (portfolio.trades, exposure_curve)
    if return_skips:
        return (portfolio.trades, [], skipped)
    return portfolio.trades


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
        "counterfactual_pnl": pnl_net,
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
) -> dict[str, Any]:
    """Exact counterfactual: bar-by-bar re-simulation with REM."""
    if start_index < 0 or start_index >= len(market_data):
        return {}

    pm = PortfolioManager(
        initial_cash=0.0, instrument=instrument, cost_model=cost_model
    )
    entry_time = cast(datetime, market_data.index[start_index])
    pm.create_new_position(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        size=size,
        entry_time=entry_time,
        instrument=instrument,
        initial_risk_ccy=None,
    )

    bars_touched = 0
    rem_exit = False
    for i in range(start_index, len(market_data)):
        cb = market_data.iloc[i]
        bars_touched += 1
        # Apply REM exits first for fidelity
        if pm.current_position:
            exit_details = rem.check_exits(pm.current_position, cb)
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
        "counterfactual_pnl": float(t.pnl),
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
