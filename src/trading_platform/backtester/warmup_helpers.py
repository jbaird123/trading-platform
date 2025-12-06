from __future__ import annotations

# ruff: noqa: TRY301
import logging
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pandas as pd

from trading_platform.core.feature_resolver import resolve_global_features
from trading_platform.strategy.features import _resolve_parameter

logger = logging.getLogger(__name__)


def infer_execution_timeframe(config: Any, market_data: pd.DataFrame) -> str:
    instrument_cfg = getattr(config, "instrument", None) or {}
    if isinstance(instrument_cfg, dict):
        instrument_tf = instrument_cfg.get("timeframe")
    else:
        instrument_tf = getattr(instrument_cfg, "timeframe", None)
    data_req_cfg = getattr(config, "data_request", None) or {}
    if isinstance(data_req_cfg, dict):
        data_req_tf = data_req_cfg.get("timeframe")
    else:
        data_req_tf = getattr(data_req_cfg, "timeframe", None)

    # If insufficient bars to infer, fall back to configured timeframe(s)
    if len(market_data.index) < 2:
        if instrument_tf:
            return str(instrument_tf)
        if data_req_tf:
            return str(data_req_tf)
        return "1min"

    if instrument_tf:
        return str(instrument_tf)

    if data_req_tf:
        return str(data_req_tf)

    if not market_data.empty:
        diffs = market_data.index[1:] - market_data.index[:-1]
        if not diffs.empty:
            most_common = diffs.value_counts().idxmax()
            minutes = int(pd.Timedelta(most_common).total_seconds() / 60)
            mapping = {
                1: "1min",
                5: "5min",
                15: "15min",
                60: "1H",
                240: "4H",
                1440: "1D",
                10080: "1W",
            }
            timeframe = mapping.get(minutes)
            if timeframe:
                return timeframe
            if minutes > 0:
                # Fallback to a generic minutes label if not in mapping
                return f"{minutes}min"
    raise ValueError("Execution timeframe is required.")


def resolve_global_feature_defs(
    execution_timeframe: str, config_path: Path | str | None
) -> list[dict[str, Any]]:
    if not config_path:
        return []
    path = Path(config_path)
    resolved = resolve_global_features(execution_timeframe, config_path=path)
    return [
        {
            "name": f.name,
            "type": f.type,
            "params": f.params,
            "source": f.source,
            "timeframe": f.timeframe,
        }
        for f in resolved
    ]


def _parse_data_request_bounds(
    data_request: dict[str, Any] | None, market_data: pd.DataFrame
) -> tuple[pd.Timestamp, pd.Timestamp, bool]:
    if data_request is None:
        data_request = {}

    target_start = cast(pd.Timestamp, market_data.index.min())
    target_end = cast(pd.Timestamp, market_data.index.max())
    start_explicit = False

    start_val = data_request.get("start")
    if start_val is not None:
        target_start = pd.to_datetime(start_val, utc=True)
        start_explicit = True

    end_val = data_request.get("end")
    if end_val is not None:
        end_ts = pd.to_datetime(end_val, utc=True)
        if isinstance(end_val, str) and len(end_val) == 10:
            end_ts = end_ts + timedelta(days=1) - timedelta(seconds=1)
        target_end = end_ts

    return target_start, target_end, start_explicit


def resolve_strategy_features_for_warmup(strat: Any) -> list[dict[str, Any]]:
    resolved_features: list[dict[str, Any]] = []
    params = getattr(strat, "parameters", None) or {}
    features = getattr(strat, "features", None) or []
    for feature in features:
        feature_copy = feature.copy()
        feat_params = feature_copy.get("params")
        if isinstance(feat_params, dict):
            feature_copy["params"] = {
                key: _resolve_parameter(value, params)
                for key, value in feat_params.items()
            }
        resolved_features.append(feature_copy)
    return resolved_features


def ensure_market_data_with_warmup(
    *,
    market_data: pd.DataFrame,
    execution_timeframe: str,
    strategy_features: list[dict[str, Any]],
    global_features: list[dict[str, Any]],
    data_request: dict[str, Any] | None,
    data_handler: Any | None = None,
) -> pd.DataFrame:
    if market_data.empty:
        return market_data

    target_start, target_end, _ = _parse_data_request_bounds(data_request, market_data)

    if not isinstance(market_data.index, pd.DatetimeIndex):
        logger.warning("Market data index is not datetime; skipping warmup extension.")
        return cast(pd.DataFrame, market_data.loc[target_start:target_end].copy())

    # System-wide warmup: always include data from the earliest available bar.
    # This ensures cumulative indicators (EMA/OBV/etc.) have full history.
    # The engine will skip to trading_window_start for trade execution.
    warmup_ts = cast(pd.Timestamp, market_data.index.min())

    trimmed = market_data.loc[warmup_ts:target_end].copy()
    if trimmed.empty:
        raise ValueError(
            "Warmup trimming removed all market data. "
            "Verify data_request bounds and feature lookbacks."
        )
    return trimmed
