"""Classifier-based profitability gating engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, SupportsFloat, cast

import numpy as np
import pandas as pd

from trading_platform.ai.models import ModelRegistry
from trading_platform.core import paths
from trading_platform.regime_market_manager.models import (
    RMMGatingContext,
    RMMGatingProfile,
)

ALIGNMENT_COLUMN_MAP = {
    "5min": "context_at_entry_global_features_15min_trend_alignment_full_alignment",
    "15min": "context_at_entry_global_features_1h_trend_alignment_full_alignment",
}


@dataclass
class GatingDecision:
    allowed: bool
    probability: float | None
    threshold: float
    expression_passed: bool
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "probability": self.probability,
            "threshold": self.threshold,
            "expression_passed": self.expression_passed,
            "reason": self.reason,
        }


class ProfitabilityGatingEngine:
    """Evaluate classifier-based gating rules for trade entries."""

    def __init__(
        self,
        profile: RMMGatingProfile,
        model_dir: Path | None = None,
        registry: ModelRegistry | None = None,
    ) -> None:
        self.profile = profile
        self._logger = logging.getLogger(__name__)
        self._context_map = profile.context_map()
        self._missing_models: set[str] = set()
        self.registry = registry or ModelRegistry(
            model_dir=model_dir or paths.PROJECT_ROOT / "data" / "dvc" / "ml" / "models"
        )
        # Ensure models are loaded so get_model works immediately
        self.registry.load()

    def should_allow(
        self,
        timeframe: str,
        archetype: str,
        side: str,
        symbol: str,
        entry_time: datetime,
        context: dict[str, Any] | None,
    ) -> GatingDecision:
        ctx_key = (str(timeframe).lower(), archetype)
        ctx_cfg = self._context_map.get(ctx_key)
        if ctx_cfg is None:
            return GatingDecision(
                allowed=True,
                probability=None,
                threshold=0.0,
                expression_passed=True,
                reason="no_gating_context",
            )

        classifier = self._get_classifier(ctx_cfg)
        if classifier is None:
            return GatingDecision(
                allowed=True,
                probability=None,
                threshold=ctx_cfg.probability_threshold,
                expression_passed=True,
                reason="missing_classifier",
            )

        row = self._build_feature_row(context or {}, side, symbol, entry_time)
        try:
            proba = classifier.predict_proba(row)
        except ValueError as exc:
            raise ValueError(
                "Profitability classifier is missing required features for "
                f"{ctx_cfg.timeframe}_{ctx_cfg.archetype}: {exc}"
            ) from exc
        if isinstance(proba, pd.Series):
            probability = float(proba.iloc[0])
        else:
            try:
                probability = float(proba[0][-1])
            except Exception:
                probability = float(proba[0])
        expression_passed = self._evaluate_expression(ctx_cfg, row)
        allowed = probability >= ctx_cfg.probability_threshold and expression_passed
        reason = None
        if not allowed:
            if probability < ctx_cfg.probability_threshold:
                reason = "probability_below_threshold"
            elif not expression_passed:
                reason = "gating_expression_failed"
        return GatingDecision(
            allowed=allowed,
            probability=probability,
            threshold=ctx_cfg.probability_threshold,
            expression_passed=expression_passed,
            reason=reason,
        )

    def _get_classifier(self, ctx_cfg: RMMGatingContext):
        key = f"{ctx_cfg.timeframe}_{ctx_cfg.archetype}"
        model = self.registry.get_model("profitability_classifier", key)
        if model is None:
            if key not in self._missing_models:
                self._missing_models.add(key)
            msg = (
                f"Profitability classifier '{key}' not found. "
                "Train the classifier before enabling gating."
            )
            self._logger.error(msg)
            raise RuntimeError(msg)
        return model

    def _build_feature_row(
        self,
        context: dict[str, Any],
        side: str,
        symbol: str,
        entry_time: datetime,
    ) -> pd.DataFrame:
        strategy_section = context.get("strategy_features") or {}
        risk_section = context.get("risk") or {}

        # Derive risk distances if stop + entry are available
        entry_price = risk_section.get("entry_price")
        stop_price = risk_section.get("initial_stop_loss_price")
        if entry_price is not None and stop_price is not None:
            entry_val = float(cast(SupportsFloat, entry_price))
            stop_val = float(cast(SupportsFloat, stop_price))
            risk_distance = abs(entry_val - stop_val)
            risk_section.setdefault("risk_distance_abs", risk_distance)
            entry_abs = abs(entry_val) or 1.0
            risk_section.setdefault(
                "risk_distance_pct_entry", risk_distance / entry_abs
            )
            atr_val = strategy_section.get("atr_14")
            if atr_val not in (None, 0, 0.0):
                atr_float = float(cast(SupportsFloat, atr_val))
                risk_section.setdefault(
                    "risk_distance_atr_ratio", risk_distance / atr_float
                )

        def _prefixed_key(base: str, name: str) -> str:
            if name.startswith("context_at_entry_"):
                return name
            return f"{base}{name}"

        flat: dict[str, Any] = {}
        for section_name, payload in context.items():
            if not isinstance(payload, dict):
                continue
            prefix = f"context_at_entry_{section_name}_"
            for key, value in payload.items():
                if isinstance(value, dict):
                    for sub_key, sub_val in value.items():
                        target = _prefixed_key(prefix, f"{key}_{sub_key}")
                        flat[target] = sub_val
                else:
                    target = _prefixed_key(prefix, key)
                    flat[target] = value
        flat["side"] = str(side).lower()
        symbol_key = "".join(ch for ch in str(symbol) if ch.isalnum()).upper()
        flat["symbol"] = symbol_key or str(symbol)

        ts = pd.Timestamp(entry_time)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        flat["entry_time"] = ts
        flat["hour_of_day"] = ts.tz_convert("UTC").hour
        flat["day_of_week"] = ts.tz_convert("UTC").dayofweek

        risk_ctx = context.get("risk")
        if isinstance(risk_ctx, dict):
            for key, value in risk_ctx.items():
                flat[str(key)] = value

        row = pd.DataFrame([flat])
        # Replace NaN/inf with 0.0 before passing to classifiers
        row = row.replace([np.inf, -np.inf], np.nan)
        row = row.fillna(0.0)
        return row

    def _evaluate_expression(
        self, ctx_cfg: RMMGatingContext, row: pd.DataFrame
    ) -> bool:
        expr = ctx_cfg.gating_expression.strip().lower()
        if not expr or expr == "true":
            return True
        if expr == "alignment_full":
            column = ALIGNMENT_COLUMN_MAP.get(ctx_cfg.timeframe)
            if not column:
                return False
            value = row.iloc[0].get(column)
            if value is None:
                return False
            try:
                return float(value) > 0.0
            except (TypeError, ValueError):
                return False
        # Unsupported expressions default to False to avoid false positives
        self._logger.warning(
            "Unsupported gating_expression '%s' for timeframe %s",
            ctx_cfg.gating_expression,
            ctx_cfg.timeframe,
        )
        return False
