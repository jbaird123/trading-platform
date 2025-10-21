from __future__ import annotations

import hashlib
import importlib.metadata as ilmd
import json
import logging
import platform
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from statistics import median
from typing import Any

import jsonschema
import numpy as np
import pandas as pd
from pyarrow import ArrowInvalid

from trading_platform.portfolio.metrics import (
    calculate_equity_curve,
    calculate_win_rate,
)
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.analytics import (
    compute_activity,
    compute_contrasts,
    compute_exit_efficiency,
    compute_feature_analysis,
    compute_stationarity,
    compute_stop_tp_candidates,
    compute_timing_buckets,
)

logger = logging.getLogger(__name__)

# Path to the JSON Schema for brief field documentation
SCHEMA_PATH = Path(__file__).parent / "schemas" / "brief.schema.json"


def _extract_rmm_policy(config_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Extract RMM policy information from config snapshot for AI context."""
    if not config_snapshot:
        return {}

    rmm_config = config_snapshot.get("rmm_config", {})
    if not rmm_config:
        return {}

    policy = {
        "name": rmm_config.get("name", "Unknown"),
        "version": rmm_config.get("version", "Unknown"),
        "policy": rmm_config.get("policy", {}),
        "regimes": rmm_config.get("regimes", []),
        "features_used": [
            f.get("name") for f in rmm_config.get("features", []) if f.get("name")
        ],
        "regime_labels": [
            r.get("label") for r in rmm_config.get("regimes", []) if r.get("label")
        ],
        "min_confidence": rmm_config.get("policy", {}).get("min_confidence", None),
        "allowed_labels": rmm_config.get("policy", {}).get("allow_labels", []),
    }

    return policy


def _extract_rem_policy(config_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Extract REM (Risk Exit Manager) policy information from config snapshot
    for AI context."""
    if not config_snapshot:
        return {}

    rem_config = config_snapshot.get("rem_config", {})
    if not rem_config:
        return {}

    policy = {
        "stop_loss": rem_config.get("stop_loss", {}),
        "take_profit": rem_config.get("take_profit", {}),
        "trailing_stop": rem_config.get("trailing_stop", {}),
        "time_exit": rem_config.get("time_exit", {}),
    }

    # Add human-readable interpretations, handling both dict and list-of-dict
    stop_loss_config = rem_config.get("stop_loss")
    take_profit_config = rem_config.get("take_profit")

    # Get the first rule if it's a list
    stop_loss_rule = stop_loss_config
    if isinstance(stop_loss_config, list) and stop_loss_config:
        stop_loss_rule = stop_loss_config[0]

    take_profit_rule = take_profit_config
    if isinstance(take_profit_config, list) and take_profit_config:
        take_profit_rule = take_profit_config[0]

    # Now check the rule if it's a dict
    if isinstance(stop_loss_rule, dict) and stop_loss_rule.get("price_offset"):
        policy["stop_loss_pips"] = f"{stop_loss_rule['price_offset'] * 10000:.0f} pips"

    if isinstance(take_profit_rule, dict) and take_profit_rule.get("price_offset"):
        policy["take_profit_pips"] = (
            f"{take_profit_rule['price_offset'] * 10000:.0f} pips"
        )

    return policy


def _schema_node_type(node: dict[str, Any]) -> str:
    t = node.get("type")
    if isinstance(t, list):
        parts = sorted(map(str, t))
        return "/".join(parts)
    return str(t) if t else "object"


def _lookup_schema(schema: dict[str, Any], path: list[str]) -> dict[str, Any] | None:
    node: dict[str, Any] | None = schema
    for i, seg in enumerate(path):
        if not isinstance(node, dict):
            return None
        props = node.get("properties")
        if isinstance(props, dict) and seg in props:
            node = props[seg]
            continue
        # Support object schemas that use additionalProperties to describe children
        ntype = node.get("type")
        is_object = (isinstance(ntype, str) and ntype == "object") or (
            isinstance(ntype, list) and "object" in ntype
        )
        if is_object and "additionalProperties" in node:
            ap = node.get("additionalProperties")
            if isinstance(ap, dict):
                node = ap
                continue
            return None
        # If no explicit schema for this child and we're at the last segment,
        # return the current node (generic object schema) so long as it has a
        # description. This still enforces schema-provided descriptions.
        if is_object and i == len(path) - 1 and node.get("description"):
            return node
        return None
    return node


def _leaf_paths(obj: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "field_definitions":
                continue
            p = f"{prefix}.{k}" if prefix else k
            paths.extend(_leaf_paths(v, p))
    elif isinstance(obj, list):
        paths.append(prefix)
    else:
        paths.append(prefix)
    return paths


def _round_currency(value: float | None) -> float:
    if value is None:
        return 0.0
    # Use Decimal for correct rounding of currency values
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _round_percentage(value: float | None) -> float | None:
    if value is None:
        return 0.0
    # Round percentages to 3 decimal places
    return float(Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _round_price(value: float | None) -> float | None:
    """Round price values to 4 decimal places.

    Keeps currency (PnL, costs) at 2 decimals while allowing FX-like prices
    to retain finer precision in briefs.
    """
    if value is None:
        return None
    return float(
        Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    )


def _normalize_cost_breakdown(
    data: dict[str, Any] | None,
) -> dict[str, float]:
    base = {"spread": 0.0, "commission": 0.0, "slippage": 0.0}
    if not isinstance(data, dict):
        return base
    normalized: dict[str, float] = {}
    for key, default in base.items():
        raw = float(data.get(key, default) or 0.0)
        normalized[key] = _round_currency(raw)
    return normalized


def _round_feature(name: str, value: Any) -> float | None:
    """Round feature/indicator values based on their type.

    Centralized rounding logic for all technical indicators and features.
    This is the ONLY place where feature rounding should occur - all other
    modules should store full precision floats.
    """
    import math

    if value is None:
        return None

    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None

        name_lower = name.lower()

        # ADX: 2 decimals (percentage-like indicator)
        if "adx" in name_lower:
            return float(
                Decimal(str(f)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )

        # ATR: 6 decimals (price volatility - needs FX precision)
        if "atr" in name_lower:
            return float(
                Decimal(str(f)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            )

        # RSI, Stochastic, CCI: 2 decimals (bounded oscillators)
        if any(x in name_lower for x in ["rsi", "stoch", "cci"]):
            return float(
                Decimal(str(f)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )

        # Volume: whole numbers
        if "volume" in name_lower or "vol" in name_lower:
            return float(Decimal(str(f)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        # EMA, SMA, prices: 4 decimals (for FX precision)
        if any(
            x in name_lower
            for x in ["ema", "sma", "price", "close", "open", "high", "low"]
        ):
            return float(
                Decimal(str(f)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            )

        # MACD, momentum, ROC: 4 decimals
        if any(x in name_lower for x in ["macd", "mom", "roc"]):
            return float(
                Decimal(str(f)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            )

        # Default: 4 decimals
        return float(
            Decimal(str(f)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        )

    except (ValueError, TypeError):
        return None


def _round_dict_features(d: dict[str, Any]) -> dict[str, Any]:
    """Round all numeric values in a dictionary using feature-based rounding."""
    return {
        k: _round_feature(k, v) if isinstance(v, (int, float)) else v
        for k, v in d.items()
    }


def _to_jsonable(obj: Any) -> Any:
    """
    Convert objects to JSON-serializable forms.

    Handles dataclasses, datetimes, numpy types, and other common types.
    """
    # Handle numpy types first
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        # Check for NaN/inf after conversion to Python float
        import math

        val = float(obj)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    if isinstance(obj, np.ndarray):
        return [_to_jsonable(x) for x in obj.tolist()]
    # Handle NaN values for Python floats
    if isinstance(obj, float):
        import math

        if math.isnan(obj):
            return None
        if math.isinf(obj):
            return None
    # asdict() only accepts dataclass instances, not classes.
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, Path):
        return str(obj)
    return obj


# Reusable defaults to reduce duplication in assembled briefs
EMPTY_DISTRIBUTION = {
    "pnl_mean": 0.0,
    "pnl_median": 0.0,
    "pnl_std": 0.0,
    "p05": 0.0,
    "p95": 0.0,
}


def _empty_sections() -> dict[str, Any]:
    """Return fresh containers for always-present empty sections."""
    return {
        "activity": {},
        "timing_buckets": {},
        "costs": {},
        "exposure": {},
        "contrasts": {},
        "stop_tp_candidates": {},
        "exit_efficiency": {},
        "parameter_search": {},
        "stationarity": {},
        "feature_analysis": {},
        "checksums": {},
    }


def _serialize_trade(t: Trade) -> dict[str, Any]:
    """Serialize trade with proper rounding for brief output."""
    # Round context features if present
    context_at_entry = getattr(t, "context_at_entry", None)
    if context_at_entry and isinstance(context_at_entry, dict):
        context_at_entry = {
            k: _round_dict_features(v)
            if isinstance(v, dict) and k == "strategy_features"
            else v
            for k, v in context_at_entry.items()
        }

    context_at_exit = getattr(t, "context_at_exit", None)
    if context_at_exit and isinstance(context_at_exit, dict):
        context_at_exit = {
            k: _round_dict_features(v)
            if isinstance(v, dict) and k == "strategy_features"
            else v
            for k, v in context_at_exit.items()
        }

    # Handle post-exit analysis (supports both old dict and new Pydantic model)
    post_exit = getattr(t, "post_exit_analysis", None)
    if post_exit:
        from trading_platform.reporting.models.exit_analysis import (
            PostExitAnalysis,
        )

        if isinstance(post_exit, PostExitAnalysis):
            # New format: convert Pydantic model to dict with rounding
            post_exit = post_exit.model_dump()
        elif isinstance(post_exit, dict):
            # Legacy format: round MFE/MAE values
            post_exit = {
                horizon: {
                    "mfe": _round_currency(data.get("mfe"))
                    if isinstance(data, dict)
                    else data,
                    "mae": _round_currency(data.get("mae"))
                    if isinstance(data, dict)
                    else data,
                }
                for horizon, data in post_exit.items()
            }

    cost_breakdown = _normalize_cost_breakdown(getattr(t, "cost_breakdown", None))

    return {
        "symbol": t.symbol,
        "side": t.side,
        "size": t.size,
        "entry_time": t.entry_time.isoformat(),
        "exit_time": t.exit_time.isoformat(),
        "entry_price": _round_price(t.entry_price),
        "exit_price": _round_price(t.exit_price),
        "pnl": _round_currency(t.pnl),
        "pnl_movement": _round_currency(getattr(t, "pnl_movement", None)),
        "exit_reason": t.exit_reason,
        "r_multiple": getattr(t, "r_multiple", None),
        "mfe_currency": _round_currency(getattr(t, "mfe_currency", None)),
        "mae_currency": _round_currency(getattr(t, "mae_currency", None)),
        "bars_held": getattr(t, "bars_held", None),
        "context_at_entry": context_at_entry,
        "context_at_exit": context_at_exit,
        "cost_breakdown": cost_breakdown,
        "post_exit_analysis": post_exit,
    }


def compute_overall_performance(
    trades: list[Trade], initial_cash: float
) -> dict[str, Any]:
    equity_curve = calculate_equity_curve(trades, initial_cash)
    final_equity = equity_curve[-1][1] if equity_curve else initial_cash
    pnls = [t.pnl for t in trades]
    total_pnl = sum(pnls) if pnls else 0.0
    mean_pnl = (total_pnl / len(trades)) if trades else 0.0
    median_pnl = median(pnls) if pnls else 0.0

    # Movement PnL and cost breakdown
    total_pnl_movement = sum(t.pnl_movement for t in trades)
    total_costs = sum(t.cost_currency for t in trades)
    total_spread = sum(
        t.cost_breakdown.get("spread", 0.0) for t in trades if t.cost_breakdown
    )
    total_commission = sum(
        t.cost_breakdown.get("commission", 0.0) for t in trades if t.cost_breakdown
    )
    total_slippage = sum(
        t.cost_breakdown.get("slippage", 0.0) for t in trades if t.cost_breakdown
    )

    by_side_total_pnl = {
        "long": sum(t.pnl for t in trades if t.side == "long"),
        "short": sum(t.pnl for t in trades if t.side == "short"),
    }
    return {
        "n_trades": len(trades),
        "total_pnl": _round_currency(total_pnl),
        "total_pnl_movement": _round_currency(total_pnl_movement),
        "total_costs": _round_currency(total_costs),
        "cost_breakdown": {
            "spread": _round_currency(total_spread),
            "commission": _round_currency(total_commission),
            "slippage": _round_currency(total_slippage),
        },
        "mean_pnl": _round_currency(mean_pnl),
        "median_pnl": _round_currency(median_pnl),
        "by_side_total_pnl": {
            "long": _round_currency(by_side_total_pnl["long"]),
            "short": _round_currency(by_side_total_pnl["short"]),
        },
        "win_rate": _round_percentage(calculate_win_rate(trades)),
        "initial_equity": _round_currency(initial_cash),
        "final_equity": _round_currency(final_equity),
    }


def compute_risk_snapshot(trades: list[Trade]) -> dict[str, Any]:
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    wins_movement = [t.pnl_movement for t in trades if t.pnl > 0]
    losses_movement = [t.pnl_movement for t in trades if t.pnl < 0]
    return {
        "win_rate": _round_percentage(calculate_win_rate(trades)),
        "avg_win": _round_currency((sum(wins) / len(wins)) if wins else 0.0),
        "avg_loss": _round_currency((sum(losses) / len(losses)) if losses else 0.0),
        "avg_win_movement": _round_currency(
            (sum(wins_movement) / len(wins_movement)) if wins_movement else 0.0
        ),
        "avg_loss_movement": _round_currency(
            (sum(losses_movement) / len(losses_movement)) if losses_movement else 0.0
        ),
        "max_win": _round_currency(max(wins) if wins else 0.0),
        "max_loss": _round_currency(min(losses) if losses else 0.0),
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return float(values[int(k)])
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return float(d0 + d1)


def compute_distribution(trades: list[Trade]) -> dict[str, Any]:
    pnls = [t.pnl for t in trades]
    if not pnls:
        return EMPTY_DISTRIBUTION
    n = len(pnls)
    mean_val = sum(pnls) / n
    median_val = median(pnls)
    var = sum((x - mean_val) ** 2 for x in pnls) / n
    std = var**0.5
    return {
        "pnl_mean": _round_currency(mean_val),
        "pnl_median": _round_currency(median_val),
        "pnl_std": _round_currency(std),
        "p05": _round_currency(_percentile(pnls, 0.05)),
        "p95": _round_currency(_percentile(pnls, 0.95)),
    }


def compute_streaks(trades: list[Trade]) -> dict[str, Any]:
    longest_win = 0
    longest_loss = 0
    current = 0
    current_sign = 0  # 1 win, -1 loss, 0 none
    for t in trades:
        if t.pnl > 0:
            sign = 1
        elif t.pnl < 0:
            sign = -1
        else:
            sign = 0
        if sign == 0:
            current = 0
            current_sign = 0
        elif sign == current_sign:
            current += 1
        else:
            current = 1
            current_sign = sign
        if current_sign == 1:
            longest_win = max(longest_win, current)
        elif current_sign == -1:
            longest_loss = max(longest_loss, current)
    return {
        "longest_win_streak": longest_win,
        "longest_loss_streak": longest_loss,
        "current_streak": current if current_sign != 0 else 0,
    }


def compute_equity_stats(trades: list[Trade], initial_cash: float) -> dict[str, Any]:
    ec = calculate_equity_curve(trades, initial_cash)
    max_peak = float("-inf")
    dd_curve: list[tuple[datetime, float]] = []
    max_dd = 0.0
    dd_duration = 0
    temp_duration = 0

    # Calculate Sharpe ratio from equity curve
    # Need at least 2 returns (3 equity points) for meaningful std calculation
    equity_values = [float(eq) for _, eq in ec]
    if len(equity_values) >= 3:
        returns = np.diff(equity_values) / equity_values[:-1]
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        # Annualize (assume ~2000 trading periods/year for hourly + blackouts)
        # This is conservative - adjust based on actual trading frequency
        periods_per_year = 2000
        annualized_return = mean_return * periods_per_year
        annualized_std = std_return * np.sqrt(periods_per_year)

        sharpe_ratio = annualized_return / annualized_std if annualized_std > 0 else 0.0
    else:
        # Insufficient data for meaningful Sharpe calculation
        sharpe_ratio = 0.0

    for ts, eq in ec:
        if eq > max_peak:
            max_peak = eq
            temp_duration = 0
        drawdown = max(0.0, max_peak - eq)
        dd_curve.append((ts, drawdown))
        if drawdown > 0:
            temp_duration += 1
            if drawdown > max_dd:
                max_dd = drawdown
                dd_duration = temp_duration
    equity_curve = [[ts.isoformat(), _round_currency(float(eq))] for ts, eq in ec]
    drawdown_curve = [
        [ts.isoformat(), _round_currency(float(dd))] for ts, dd in dd_curve
    ]
    return {
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "max_drawdown": _round_currency(max_dd),
        "dd_duration_bars": dd_duration,
        "sharpe_ratio": round(sharpe_ratio, 2),
    }


def compute_costs_aggregate(trades: list[Trade]) -> dict[str, Any]:
    """Aggregate per-trade costs into totals/averages and breakdown sums.

    If a trade lacks cost fields, it contributes zeros.
    """
    if not trades:
        return {
            "total_costs": 0.0,
            "avg_cost_per_trade": 0.0,
            "breakdown": {"spread": 0.0, "commission": 0.0, "slippage": 0.0},
        }
    total = 0.0
    b_spread = 0.0
    b_comm = 0.0
    b_slip = 0.0
    for t in trades:
        total += getattr(t, "cost_currency", 0.0) or 0.0
        bd = getattr(t, "cost_breakdown", None) or {}
        b_spread += float(bd.get("spread", 0.0) or 0.0)
        b_comm += float(bd.get("commission", 0.0) or 0.0)
        b_slip += float(bd.get("slippage", 0.0) or 0.0)
    return {
        "total_costs": _round_currency(total),
        "avg_cost_per_trade": _round_currency(total / len(trades) if trades else 0.0),
        "breakdown": {
            "spread": _round_currency(b_spread),
            "commission": _round_currency(b_comm),
            "slippage": _round_currency(b_slip),
        },
    }


def _median_holding_secs(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    vals = [max(0.0, (t.exit_time - t.entry_time).total_seconds()) for t in trades]
    return float(median(vals))


def _compute_regimes(
    trades: list[Trade], regimes_at_entry: list[str] | None
) -> dict[str, Any]:
    if not regimes_at_entry or len(regimes_at_entry) != len(trades):
        return {}
    buckets: dict[str, list[float]] = {}
    for t, label in zip(trades, regimes_at_entry):
        buckets.setdefault(label, []).append(t.pnl)
    result: dict[str, Any] = {}
    for label, pnls in buckets.items():
        n = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        result[label] = {
            "n_trades": n,
            "total_pnl": _round_currency(float(sum(pnls))),
            "mean_pnl": _round_currency(float(sum(pnls) / n) if n else 0.0),
            "median_pnl": _round_currency(float(median(pnls)) if pnls else 0.0),
            "win_rate": _round_percentage((wins / n) if n else 0.0),
        }
    return result


def _compute_exposure_metrics(
    exposure_curve: list[tuple[datetime, float]] | None,
) -> dict[str, Any]:
    if not exposure_curve:
        return {}
    values = [float(v) for _, v in exposure_curve]
    if not values:  # defensive redundancy; values is empty only if input was empty
        return {}  # pragma: no cover
    avg = sum(values) / len(values)
    peak = max(values)
    return {
        "average_gross_exposure": _round_currency(avg),
        "peak_gross_exposure": _round_currency(peak),
    }


def generate_brief(
    *,
    meta: dict[str, Any] | None,
    params: dict[str, Any] | None,
    trades: list[Trade],
    initial_cash: float,
    regimes_at_entry: list[str] | None = None,
    data_quality: dict[str, Any] | None = None,
    instrument_definitions: dict[str, Any] | None = None,
    cost_model: dict[str, Any] | None = None,
    fill_policy: dict[str, Any] | None = None,
    tie_break_policy: dict[str, Any] | None = None,
    monte_carlo: dict[str, Any] | None = None,
    walk_forward: dict[str, Any] | None = None,
    blackout_policy: dict[str, Any] | None = None,
    exposure_curve: list[tuple[datetime, float]] | None = None,
    config_snapshot: dict[str, Any] | None = None,
    skipped_trades: list[dict[str, Any]] | None = None,
    parameter_search: dict[str, Any] | None = None,
    field_definitions: dict[str, Any] | None = None,
    signals_path: str | None = None,
    rmm_spans_path: str | None = None,
    processed_data_path: str | None = None,
    recommendations: list[dict[str, Any]] | None = None,
    dynamic_rem_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a JSON brief from trades and metrics (incremental MVP)."""
    meta = meta or {}
    # Use the actual strategy parameters as provided, don't hardcode parameter names
    params = params or {}
    performance = compute_overall_performance(trades, initial_cash)
    risk_snapshot = compute_risk_snapshot(trades)
    equity_stats = compute_equity_stats(trades, initial_cash)
    distribution = compute_distribution(trades)
    trades_json = []
    for t in trades:
        item = _serialize_trade(t)
        item["cost_breakdown"] = _normalize_cost_breakdown(
            getattr(t, "cost_breakdown", None)
        )
        trades_json.append(item)
    # Compute provenance/environment
    prov = _compute_provenance(trades, meta)
    env = _compute_environment()

    exposure = _compute_exposure_metrics(exposure_curve)
    checksums: dict[str, Any] = {}
    if instrument_definitions is not None:
        checksums["instrument_defs_hash"] = _stable_hash(instrument_definitions)
    if config_snapshot is not None:
        checksums["config_snapshot_hash"] = _stable_hash(config_snapshot)

    artifacts: dict[str, Any] = {}
    if signals_path:
        artifacts["signals_path"] = signals_path
    if rmm_spans_path:
        artifacts["rmm_spans_path"] = rmm_spans_path
    if processed_data_path:
        artifacts["processed_data_path"] = processed_data_path

    # --- Model analysis section (placeholder logic) ---
    tp_trades = [t for t in trades if getattr(t, "exit_reason", None) == "take_profit"]
    sl_trades = [t for t in trades if getattr(t, "exit_reason", None) == "stop_loss"]
    avg_pnl_left_on_table_at_tp = (
        sum((getattr(t, "mfe_currency", 0.0) or 0.0) - t.pnl for t in tp_trades)
        / len(tp_trades)
        if tp_trades
        else 0.0
    )
    avg_loss_avoided_by_stop = (
        sum((getattr(t, "mae_currency", 0.0) or 0.0) - abs(t.pnl) for t in sl_trades)
        / len(sl_trades)
        if sl_trades
        else 0.0
    )
    model_analysis = {
        "avg_pnl_left_on_table_at_tp": _round_currency(avg_pnl_left_on_table_at_tp),
        "avg_loss_avoided_by_stop": _round_currency(avg_loss_avoided_by_stop),
    }
    # --- Signal quality analysis section (placeholder logic) ---
    # If signals_path is provided and file exists, try to load signals; else use empty
    import os

    signal_quality_analysis = {
        "signal_persistence_pct": 0.0,
        "avg_signal_duration_bars": 0.0,
    }
    try:
        signals = None
        if signals_path and os.path.exists(signals_path):
            import pandas as pd

            signals = pd.read_parquet(signals_path)
        # Accept Series or DataFrame with 'signal' column
        if signals is not None:
            if isinstance(signals, pd.DataFrame):
                if "signal" not in signals.columns:
                    raise ValueError(
                        "Signal DataFrame must contain 'signal' column. Found columns: "
                        f"{list(signals.columns)}"
                    )
                sig = signals["signal"]
            elif isinstance(signals, pd.Series):
                sig = signals
            else:
                raise ValueError(
                    f"Signals must be pandas DataFrame or Series, got {type(signals)}"
                )

            if sig is not None:
                # For command-based signals: count non-None commands
                # Commands are discrete events that fire once (duration = 1 bar)
                non_none_commands = sig[sig.notna()]
                command_count = len(non_none_commands)

                # Signal persistence = % of bars with actual commands
                signal_persistence_pct = (
                    100.0 * command_count / len(sig) if len(sig) else 0.0
                )

                # Average duration = 1 bar for commands (they fire once)
                # This replaces the old run-length logic for state-based signals
                avg_signal_duration_bars = 1.0 if command_count > 0 else 0.0

                signal_quality_analysis = {
                    "signal_persistence_pct": _round_currency(signal_persistence_pct),
                    "avg_signal_duration_bars": _round_currency(
                        avg_signal_duration_bars
                    ),
                }
    except (OSError, FileNotFoundError, pd.errors.ParserError, ArrowInvalid):
        # Only catch file I/O and parsing errors, let data validation errors propagate
        pass

    # --- Stationarity analysis section ---
    stationarity = compute_stationarity(trades)

    # --- Feature analysis section ---
    feature_analysis = compute_feature_analysis(trades)

    # --- Activity analysis section ---
    activity = compute_activity(trades)

    # --- Timing buckets analysis section ---
    timing_buckets = compute_timing_buckets(trades)

    # --- Contrasts analysis section ---
    contrasts = compute_contrasts(trades)

    # --- Stop/TP candidates analysis section ---
    stop_tp_candidates = compute_stop_tp_candidates(trades)

    # --- Exit efficiency analysis section ---
    exit_efficiency = compute_exit_efficiency(trades)

    # --- Simulated hold analysis (realistic post-exit analysis) ---
    from trading_platform.reporting.aggregators import (
        aggregate_simulated_hold_analysis,
    )

    simulated_hold_analysis = aggregate_simulated_hold_analysis(trades)
    # Add to exit_efficiency dict
    if simulated_hold_analysis.by_hold_period:
        exit_efficiency["simulated_hold_analysis"] = _to_jsonable(
            simulated_hold_analysis.model_dump()
        )

    base = {
        "meta": _to_jsonable(meta),
        "strategy_params": _to_jsonable(params),
        # Canonical, instrument-agnostic sections
        "overall_performance": performance,
        "risk_snapshot": risk_snapshot,
        "equity_stats": equity_stats,
        "distribution": distribution,
        "streaks": compute_streaks(trades),
        "holding_time": {"median_secs": _median_holding_secs(trades)},
        "costs": compute_costs_aggregate(trades),
        "exposure": _to_jsonable(exposure),
        "monte_carlo": _to_jsonable(monte_carlo or {}),
        "walk_forward": _to_jsonable(walk_forward or {}),
        "parameter_search": _to_jsonable(parameter_search or {}),
        "regimes": _compute_regimes(trades, regimes_at_entry),
        "data_quality": _to_jsonable(data_quality or {}),
        "model_analysis": model_analysis,
        "signal_quality_analysis": signal_quality_analysis,
        "stationarity": stationarity,
        "feature_analysis": feature_analysis,
        "activity": activity,
        "timing_buckets": timing_buckets,
        "contrasts": contrasts,
        "stop_tp_candidates": stop_tp_candidates,
        "exit_efficiency": exit_efficiency,
        "dynamic_rem_metrics": _to_jsonable(dynamic_rem_metrics or {}),
        # Snapshots and placeholders (configurable)
        "instrument_definitions": _to_jsonable(instrument_definitions or {}),
        "cost_model": _to_jsonable(cost_model or {}),
        "fill_policy": _to_jsonable(fill_policy or {}),
        "tie_break_policy": _to_jsonable(tie_break_policy or {}),
        "blackout_policy": _to_jsonable(blackout_policy or {}),
        "rmm_policy": _extract_rmm_policy(config_snapshot),
        "rem_policy": _extract_rem_policy(config_snapshot),
        "environment": _to_jsonable(env),
        "provenance": _to_jsonable(prov),
        "checksums": _to_jsonable(checksums),
        "artifacts": _to_jsonable(artifacts),
        "field_definitions": _to_jsonable(field_definitions or {}),
        # Trades serialized with ISO datetimes
        "trades": trades_json,
        "recommendations": _to_jsonable(recommendations or []),
    }

    # Add policy information if available (these are not in schema yet)
    rmm_policy = _extract_rmm_policy(config_snapshot)
    if rmm_policy:
        base["rmm_policy"] = rmm_policy

    rem_policy = _extract_rem_policy(config_snapshot)
    if rem_policy:
        base["rem_policy"] = rem_policy

    placeholders = _empty_sections()
    placeholders.update(base)
    # --- Regime Summary Augmentation ---
    rmm_policy = placeholders.get("rmm_policy", {})
    regimes = rmm_policy.get("regimes", [])
    allowed_labels = rmm_policy.get("allowed_labels", [])
    regime_counts: dict[str, int] = {}
    for trade in placeholders.get("trades", []):
        # Defensive: context_at_entry may be None (schema allows null). Accept
        # either a flat 'regime_label' or a nested 'regime': {"label": ...}.
        ctx = trade.get("context_at_entry") or {}
        regime = None
        if isinstance(ctx, dict):  # pragma: no branch
            regime = ctx.get("regime_label") or (ctx.get("regime") or {}).get("label")
        if regime:  # pragma: no branch
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
    for skip in skipped_trades or []:
        regime = skip.get("regime", {}).get("label")
        if regime:
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
    regime_labels = [r.get("label") for r in regimes if r.get("label")]
    skipped_list = skipped_trades or []
    regime_summary = {
        "regime_labels": regime_labels,
        "allowed_labels": allowed_labels,
        "regime_counts": regime_counts,
        "n_trades": len(placeholders.get("trades", [])),
        "n_skipped_trades": len(skipped_list),
        "n_long": sum(
            1 for t in placeholders.get("trades", []) if t.get("side") == "long"
        ),
        "n_short": sum(
            1 for t in placeholders.get("trades", []) if t.get("side") == "short"
        ),
        "n_long_skipped": sum(1 for s in skipped_list if s.get("side") == "long"),
        "n_short_skipped": sum(1 for s in skipped_list if s.get("side") == "short"),
        "n_allowed_regimes": len(allowed_labels),
        "n_active_regimes": len(set(regime_counts.keys())),
        "n_trades_in_allowed_regimes": sum(
            regime_counts.get(label, 0) for label in allowed_labels
        ),
        "n_trades_in_disallowed_regimes": sum(
            regime_counts.get(label, 0)
            for label in regime_labels
            if label not in allowed_labels
        )
        if regimes
        else 0,
        # 'narrative' intentionally omitted; scenario-specific explanations should
        # be generated dynamically in reporting, not hardcoded in the brief.
    }
    placeholders["regime_summary"] = regime_summary

    # --- Policy Effects Augmentation ---
    policy_effects = {
        # 'rmm_filtering' narrative intentionally omitted; should be generated
        # dynamically in reporting, not hardcoded in the brief.
        "n_trades": len(placeholders.get("trades", [])),
        "n_skipped_trades": len(placeholders.get("skipped_trades", [])),
        "n_long": regime_summary["n_long"],
        "n_short": regime_summary["n_short"],
        "n_long_skipped": regime_summary["n_long_skipped"],
        "n_short_skipped": regime_summary["n_short_skipped"],
    }
    placeholders["policy_effects"] = policy_effects

    # Attach skipped trades before field_definitions so they're included in leaf paths
    skipped_trades = skipped_trades or []
    for trade in skipped_trades:
        if "cf_pnl_currency" in trade:
            trade["cf_pnl_currency"] = _round_currency(trade["cf_pnl_currency"])
    placeholders["skipped_trades"] = _to_jsonable(skipped_trades)

    # Populate field_definitions strictly from the JSON Schema if not provided
    if not field_definitions:
        try:
            schema = json.loads(SCHEMA_PATH.read_text())
        except Exception as e:  # pragma: no cover
            # Safe to continue: schema is for field definitions metadata only
            logger.debug(f"Failed to load brief schema: {e}")
            schema = {}

        # Define wildcard field definitions first (for validation)
        simulated_hold_field_defs = {
            "exit_efficiency.simulated_hold_analysis": (
                "Realistic simulation-based post-exit analysis. Simulates "
                "holding positions longer after exit, accounting for "
                "stop-loss and take-profit triggers. Provides actionable "
                "guidance on whether delayed exits would actually improve "
                "performance."
            ),
            "exit_efficiency.simulated_hold_analysis.by_hold_period": (
                "Analysis results grouped by hold period (e.g., '10', '20', "
                "'50' bars)."
            ),
            "exit_efficiency.simulated_hold_analysis.by_hold_period.*.avg_pnl_change_realistic": (  # noqa: E501
                "Average change in PnL if positions were held this many "
                "extra bars, accounting for stop-loss and take-profit "
                "triggers. Positive means holding longer would have been "
                "profitable."
            ),
            "exit_efficiency.simulated_hold_analysis.by_hold_period.*.avg_mfe_unrealistic": (  # noqa: E501
                "Average Maximum Favorable Excursion during the hold period "
                "(for comparison with old metrics). This is the unrealistic "
                "best-case scenario."
            ),
            "exit_efficiency.simulated_hold_analysis.by_hold_period.*.outcome_distribution": (  # noqa: E501
                "Breakdown of how simulations ended: stop_loss_hit, "
                "take_profit_hit, or held_full_period (percentages)."
            ),
            "exit_efficiency.simulated_hold_analysis.by_hold_period.*.outcome_distribution.stop_loss_hit": (  # noqa: E501
                "Percentage of simulations that ended by hitting the " "stop-loss."
            ),
            "exit_efficiency.simulated_hold_analysis.by_hold_period.*.outcome_distribution.take_profit_hit": (  # noqa: E501
                "Percentage of simulations that ended by hitting the " "take-profit."
            ),
            "exit_efficiency.simulated_hold_analysis.by_hold_period.*.outcome_distribution.held_full_period": (  # noqa: E501
                "Percentage of simulations that were held for the full "
                "period without hitting stops."
            ),
            "exit_efficiency.simulated_hold_analysis.by_hold_period.*.avg_pnl_change_by_original_exit_reason": (  # noqa: E501
                "Average PnL change broken down by the trade's original exit "
                "reason (e.g., 'opposite_signal', 'stop-loss', 'signal')."
            ),
            "exit_efficiency.simulated_hold_analysis.by_hold_period.*.avg_pnl_change_by_original_exit_reason.*": (  # noqa: E501
                "Average PnL change for trades that originally exited with "
                "this specific exit reason."
            ),
        }

        # Helper to check if a path matches a wildcard pattern
        def _matches_wildcard(path: str, pattern: str) -> bool:
            """Check if path matches a wildcard pattern with * placeholders."""
            path_parts = path.split(".")
            pattern_parts = pattern.split(".")
            if len(path_parts) != len(pattern_parts):
                return False
            for pp, pat in zip(path_parts, pattern_parts):
                if pat != "*" and pp != pat:
                    return False
            return True

        fdefs: dict[str, Any] = {}
        for p in _leaf_paths(placeholders):
            parts = p.split(".") if p else []
            node = _lookup_schema(schema, parts)
            if not node or not node.get("description"):
                # Check if path matches any wildcard pattern
                matched = False
                for wildcard_pattern, desc in simulated_hold_field_defs.items():
                    if "*" in wildcard_pattern and _matches_wildcard(
                        p, wildcard_pattern
                    ):
                        fdefs[p] = desc
                        matched = True
                        break
                if not matched:
                    # Strict mode: require schema coverage for every leaf
                    raise ValueError(f"Missing schema description for brief path: {p}")
            else:
                fdefs[p] = node["description"]
        # Add wildcard patterns themselves to fdefs (for documentation)
        fdefs.update(simulated_hold_field_defs)
        placeholders["field_definitions"] = fdefs

    # Omit optional sections when empty to satisfy schema
    if not data_quality:
        placeholders.pop("data_quality", None)
    checks = placeholders.get("checksums")
    if isinstance(checks, dict) and not checks:
        placeholders.pop("checksums", None)

    if skipped_trades:
        # Aggregate impact metrics by skip_reason
        agg: dict[str, Any] = {}
        for s in skipped_trades:
            rc = s.get("skip_reason") or "unknown"
            st = agg.setdefault(
                rc,
                {
                    "n_skipped": 0,
                    "total_cf_pnl": 0.0,
                    "mean_cf_pnl": 0.0,
                    "median_cf_pnl": 0.0,
                },
            )
            st["n_skipped"] += 1
        # Compute totals/means/medians for cf_pnl where present
        from statistics import median as _med

        for rc, st in agg.items():
            vals = [
                float(s.get("cf_pnl_currency", 0.0))
                for s in skipped_trades
                if (s.get("skip_reason") or "unknown") == rc
            ]
            st["total_cf_pnl"] = _round_currency(float(sum(vals)))
            st["mean_cf_pnl"] = _round_currency(
                float(sum(vals) / len(vals)) if vals else 0.0
            )
            st["median_cf_pnl"] = _round_currency(float(_med(vals)) if vals else 0.0)
        placeholders["filter_impact"] = agg
    return placeholders


def _numpy_json_encoder(obj: Any) -> Any:
    """
    Custom JSON encoder for numpy types.

    Converts numpy integer and float types to Python native types
    for JSON serialization.
    """
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def save_brief(brief: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(brief, indent=2, default=_numpy_json_encoder))


def save_run_brief(
    run_path: Path,
    *,
    meta: dict[str, Any],
    params: dict[str, Any],
    trades: list[Trade],
    initial_cash: float,
    regimes_at_entry: list[str] | None = None,
    data_quality: dict[str, Any] | None = None,
    instrument_definitions: dict[str, Any] | None = None,
    cost_model: dict[str, Any] | None = None,
    fill_policy: dict[str, Any] | None = None,
    tie_break_policy: dict[str, Any] | None = None,
    monte_carlo: dict[str, Any] | None = None,
    walk_forward: dict[str, Any] | None = None,
    blackout_policy: dict[str, Any] | None = None,
    exposure_curve: list[tuple[datetime, float]] | None = None,
    config_snapshot: dict[str, Any] | None = None,
    parameter_search: dict[str, Any] | None = None,
    skipped_trades: list[dict[str, Any]] | None = None,
    signals_path: str | None = None,
    rmm_spans_path: str | None = None,
    processed_data_path: str | None = None,
    validate_schema: bool = False,
    recommendations: list[dict[str, Any]] | None = None,
    field_definitions: dict[str, Any] | None = None,
) -> Path:
    """Generate and save a brief to `run_path/brief.json`.

    Returns the written path.
    """
    brief = generate_brief(
        meta=meta,
        params=params,
        trades=trades,
        initial_cash=initial_cash,
        regimes_at_entry=regimes_at_entry,
        data_quality=data_quality,
        instrument_definitions=instrument_definitions,
        cost_model=cost_model,
        fill_policy=fill_policy,
        tie_break_policy=tie_break_policy,
        monte_carlo=monte_carlo,
        walk_forward=walk_forward,
        blackout_policy=blackout_policy,
        exposure_curve=exposure_curve,
        config_snapshot=config_snapshot,
        parameter_search=parameter_search,
        skipped_trades=skipped_trades,
        signals_path=signals_path,
        rmm_spans_path=rmm_spans_path,
        processed_data_path=processed_data_path,
        recommendations=recommendations,
        field_definitions=field_definitions,
    )
    if validate_schema:
        try:
            schema = json.loads(SCHEMA_PATH.read_text())
            jsonschema.validate(instance=brief, schema=schema)
        except Exception as exc:  # pragma: no cover (error path)
            raise ValueError(f"Brief failed schema validation: {exc}") from exc
    out_path = run_path / "brief.json"
    save_brief(brief, out_path)
    return out_path


def compute_data_quality(df: pd.DataFrame) -> dict[str, Any]:
    """Return a simple data-quality snapshot for an OHLCV DataFrame.

    - Index monotonic increasing
    - Duplicate index count
    - NaN counts per column
    """
    result: dict[str, Any] = {}
    result["index_monotonic_increasing"] = bool(df.index.is_monotonic_increasing)
    result["duplicate_bars_count"] = int(df.index.duplicated().sum())
    nan_counts = {col: int(df[col].isna().sum()) for col in df.columns}
    result["nan_counts"] = nan_counts
    result["has_nans"] = any(nan_counts.values())

    # Task 2.1–2.4: Add quality_score
    score = 1.0
    if result["has_nans"]:
        score -= 0.5
    duplicate_penalty = min(0.5, result["duplicate_bars_count"] / 1000.0)
    score -= duplicate_penalty
    score = max(0.0, score)
    result["quality_score"] = score
    return result


def _compute_environment() -> dict[str, Any]:
    tz = datetime.now().astimezone().tzinfo

    def _ver(pkg: str) -> str | None:
        try:
            return ilmd.version(pkg)
        except Exception as e:  # pragma: no cover
            # Safe to continue: package version is metadata only
            logger.debug(f"Failed to get version for {pkg}: {e}")
            return None

    return {
        "python_version": sys.version.split(" ")[0],
        "platform": platform.platform(),
        "timezone": str(tz) if tz else None,
        "dependency_versions": {
            "pandas": _ver("pandas"),
            "pydantic": _ver("pydantic"),
        },
    }


def _compute_provenance(trades: list[Trade], meta: dict[str, Any]) -> dict[str, Any]:
    # Derive minimal provenance from trades and meta
    symbols = sorted({t.symbol for t in trades})
    data_start = min((t.entry_time for t in trades), default=None)
    data_end = max((t.exit_time for t in trades), default=None)
    meta = meta or {}
    try:
        app_version = ilmd.version("trading-platform")
    except Exception as e:  # pragma: no cover
        # Safe to continue: app version is metadata only
        logger.debug(f"Failed to get trading-platform version: {e}")
        app_version = None
    return {
        "run_id": meta.get("run_id"),
        "strategy_name": meta.get("strategy_name"),
        "data_start": data_start.isoformat() if data_start else None,
        "data_end": data_end.isoformat() if data_end else None,
        "symbols": symbols,
        "app_version": app_version,
        "git_commit": meta.get("git_commit"),
        "run_seed": meta.get("run_seed"),
    }


def _stable_hash(obj: Any) -> str:
    jsonable = _to_jsonable(obj)
    s = json.dumps(jsonable, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
