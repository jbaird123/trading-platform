"""Utility for collecting diagnostic model insights into JSON summaries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

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
    feature_names = getattr(model, "feature_names_", None)
    if isinstance(feature_names, (list, tuple, np.ndarray, pd.Index)):
        names = [str(name) for name in feature_names]
        return context_df.loc[:, names]
    available = [c for c in context_df.columns if c not in META_COLUMNS]
    return context_df.loc[:, available]


def _top_features(model: object, feature_names: Iterable[str]) -> list[str]:
    importances = getattr(model, "feature_importances_", None)
    feature_list = list(feature_names)
    if importances is None or len(importances) != len(feature_list):
        return feature_list
    order = np.argsort(importances)[::-1]
    return [feature_list[idx] for idx in order]


def collect_diagnostic_contexts(
    enriched_path: Path,
    registry,
    output_dir: Path,
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
        summary = {
            "model_hash": _model_hash(model),
            "context_key": context_key,
            "top_features": _top_features(model, feature_names),
            "high_quintile_trades": high_quintile,
        }

        context_dir = output_dir / context_key
        context_dir.mkdir(parents=True, exist_ok=True)
        summary_path = context_dir / "diagnostic_summary.json"
        summary["summary_path"] = str(summary_path)
        summary["quintile_probabilities"] = probabilities.tolist()

        summary_path.write_text(json.dumps(summary, indent=2))
