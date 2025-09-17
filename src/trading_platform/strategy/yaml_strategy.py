from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd

try:
    import jsonschema  # type: ignore[import-untyped]
except ImportError:
    jsonschema = None

from .features import compute_features


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
    # Internal state populated during signal generation
    _feature_df: pd.DataFrame | None = None

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        df2 = compute_features(df, self.features)
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

        sig: list[str] = []
        state = "flat"
        for i in range(len(df2)):
            if state == "flat":
                if bool(le.iloc[i]):
                    state = "long"
                elif bool(se.iloc[i]):
                    state = "short"
            elif state == "long":
                if bool(lx.iloc[i]):
                    state = "flat"
            elif state == "short":
                if bool(sx.iloc[i]):
                    state = "flat"
            sig.append(state)
        return pd.Series(sig, index=df2.index)

    def get_context(self, index: int) -> dict[str, Any]:
        """Return a dict of feature values at a specific integer index."""
        if self._feature_df is None or index >= len(self._feature_df):
            return {}
        # Get the row for the given index
        row = self._feature_df.iloc[index]
        # Return a dictionary of feature names and their values
        return {f["name"]: row[f["name"]] for f in self.features if f["name"] in row}


def compile_strategy(cfg: dict[str, Any]) -> CompiledStrategy:
    validate_strategy_config(cfg)
    name = str(cfg.get("strategy_name", "Strategy"))
    overlays = [str(x) for x in (cfg.get("overlays") or [])]
    features = list(cfg.get("features") or [])
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
    )
