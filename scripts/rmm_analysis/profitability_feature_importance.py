"""Compute permutation-based feature importance for profitability models."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error
from trading_platform.ai.feature_engineering.unpacking import (
    unpack_simulated_holds,
)
from trading_platform.ai.models import ModelRegistry
from trading_platform.ai.models.profitability import ProfitabilityModel

TRAIN_START = "2018-01-01"
TRAIN_END = "2021-12-31"
TEST_START = "2022-01-01"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute permutation feature importance for profitability models "
            "using the master trade log."
        )
    )
    parser.add_argument(
        "--enriched-data",
        required=True,
        type=Path,
        help="Path to master_trade_log.parquet (enriched trades).",
    )
    parser.add_argument(
        "--model-dir",
        required=True,
        type=Path,
        help="Directory containing trained profitability models.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write feature importance CSV files.",
    )
    parser.add_argument(
        "--n-repeats",
        type=int,
        default=10,
        help="Number of shuffles per feature for permutation importance.",
    )
    return parser.parse_args(argv)


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    df = unpack_simulated_holds(df)
    df = df[df["r_multiple"].notna()].copy()
    return df


def split_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_mask = (df["entry_time"] >= TRAIN_START) & (df["entry_time"] <= TRAIN_END)
    test_mask = df["entry_time"] >= TEST_START
    return df.loc[train_mask].copy(), df.loc[test_mask].copy()


def _prepare_feature_matrix(
    model: ProfitabilityModel, df: pd.DataFrame
) -> tuple[np.ndarray, list[str]]:
    """Extract aligned feature matrix ready for the underlying estimator."""
    features_df = model._extract_features(df)
    aligned = model._align_features(features_df)
    if model.imputer is None:
        raise ValueError("Model imputer is not fitted.")
    imputed = model.imputer.transform(aligned)
    columns = list(aligned.columns)
    return np.asarray(imputed, dtype=float), columns


def compute_importance(
    model: ProfitabilityModel,
    df: pd.DataFrame,
    n_repeats: int,
) -> pd.DataFrame | None:
    if model.model is None or model.feature_names_ is None or model.imputer is None:
        return None

    if df.empty:
        return None

    X, feature_names = _prepare_feature_matrix(model, df)
    y = df["r_multiple"].to_numpy(dtype=float)

    if len(y) < 30:
        return None

    baseline_pred = model.model.predict(X)
    baseline_mae = mean_absolute_error(y, baseline_pred)

    result = permutation_importance(
        model.model,
        X,
        y,
        scoring="neg_mean_absolute_error",
        n_repeats=n_repeats,
        random_state=42,
        n_jobs=1,
    )

    rows = []
    for idx, feature in enumerate(feature_names):
        rows.append(
            {
                "feature": feature,
                "importance_mean": float(result.importances_mean[idx]),
                "importance_std": float(result.importances_std[idx]),
            }
        )

    df_result = pd.DataFrame(rows)
    df_result.sort_values("importance_mean", ascending=False, inplace=True)
    df_result["baseline_mae"] = float(baseline_mae)
    return df_result


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    df = load_data(args.enriched_data)
    _train_df, test_df = split_data(df)

    registry = ModelRegistry(model_dir=args.model_dir)
    registry.load()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []

    for context in registry.list_models("profitability"):
        model = registry.get_model("profitability", context)
        if not isinstance(model, ProfitabilityModel):
            continue

        timeframe, archetype = context.split("_", 1)
        mask = (test_df["execution_timeframe"] == timeframe) & (
            test_df["strategy_archetype"] == archetype
        )
        context_df = test_df.loc[mask].copy()
        importance_df = compute_importance(model, context_df, args.n_repeats)

        if importance_df is None:
            continue

        importance_df.insert(0, "context", context)
        importance_path = output_dir / f"{context}_feature_importance.csv"
        importance_df.to_csv(importance_path, index=False)

        top_features = importance_df.head(10)
        summary_rows.append(
            {
                "context": context,
                "baseline_mae": float(top_features["baseline_mae"].iloc[0]),
                "top_features": ",".join(top_features["feature"].tolist()),
            }
        )

    if summary_rows:
        summary_path = output_dir / "feature_importance_summary.csv"
        pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
        print(f"Wrote feature importance summary to {summary_path}")
    else:
        print("No profitability models produced feature importance output.")


if __name__ == "__main__":  # pragma: no cover
    main()
