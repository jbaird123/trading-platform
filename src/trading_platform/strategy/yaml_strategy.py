from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd

try:
    import jsonschema  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]

from .features import compute_features


def validate_strategy_config(cfg: dict[str, Any]) -> None:
    """Lightweight validation aligned to docs/schemas/strategy.schema.json.

    This avoids a full jsonschema dependency while enforcing key structure:
    - required: strategy_name (str), entry_rules (list), exit_rules (list)
    - features: optional list of {name:str, type:str}
    - rule blocks: each item has all_of or any_of with a list of predicates
    - predicate: {condition, left, right} with known conditions
    """
    if not isinstance(cfg, dict):
        raise ValueError("strategy must be an object")
    # JSON Schema validation if available (prefer strict validation first)
    if jsonschema is not None:
        schema_path = (
            Path(__file__).resolve().parents[3]
            / "docs"
            / "schemas"
            / "strategy.schema.json"
        )
        try:
            schema = json.loads(schema_path.read_text())
            jsonschema.validate(cfg, schema)  # type: ignore[misc]
        except Exception as exc:  # pragma: no cover
            raise ValueError(f"strategy schema validation failed: {exc}") from exc
    for req in ("strategy_name", "entry_rules", "exit_rules"):
        if req not in cfg:
            raise ValueError(f"missing required field: {req}")
    if not isinstance(cfg["strategy_name"], str):
        raise ValueError("strategy_name must be a string")
    for k in ("entry_rules", "exit_rules"):
        if not isinstance(cfg[k], list) or not cfg[k]:
            raise ValueError(f"{k} must be a non-empty array")
        for block in cfg[k]:
            if not isinstance(block, dict):
                raise ValueError("rule block must be an object")
            choices = ["all_of", "any_of"]
            present = [c for c in choices if c in block]
            if not present:
                raise ValueError("rule block must have all_of or any_of")
            preds = block[present[0]]
            if not isinstance(preds, list) or not preds:
                raise ValueError("predicate list must be a non-empty array")
            for pred in preds:
                if not isinstance(pred, dict):
                    raise ValueError("predicate must be an object")
                cond = str(pred.get("condition", ""))
                if cond not in {"is_above", "is_below", "cross_above", "cross_below"}:
                    raise ValueError(f"unsupported condition: {cond}")


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
    entry_blocks: list[dict]
    exit_blocks: list[dict]
    risk: dict[str, Any]
    allow_bearish_entry_from_exit: bool = False

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        df2 = compute_features(df, self.features)
        enter_long = pd.Series([False] * len(df2), index=df2.index)
        for b in self.entry_blocks:
            enter_long = enter_long | _eval_rule_block(df2, b)
        exit_or_enter_short = pd.Series([False] * len(df2), index=df2.index)
        for b in self.exit_blocks:
            exit_or_enter_short = exit_or_enter_short | _eval_rule_block(df2, b)
        # Stateful signals supporting flat, long, short (minimal semantics):
        # - flat -> long when entry rules true
        # - flat -> short when exit rules true (used as bearish entry)
        # - long -> flat when exit rules true
        # - short -> flat when entry rules true
        sig = []
        state = "flat"
        for i in range(len(df2)):
            if state == "flat":
                if bool(enter_long.iloc[i]):
                    state = "long"
                elif self.allow_bearish_entry_from_exit and bool(
                    exit_or_enter_short.iloc[i]
                ):
                    state = "short"
            elif state == "long":
                if bool(exit_or_enter_short.iloc[i]):
                    state = "flat"
            elif state == "short":
                if bool(enter_long.iloc[i]):
                    state = "flat"
            sig.append(state)
        return pd.Series(sig, index=df2.index)


def compile_strategy(cfg: dict[str, Any]) -> CompiledStrategy:
    validate_strategy_config(cfg)
    name = str(cfg.get("strategy_name", "Strategy"))
    overlays = [str(x) for x in (cfg.get("overlays") or [])]
    features = list(cfg.get("features") or [])
    entry_blocks = list(cfg.get("entry_rules") or [])
    exit_blocks = list(cfg.get("exit_rules") or [])
    risk = dict(cfg.get("risk") or {})

    # Allow bearish entry from exit rules only if exit blocks use crossing
    def _has_cross(b: dict[str, Any]) -> bool:
        arr = b.get("all_of") or b.get("any_of") or []
        for p in arr:
            if isinstance(p, dict) and p.get("condition") in {
                "cross_above",
                "cross_below",
            }:
                return True
        return False

    allow_short = any(_has_cross(b) for b in exit_blocks)
    return CompiledStrategy(
        name=name,
        overlays=overlays,
        features=features,
        entry_blocks=entry_blocks,
        exit_blocks=exit_blocks,
        risk=risk,
        allow_bearish_entry_from_exit=allow_short,
    )
