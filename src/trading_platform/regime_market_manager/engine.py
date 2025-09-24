from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from trading_platform.data.schema import resample_ohlc
from trading_platform.strategy.features import compute_features

try:
    import jsonschema
    from jsonschema import ValidationError
except Exception:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]


def _op_series(df: pd.DataFrame, operand: Any) -> pd.Series:
    if isinstance(operand, (int, float)):
        return pd.Series([float(operand)] * len(df), index=df.index)
    if isinstance(operand, str) and operand in df.columns:
        return pd.Series(df[operand], dtype="float64")
    if isinstance(operand, dict) and "ref" in operand:
        name = str(operand["ref"])
        return pd.Series(df[name], dtype="float64")
    return pd.Series([0.0] * len(df), index=df.index)


def _eval_pred(df: pd.DataFrame, pred: dict[str, Any]) -> pd.Series:
    cond = str(pred.get("condition"))
    left = _op_series(df, pred.get("left"))
    right = _op_series(df, pred.get("right"))
    if cond == "is_above":
        return left > right
    if cond == "is_below":
        return left < right
    if cond == "cross_above":
        return (left.shift(1) <= right.shift(1)) & (left > right)
    if cond == "cross_below":
        return (left.shift(1) >= right.shift(1)) & (left < right)
    return pd.Series([False] * len(df), index=df.index)


def _eval_block(df: pd.DataFrame, block: dict[str, Any]) -> pd.Series:
    if "all_of" in block:
        out = pd.Series([True] * len(df), index=df.index)
        for p in block.get("all_of") or []:
            out = out & _eval_pred(df, p)
        return out
    if "any_of" in block:
        out = pd.Series([False] * len(df), index=df.index)
        for p in block.get("any_of") or []:
            out = out | _eval_pred(df, p)
        return out
    return pd.Series([False] * len(df), index=df.index)


@dataclass(frozen=True)
class RMMEngine:
    config: dict[str, Any]

    @staticmethod
    def validate_config(cfg: dict[str, Any]) -> None:
        if jsonschema is None:
            raise ValueError(
                "jsonschema is required for RMM validation but is not installed."
            )
        schema_path = (
            Path(__file__).resolve().parents[3] / "docs" / "schemas" / "rmm.schema.json"
        )
        schema = json.loads(schema_path.read_text())
        try:
            jsonschema.validate(cfg, schema)
        except ValidationError as e:  # pragma: no cover
            path = ".".join(str(p) for p in getattr(e, "path", []))
            where = f" at '{path}'" if path else ""
            raise ValueError(f"rmm schema validation error{where}: {e.message}") from e

    def classify_daily(self, df_hourly: pd.DataFrame) -> pd.DataFrame:
        """Return daily regime labels/confidence based on RMM config rules."""
        cfg = self.config
        feats = list(cfg.get("features") or [])
        regimes = list(cfg.get("regimes") or [])
        daily = resample_ohlc(df_hourly, "1d")
        df = compute_features(daily, feats)
        labels = []
        confs = []
        for i in range(len(df)):
            row = df.iloc[: i + 1]  # predicates can use shift
            chosen = None
            for r in regimes:
                conds = r.get("conditions") or {}
                mask = _eval_block(row, conds)
                if bool(mask.iloc[-1]):
                    chosen = (str(r.get("label")), float(r.get("confidence", 0.0)))
                    break
            if chosen is None:
                chosen = ("unknown", 0.0)
            labels.append(chosen[0])
            confs.append(chosen[1])
        out = pd.DataFrame({"label": labels, "confidence": confs}, index=df.index)
        return out

    @staticmethod
    def allowed_sides_for(label: str, confidence: float, policy: dict) -> list[str]:
        """Decide allowed sides based on policy + conventional mapping.

        Policy (per schema):
        - min_confidence: float
        - allow_labels: [str]
        - block_labels: [str]

        Conventional mapping:
        - trend_up -> ["long"]
        - trend_down -> ["short"]
        - range/unknown -> []
        """
        min_c = (
            float(policy.get("min_confidence", 0.0))
            if isinstance(policy, dict)
            else 0.0
        )
        if confidence < min_c:
            return []
        allow_labels = policy.get("allow_labels") or None
        if isinstance(allow_labels, list) and label not in allow_labels:
            return []
        block_labels = policy.get("block_labels") or None
        if isinstance(block_labels, list) and label in block_labels:
            return []
        if label == "trend_up":
            return ["long"]
        if label == "trend_down":
            return ["short"]
        return []

    def project_to_index(
        self, daily: pd.DataFrame, target_index: pd.DatetimeIndex, policy: dict | None
    ) -> pd.DataFrame:
        """Forward-fill daily regimes onto target index with allowed sides.

        Returns DataFrame with columns: label, confidence, allowed_sides
        indexed by target_index.
        """
        if daily.empty:
            return pd.DataFrame(
                index=target_index, columns=["label", "confidence", "allowed_sides"]
            ).fillna(  # noqa: E501
                {"label": "unknown", "confidence": 0.0, "allowed_sides": []}
            )
        # Reindex with forward-fill to align to target_index boundaries
        aligned = daily.reindex(daily.index.union(target_index)).sort_index().ffill()
        aligned = aligned.loc[target_index]
        allowed = [
            self.allowed_sides_for(
                str(row["label"]), float(row["confidence"]), policy or {}
            )
            for _, row in aligned.iterrows()
        ]
        aligned = aligned.assign(
            allowed_sides=pd.Series(allowed, index=aligned.index, dtype=object)
        )
        return aligned
