"""Utility for collecting diagnostic model insights into JSON summaries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Union, cast

import numpy as np
import pandas as pd

META_COLUMNS: set[str] = {
    "execution_timeframe",
    "strategy_archetype",
    "entry_time",
    "exit_time",
}


def _model_hash(model: object) -> str:
    payload = repr(model).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _select_feature_frame(context_df: pd.DataFrame, model: object) -> pd.DataFrame:
    """Extract and align the feature frame expected by the diagnostic model.

    Diagnostic models expose `feature_names_` (post-encoding) while the raw
    enriched trades only contain canonical columns (e.g., `side`, `exit_reason`).
    Models are responsible for expanding these into one-hot encoded features,
    so we reuse the fitted model's extraction utilities when available.
    """

    extract_features = getattr(model, "_extract_features", None)
    if callable(extract_features):
        feature_frame = cast(pd.DataFrame, extract_features(context_df.copy()))
    else:
        feature_names = getattr(model, "feature_names_", None)
        if isinstance(feature_names, (list, tuple, np.ndarray, pd.Index)):
            names = [str(name) for name in feature_names]
            missing = [name for name in names if name not in context_df.columns]
            frame = context_df.copy()
            for name in missing:
                frame[name] = 0.0
            feature_frame = frame.loc[:, names]
        else:
            available = [c for c in context_df.columns if c not in META_COLUMNS]
            feature_frame = context_df.loc[:, available]

    feature_names = getattr(model, "feature_names_", None)
    if isinstance(feature_names, (list, tuple, np.ndarray, pd.Index)):
        ordered = [str(name) for name in feature_names]
        for name in ordered:
            if name not in feature_frame.columns:
                feature_frame[name] = 0.0
        feature_frame = feature_frame.loc[:, ordered]

    return feature_frame


def _top_features(model: object, feature_names: Iterable[str]) -> list[str]:
    importances = getattr(model, "feature_importances_", None)
    feature_list = list(feature_names)
    if importances is None or len(importances) != len(feature_list):
        return feature_list
    order = np.argsort(importances)[::-1]
    return [feature_list[idx] for idx in order]


FeatureBound = dict[str, Union[str, float]]


def _feature_bounds(
    feature_frame: pd.DataFrame,
    top_features: Iterable[str],
    mask: np.ndarray,
    lower_quantile: float,
    upper_quantile: float,
) -> list[FeatureBound]:
    high_df = feature_frame.loc[mask]
    if high_df.empty:
        high_df = feature_frame

    bounds: list[FeatureBound] = []
    for feature in top_features:
        if feature not in high_df.columns:
            continue
        series = high_df[feature].astype(float)
        lower = float(series.quantile(lower_quantile))
        upper = float(series.quantile(upper_quantile))
        bounds.append({"feature": feature, "lower": lower, "upper": upper})
    return bounds


def collect_diagnostic_contexts(
    enriched_path: Path,
    registry,
    output_dir: Path,
    *,
    lower_quantile: float = 0.25,
    upper_quantile: float = 0.75,
) -> None:
    """Generate diagnostic summaries for each context using trained models."""

    df = pd.read_parquet(enriched_path)
    if df.empty:
        return

    contexts = (
        df[["execution_timeframe", "strategy_archetype"]]
        .drop_duplicates()
        .itertuples(index=False)
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    for row in contexts:
        timeframe = row.execution_timeframe
        archetype = row.strategy_archetype
        context_key = f"{timeframe}_{archetype}"
        model = registry.get_model("diagnostic", context_key)
        if model is None:
            continue

        mask = (df["execution_timeframe"] == timeframe) & (
            df["strategy_archetype"] == archetype
        )
        context_df = df.loc[mask].copy()
        if context_df.empty:
            continue

        feature_frame = _select_feature_frame(context_df, model)
        if feature_frame.empty:
            continue

        probabilities = model.predict_proba(feature_frame)
        predictions = model.predict(feature_frame)

        high_quintile = int(np.sum(predictions == 4))

        feature_names = feature_frame.columns.tolist()
        top_features = _top_features(model, feature_names)
        summary = {
            "model_hash": _model_hash(model),
            "context_key": context_key,
            "top_features": top_features,
            "high_quintile_trades": high_quintile,
        }

        summary["feature_bounds"] = _feature_bounds(
            feature_frame,
            top_features,
            predictions == 4,
            lower_quantile,
            upper_quantile,
        )

        context_dir = output_dir / context_key
        context_dir.mkdir(parents=True, exist_ok=True)
        summary_path = context_dir / "diagnostic_summary.json"
        summary["summary_path"] = str(summary_path)
        summary["quintile_probabilities"] = probabilities.tolist()

        summary_path.write_text(json.dumps(summary, indent=2))
