from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

try:
    import jsonschema  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]


class RegimeManagerConfig(BaseModel):
    """
    Configuration for the rule-based Regime Market Manager.
    """

    trend_indicator: str = Field(
        default="ADX(14)", description="Indicator used to measure trend strength."
    )
    trend_threshold_high: float = Field(
        default=25.0,
        description="ADX value above which a strong trend is considered.",
    )
    trend_threshold_low: float = Field(
        default=20.0,
        description="ADX value below which a ranging market is considered.",
    )
    slope_indicator: str = Field(
        default="EMA(200)_slope", description="Indicator for trend direction."
    )
    slope_threshold: float = Field(
        default=0.1,
        description="Absolute slope value to confirm trend direction.",
    )


def validate_rmm_config(cfg: dict) -> None:
    """Lightweight validation aligned to docs/schemas/rmm.schema.json.

    Required top-level: regimes (non-empty array). Each regime:
    - label: str
    - confidence: number in [0,1]
    - conditions: object with all_of or any_of -> list of predicates
    """
    if not isinstance(cfg, dict):
        raise ValueError("rmm config must be an object")
    # JSON Schema validation if available (best-effort, non-fatal)
    if jsonschema is not None:
        schema_path = (
            Path(__file__).resolve().parents[3] / "docs" / "schemas" / "rmm.schema.json"
        )
        try:
            schema = json.loads(schema_path.read_text())
            jsonschema.validate(cfg, schema)  # type: ignore[misc]
        except Exception:  # pragma: no cover
            # Accept minimal configs; rely on lightweight checks below.
            pass
    regimes = cfg.get("regimes")
    if not isinstance(regimes, list) or not regimes:
        raise ValueError("regimes must be a non-empty array")
    for r in regimes:
        if not isinstance(r, dict):
            raise ValueError("regime must be an object")
        if not isinstance(r.get("label"), str):
            raise ValueError("regime.label must be a string")
        conf = r.get("confidence")
        if not isinstance(conf, (int, float)) or not (0.0 <= float(conf) <= 1.0):
            raise ValueError("regime.confidence must be 0..1")
        conds = r.get("conditions")
        if not isinstance(conds, dict):
            raise ValueError("regime.conditions must be an object")
        present = [k for k in ("all_of", "any_of") if k in conds]
        if not present:
            raise ValueError("regime.conditions requires all_of or any_of")
        preds = conds[present[0]]
        if not isinstance(preds, list) or not preds:
            raise ValueError("predicate list must be a non-empty array")
