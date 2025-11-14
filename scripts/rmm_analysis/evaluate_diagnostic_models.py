"""Evaluate diagnostic models on enriched data to gauge predictive quality."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix
from trading_platform.ai.feature_engineering.unpacking import (
    unpack_simulated_holds,
)
from trading_platform.ai.models import ModelRegistry
from trading_platform.ai.models._timeframe_utils import (
    drop_lower_timeframe_global_features,
)
from trading_platform.ai.models.performance_diagnostic import (
    PerformanceDiagnosticModel,
)

TRAIN_START = "2018-01-01"
TRAIN_END = "2022-12-31"
TEST_START = "2023-01-01"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate diagnostic models using the enriched trade log."
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
        help="Directory containing trained diagnostic models (data/dvc/ml/models).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for evaluation metrics (JSON/Markdown).",
    )
    return parser.parse_args(argv)


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    return unpack_simulated_holds(df)


def split_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_mask = (df["entry_time"] >= TRAIN_START) & (df["entry_time"] <= TRAIN_END)
    test_mask = df["entry_time"] >= TEST_START
    return df.loc[train_mask].copy(), df.loc[test_mask].copy()


def evaluate_model(
    model: PerformanceDiagnosticModel, df: pd.DataFrame
) -> dict[str, object] | None:
    mask = (df["execution_timeframe"] == model.timeframe) & (
        df["strategy_archetype"] == model.archetype
    )
    context_df = df.loc[mask].copy()
    if context_df.empty:
        return None

    target_metric = getattr(model, "target_metric", "r_multiple")
    context_df = context_df.dropna(subset=[target_metric])
    if context_df.empty:
        return None

    context_df = drop_lower_timeframe_global_features(context_df, model.timeframe)

    target_values = context_df[target_metric].to_numpy()
    if target_values.size == 0:
        return None

    y = model._create_quintile_target(target_values)
    preds = model.predict(context_df)

    acc = accuracy_score(y, preds)
    bal_acc = balanced_accuracy_score(y, preds)
    conf = confusion_matrix(y, preds, labels=[0, 1, 2, 3, 4])
    return {
        "samples": int(len(context_df)),
        "accuracy": float(acc),
        "balanced_accuracy": float(bal_acc),
        "confusion_matrix": conf.tolist(),
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    df = load_data(args.enriched_data)
    train_df, test_df = split_data(df)
    registry = ModelRegistry(model_dir=args.model_dir)
    registry.load()

    rows = []
    for context in registry.list_models("diagnostic"):
        model = registry.get_model("diagnostic", context)
        if not isinstance(model, PerformanceDiagnosticModel):
            continue
        train_eval = evaluate_model(model, train_df)
        test_eval = evaluate_model(model, test_df)
        if train_eval is None and test_eval is None:
            continue
        rows.append(
            {
                "context": context,
                "train_samples": train_eval["samples"] if train_eval else 0,
                "train_accuracy": (train_eval["accuracy"] if train_eval else None),
                "train_balanced_accuracy": (
                    train_eval["balanced_accuracy"] if train_eval else None
                ),
                "test_samples": test_eval["samples"] if test_eval else 0,
                "test_accuracy": (test_eval["accuracy"] if test_eval else None),
                "test_balanced_accuracy": (
                    test_eval["balanced_accuracy"] if test_eval else None
                ),
                "train_confusion_matrix": (
                    train_eval["confusion_matrix"] if train_eval else None
                ),
                "test_confusion_matrix": (
                    test_eval["confusion_matrix"] if test_eval else None
                ),
            }
        )

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "diagnostic_model_metrics.csv"
    pd.DataFrame(rows).to_csv(metrics_path, index=False)
    print(f"Wrote diagnostics to {metrics_path}")


if __name__ == "__main__":
    main()
