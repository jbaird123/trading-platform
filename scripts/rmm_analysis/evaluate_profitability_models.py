"""Evaluate profitability models on enriched trades using train/test splits."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Sequence

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from trading_platform.ai.feature_engineering.unpacking import (
    unpack_simulated_holds,
)
from trading_platform.ai.models import ModelRegistry
from trading_platform.ai.models.profitability import ProfitabilityModel

TRAIN_START = "2018-01-01"
TRAIN_END = "2022-12-31"
TEST_START = "2023-01-01"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate profitability models using enriched trade data."
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
        help="Directory for evaluation metrics (CSV/JSON).",
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


def evaluate_model(
    model: ProfitabilityModel, df: pd.DataFrame
) -> dict[str, object] | None:
    mask = (df["execution_timeframe"] == model.timeframe) & (
        df["strategy_archetype"] == model.archetype
    )
    context_df = df.loc[mask].copy()
    if context_df.empty:
        return None

    actual = context_df["r_multiple"].to_numpy()
    predictions = model.predict(context_df)

    mae = mean_absolute_error(actual, predictions)
    mse = mean_squared_error(actual, predictions)
    rmse = math.sqrt(mse)
    r2 = r2_score(actual, predictions)

    actual_pos = (actual > 0).astype(int)
    pred_pos = (predictions > 0).astype(int)
    sign_acc = accuracy_score(actual_pos, pred_pos)
    conf = confusion_matrix(actual_pos, pred_pos, labels=[0, 1]).tolist()

    return {
        "samples": int(len(context_df)),
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "sign_accuracy": float(sign_acc),
        "sign_confusion_matrix": conf,
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    df = load_data(args.enriched_data)
    train_df, test_df = split_data(df)

    registry = ModelRegistry(model_dir=args.model_dir)
    registry.load()

    rows: list[dict[str, object]] = []
    for key in registry.list_models("profitability"):
        model = registry.get_model("profitability", key)
        if not isinstance(model, ProfitabilityModel):
            continue

        train_metrics = evaluate_model(model, train_df)
        test_metrics = evaluate_model(model, test_df)

        if train_metrics is None and test_metrics is None:
            continue

        rows.append(
            {
                "context": key,
                "train_samples": (
                    train_metrics["samples"] if train_metrics else 0
                ),
                "train_mae": (
                    train_metrics["mae"] if train_metrics else None
                ),
                "train_rmse": (
                    train_metrics["rmse"] if train_metrics else None
                ),
                "train_r2": (
                    train_metrics["r2"] if train_metrics else None
                ),
                "train_sign_accuracy": (
                    train_metrics["sign_accuracy"] if train_metrics else None
                ),
                "train_sign_confusion_matrix": (
                    train_metrics["sign_confusion_matrix"]
                    if train_metrics
                    else None
                ),
                "test_samples": (
                    test_metrics["samples"] if test_metrics else 0
                ),
                "test_mae": (
                    test_metrics["mae"] if test_metrics else None
                ),
                "test_rmse": (
                    test_metrics["rmse"] if test_metrics else None
                ),
                "test_r2": (
                    test_metrics["r2"] if test_metrics else None
                ),
                "test_sign_accuracy": (
                    test_metrics["sign_accuracy"] if test_metrics else None
                ),
                "test_sign_confusion_matrix": (
                    test_metrics["sign_confusion_matrix"]
                    if test_metrics
                    else None
                ),
            }
        )

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "profitability_model_metrics.csv"
    pd.DataFrame(rows).to_csv(metrics_path, index=False)
    print(f"Wrote profitability metrics to {metrics_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
