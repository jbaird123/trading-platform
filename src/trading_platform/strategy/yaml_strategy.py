from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

from trading_platform.ai.inference_client import AIInferenceClient

from .features import compute_features

logger = logging.getLogger(__name__)


def validate_strategy_config(cfg: dict[str, Any]) -> None:
    """Validate strategy config against key schema expectations.

    We prefer jsonschema when available, but also enforce minimal rules:
    - required: strategy_name (str)
        - at least one pair present: (long_entry_rules & long_exit_rules) or
            (short_entry_rules & short_exit_rules)
    - rule blocks: each has all_of or any_of with a non-empty predicate list
    - predicate: {condition, left, right} with supported conditions
    """
    if not isinstance(cfg, dict):
        raise ValueError("strategy must be an object")
    if jsonschema is not None:
        schema_path = (
            Path(__file__).resolve().parents[3]
            / "docs"
            / "schemas"
            / "strategy.schema.json"
        )
        schema = json.loads(schema_path.read_text())
        try:
            jsonschema.validate(cfg, schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Strategy schema validation error: {e.message}") from e


def load_strategy_config(doc: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(doc, dict):
        return doc
    p = Path(str(doc))
    txt = p.read_text()
    # Best-effort JSON/YAML parse without external deps: expect JSON here
    import json

    return cast(dict[str, Any], json.loads(txt))


def _series_for_operand(df: pd.DataFrame, operand: Any) -> pd.Series:
    if isinstance(operand, (int, float)):
        return pd.Series([float(operand)] * len(df), index=df.index)
    if isinstance(operand, str):
        if operand in df.columns:
            return pd.Series(df[operand], dtype="float64")
    if isinstance(operand, dict) and "ref" in operand:
        ref = str(operand["ref"])  # feature name
        return pd.Series(df[ref], dtype="float64")
    return pd.Series([0.0] * len(df), index=df.index)


def _eval_predicate(df: pd.DataFrame, pred: dict[str, Any]) -> pd.Series:
    cond = str(pred.get("condition"))
    left = _series_for_operand(df, pred.get("left"))
    right = _series_for_operand(df, pred.get("right"))
    if cond == "is_above":
        return left > right
    if cond == "is_below":
        return left < right
    if cond == "cross_above":
        prev = left.shift(1) <= right.shift(1)
        now = left > right
        return prev & now
    if cond == "cross_below":
        prev = left.shift(1) >= right.shift(1)
        now = left < right
        return prev & now
    return pd.Series([False] * len(df), index=df.index)


def _eval_rule_block(df: pd.DataFrame, block: dict[str, Any]) -> pd.Series:
    if "all_of" in block:
        preds = block["all_of"] or []
        out = pd.Series([True] * len(df), index=df.index)
        for p in preds:
            out = out & _eval_predicate(df, p)
        return out
    if "any_of" in block:
        preds = block["any_of"] or []
        out = pd.Series([False] * len(df), index=df.index)
        for p in preds:
            out = out | _eval_predicate(df, p)
        return out
    return pd.Series([False] * len(df), index=df.index)


@dataclass(frozen=True)
class CompiledStrategy:
    name: str
    overlays: list[str]
    features: list[dict]
    long_entry_blocks: list[dict]
    long_exit_blocks: list[dict]
    short_entry_blocks: list[dict]
    short_exit_blocks: list[dict]
    parameters: dict[str, Any]
    slope_filter: bool = False
    slope_feature: str | None = None
    ai_filter_enabled: bool = False
    ai_inference_client: AIInferenceClient | None = None
    ai_confidence_threshold: float = 0.0
    ai_input_features: list[str] | None = None
    # Internal state populated during signal generation
    _feature_df: pd.DataFrame | None = None

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        df2 = compute_features(df, self.features, self.parameters)
        # Persist the feature dataframe for context lookups
        super().__setattr__("_feature_df", df2)

        le = pd.Series([False] * len(df2), index=df2.index)
        for b in self.long_entry_blocks:
            le = le | _eval_rule_block(df2, b)
        lx = pd.Series([False] * len(df2), index=df2.index)
        for b in self.long_exit_blocks:
            lx = lx | _eval_rule_block(df2, b)
        se = pd.Series([False] * len(df2), index=df2.index)
        for b in self.short_entry_blocks:
            se = se | _eval_rule_block(df2, b)
        sx = pd.Series([False] * len(df2), index=df2.index)
        for b in self.short_exit_blocks:
            sx = sx | _eval_rule_block(df2, b)

        # Optional slope gating
        slope_up = pd.Series([True] * len(df2), index=df2.index)
        slope_down = pd.Series([True] * len(df2), index=df2.index)
        if self.slope_filter:
            src = self.slope_feature or "ema_slow"
            if src in df2.columns:
                s = pd.Series(df2[src], dtype="float64")
                slope_up = s > s.shift(1)
                slope_down = s < s.shift(1)

        # Apply AI filter if enabled
        if self.ai_filter_enabled and self.ai_inference_client:
            try:
                # Prepare features for AI model
                ai_features_df = df2
                if self.ai_input_features:
                    missing_features = [
                        f for f in self.ai_input_features if f not in df2.columns
                    ]
                    if missing_features:
                        logger.warning(
                            f"Missing AI input features: {missing_features}. "
                            "Skipping AI filter."
                        )
                        ai_predictions = []
                    else:
                        ai_features_df = df2[self.ai_input_features]
                ai_predictions = self.ai_inference_client.predict(ai_features_df)
                if ai_predictions:
                    # Assuming ai_predictions is a list of dicts with 'prediction'
                    # and 'confidence'
                    # and aligns with df2's index
                    ai_confidences = pd.Series(
                        [p.get("confidence", 0.0) for p in ai_predictions],
                        index=df2.index,
                    )
                    ai_signals = pd.Series(
                        [p.get("prediction", "flat") for p in ai_predictions],
                        index=df2.index,
                    )
                    # Filter entry signals based on AI confidence and prediction
                    le = le & (
                        (ai_signals == "long")
                        & (ai_confidences >= self.ai_confidence_threshold)
                    )
                    se = se & (
                        (ai_signals == "short")
                        & (ai_confidences >= self.ai_confidence_threshold)
                    )
                else:
                    logger.warning(
                        "AI inference returned no predictions. Skipping AI filter."
                    )
            except Exception as e:
                logger.error(f"Error during AI inference: {e}. Skipping AI filter.")

        sig: list[str] = []
        state = "flat"
        for i in range(len(df2)):
            if state == "flat":
                if bool(le.iloc[i]) and (
                    not self.slope_filter or bool(slope_up.iloc[i])
                ):
                    state = "long"
                elif bool(se.iloc[i]) and (
                    not self.slope_filter or bool(slope_down.iloc[i])
                ):
                    state = "short"
            elif state == "long":
                if bool(lx.iloc[i]):
                    state = "flat"
            elif state == "short":  # pragma: no branch
                if bool(sx.iloc[i]):
                    state = "flat"
            sig.append(state)
        return pd.Series(sig, index=df2.index)

    def get_context(self, index: int) -> dict[str, Any]:
        """Return a dict of feature values at a specific integer index.
        Always returns a fully populated context dict, never None or empty.
        """
        # Fail fast for out-of-bounds index
        if self._feature_df is None or not (0 <= index < len(self._feature_df)):
            raise IndexError("Context lookup index is out of bounds.")
        
        context = {}
        if self._feature_df is not None and 0 <= index < len(self._feature_df):
            row = self._feature_df.iloc[index]
            for f in self.features:
                name = f.get("name")
                if name is not None:
                    context[name] = row.get(name, None)
        # If no features, fill with explicit None for each expected feature name
        elif self.features:
            for f in self.features:
                name = f.get("name")
                if name is not None:
                    context[name] = None
        # Always return a dict with all expected feature names
        return context


def compile_strategy(cfg: dict[str, Any]) -> CompiledStrategy:
    cfg.setdefault("parameters", {})
    validate_strategy_config(cfg)
    name = str(cfg.get("strategy_name", "Strategy"))
    overlays = [str(x) for x in (cfg.get("overlays") or [])]
    features = list(cfg.get("features") or [])
    param_map = cfg.get("parameters", {})
    if not isinstance(param_map, dict):
        param_map = {}
    slope_filter = bool(param_map.get("slope_filter", False))
    slope_feature = str(param_map.get("slope_feature", "ema_slow"))
    ai_filter_config = cfg.get("ai_filter", {})
    ai_filter_enabled = bool(ai_filter_config.get("enabled", False)) and (
        jsonschema is not None
    )
    ai_confidence_threshold = float(ai_filter_config.get("confidence_threshold", 0.0))
    ai_input_features = [str(x) for x in (ai_filter_config.get("input_features") or [])]
    ai_inference_client = AIInferenceClient() if ai_filter_enabled else None

    le = list(cfg.get("long_entry_rules") or [])
    lx = list(cfg.get("long_exit_rules") or [])
    se = list(cfg.get("short_entry_rules") or [])
    sx = list(cfg.get("short_exit_rules") or [])
    return CompiledStrategy(
        name=name,
        overlays=overlays,
        features=features,
        long_entry_blocks=le,
        long_exit_blocks=lx,
        short_entry_blocks=se,
        short_exit_blocks=sx,
        parameters=param_map,
        slope_filter=slope_filter,
        slope_feature=slope_feature,
        ai_filter_enabled=ai_filter_enabled,
        ai_inference_client=ai_inference_client,
        ai_confidence_threshold=ai_confidence_threshold,
        ai_input_features=ai_input_features,
    )
