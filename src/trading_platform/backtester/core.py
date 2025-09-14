from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pandas as pd

from trading_platform.core.policy import TradingWindowPolicy
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.portfolio.trade import Trade

"""Backtester core loop with optional exposure capture.

When `return_exposure` is True, returns `(trades, exposure_curve)`; otherwise
returns just `trades`.
"""


def run_backtest(
    market_data: pd.DataFrame,
    signals: pd.Series,
    initial_cash: float = 100000.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    allow_flip_on_bar: bool = False,
    instrument: dict | None = None,
    blackout_utc: list[tuple[str, str]] | None = None,
    blackout_events: list[dict[str, Any]] | None = None,
    warmup_bars: int = 0,
    cost_model: dict | None = None,
    return_exposure: bool = False,
    return_skips: bool = False,
    pm_limits: dict[str, int] | None = None,
    daily_loss_cap: float | None = None,
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
        initial_cash: The starting cash for the portfolio.
        stop_loss: Optional stop-loss price for new positions.
        take_profit: Optional take-profit price for new positions.
        allow_flip_on_bar: If True, allows closing a position and opening a new
                           one on the same bar. Defaults to False.

    Returns:
        A list of completed Trade objects.
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

    # Accept optional instrument snapshot; do not change PnL behavior yet.
    portfolio = PortfolioManager(
        initial_cash=initial_cash, instrument=instrument, cost_model=cost_model
    )

    policy = TradingWindowPolicy.from_config(
        blackout_utc=blackout_utc, blackout_events=blackout_events
    )

    # Track gross exposure per bar (absolute notional = |size * close|)
    exposure_curve: list[tuple[datetime, float]] = []
    skipped: list[dict[str, Any]] = []
    limits = pm_limits or {"max_open_long": 1, "max_open_short": 1}

    def _fmt_ts(val: Any) -> str:
        return val.isoformat() if isinstance(val, datetime) else str(val)

    for i in range(len(market_data)):
        current_signal = signals.iloc[i]
        current_bar = market_data.iloc[i]

        # The backtester's job is to orchestrate, not to decide.
        # It passes the current state to the PortfolioManager, which
        # contains the actual position management logic.
        portfolio.on_bar(
            current_bar=current_bar,
            current_signal=current_signal,
            allow_flip_on_bar=allow_flip_on_bar,
        )

        # If trying to add in same direction while already open, enforce cap
        if portfolio.current_position and current_signal in ["long", "short"]:
            cap_now = (
                limits.get("max_open_long", 1)
                if current_signal == "long"
                else limits.get("max_open_short", 1)
            )
            open_ct = 1  # PM supports one open position in MVP
            if open_ct >= cap_now:
                skipped.append(
                    {
                        "timestamp": _fmt_ts(current_bar.name),
                        "symbol": "EUR_USD",
                        "reason_code": "position_cap",
                        "policy_snapshot": {"cap": cap_now},
                        "notes": None,
                    }
                )

        # Potentially open a new position based on signal and policy
        if (
            not portfolio.current_position
            and current_signal in ["long", "short"]
            and policy.can_open(cast(datetime, current_bar.name))
            and i >= max(0, warmup_bars)
        ):
            # Enforce daily loss cap using PortfolioManager state
            if daily_loss_cap is not None and daily_loss_cap > 0:
                now = cast(datetime, current_bar.name)
                if portfolio.hit_daily_loss_cap(now, float(daily_loss_cap)):
                    skipped.append(
                        {
                            "timestamp": _fmt_ts(now),
                            "symbol": "EUR_USD",
                            "reason_code": "risk_cap",
                            "policy_snapshot": {
                                "daily_loss_cap": float(daily_loss_cap)
                            },
                            "notes": None,
                            "side": current_signal,
                            "entry_index": i,
                            "entry_price": float(current_bar["close"]),
                        }
                    )
                    continue
            # Enforce simple directional cap (PM holds at most one position)
            cap = (
                limits.get("max_open_long", 1)
                if current_signal == "long"
                else limits.get("max_open_short", 1)
            )
            open_ct = 1 if portfolio.current_position else 0
            if open_ct >= cap:
                skipped.append(
                    {
                        "timestamp": _fmt_ts(current_bar.name),
                        "symbol": "EUR_USD",
                        "reason_code": "position_cap",
                        "policy_snapshot": {"cap": cap},
                        "notes": None,
                        "side": current_signal,
                        "entry_index": i,
                        "entry_price": float(current_bar["close"]),
                    }
                )
            else:
                portfolio.create_new_position(
                    symbol="EUR_USD",
                    side=current_signal,
                    entry_price=current_bar["close"],
                    size=10000,
                    entry_time=cast(datetime, current_bar.name),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    instrument=instrument,
                )
        elif (
            not portfolio.current_position
            and current_signal in ["long", "short"]
            and not policy.can_open(cast(datetime, current_bar.name))
        ):
            # Log blackout skip
            reason = policy.reason(cast(datetime, current_bar.name)) or "blackout"
            snap = {
                "blackout_utc": blackout_utc or [],
                "blackout_events": blackout_events or [],
            }
            skipped.append(
                {
                    "timestamp": _fmt_ts(current_bar.name),
                    "symbol": "EUR_USD",
                    "reason_code": reason,
                    "policy_snapshot": snap,
                    "notes": None,
                    "side": current_signal,
                    "entry_index": i,
                    "entry_price": float(current_bar["close"]),
                }
            )

        # Capture gross exposure for this bar AFTER applying entries/exits
        pos = portfolio.current_position
        exposure_val = 0.0
        if pos is not None:
            exposure_val = float(abs(pos.size) * float(current_bar["close"]))
        exposure_curve.append((cast(datetime, current_bar.name), exposure_val))

    # Counterfactual simulation for each skipped entry (backtest-only)
    if skipped:
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
            cf = _simulate_counterfactual(
                market_data,
                start_index=si,
                side=side,
                entry_price=entry_px,
                size=10000.0,
                stop_loss=stop_loss,
                take_profit=take_profit,
                instrument=instrument,
                cost_model=cost_model,
            )
            s.update(cf)

    if return_exposure and return_skips:
        return (portfolio.trades, exposure_curve, skipped)
    if return_exposure:
        return (portfolio.trades, exposure_curve)
    if return_skips:
        return (portfolio.trades, [], skipped)
    return portfolio.trades


def _simulate_counterfactual(
    market_data: pd.DataFrame,
    *,
    start_index: int,
    side: str,
    entry_price: float,
    size: float,
    stop_loss: float | None,
    take_profit: float | None,
    instrument: dict | None,
    cost_model: dict | None,
) -> dict[str, Any]:
    pm = PortfolioManager(
        initial_cash=0.0, instrument=instrument, cost_model=cost_model
    )
    entry_time = cast(datetime, market_data.index[start_index])
    pm.create_new_position(
        symbol="EUR_USD",
        side=side,
        entry_price=entry_price,
        size=size,
        entry_time=entry_time,
        stop_loss=stop_loss,
        take_profit=take_profit,
        instrument=instrument,
    )
    # Step forward including the entry bar to allow immediate TP/SL hits
    for i in range(start_index, len(market_data)):
        pm.on_bar(current_bar=market_data.iloc[i], current_signal=side)
        if not pm.current_position:
            break
    # If still open at end, close at last bar close
    if pm.current_position:
        last_idx = len(market_data) - 1
        pm.close_position(
            exit_price=float(market_data.iloc[last_idx]["close"]),
            exit_time=cast(datetime, market_data.index[last_idx]),
        )
    if not pm.trades:
        return {}
    t = pm.trades[0]
    return {
        "cf_exit_time": t.exit_time.isoformat(),
        "cf_exit_price": float(t.exit_price),
        "cf_pnl_currency": float(t.pnl),
        "cf_mfe_currency": float(t.mfe_currency or 0.0),
        "cf_mae_currency": float(t.mae_currency or 0.0),
        "cf_bars_held": int(t.bars_held or 0),
    }
