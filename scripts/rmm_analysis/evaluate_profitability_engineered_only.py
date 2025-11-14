"""Evaluate profitability models using engineered forward-safe features only."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

TRAIN_START = "2018-01-01"
TRAIN_END = "2021-12-31"
TEST_START = "2022-01-01"

DEFAULT_PATTERNS = [
    "trend_alignment",
    "slope_pct",
    "rsi_bias",
    "adx_strength",
    "atr_pct",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train and evaluate profitability models using only engineered "
            "forward-safe features."
        )
    )
    parser.add_argument(
        "--enriched-data",
        required=True,
        type=Path,
        help="Path to master_trade_log.parquet (enriched trades).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write evaluation metrics.",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=200,
        help="Number of trees for RandomForestRegressor.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--patterns",
        type=str,
        default=",".join(DEFAULT_PATTERNS),
        help=(
            "Comma-separated substrings used to select engineered features "
            "(default: trend_alignment,slope_pct,rsi_bias,adx_strength,atr_pct)."
        ),
    )
    return parser.parse_args(argv)


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    df = df[df["r_multiple"].notna()].copy()
    return df


def split_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_mask = (df["entry_time"] >= TRAIN_START) & (df["entry_time"] <= TRAIN_END)
    test_mask = df["entry_time"] >= TEST_START
    return df.loc[train_mask].copy(), df.loc[test_mask].copy()


def _normalize_patterns(raw: str) -> list[str]:
    tokens = [token.strip().lower() for token in raw.split(",")]
    return [token for token in tokens if token]


def _engineered_feature_columns(df: pd.DataFrame, patterns: list[str]) -> list[str]:
    columns = []
    for col in df.columns:
        if not col.startswith("context_at_entry"):
            continue
        lowered = col.lower()
        if any(pattern in lowered for pattern in patterns):
            columns.append(col)
    return columns


def _build_feature_frame(df: pd.DataFrame, patterns: list[str]) -> pd.DataFrame:
    engineered_cols = _engineered_feature_columns(df, patterns)
    features = df[engineered_cols].copy()

    # Metadata known at entry time
    features["initial_stop_loss_price"] = df["initial_stop_loss_price"]
    features["hour_of_day"] = df["entry_time"].dt.hour
    features["day_of_week"] = df["entry_time"].dt.dayofweek

    # One-hot encode categorical columns
    categorical = pd.get_dummies(
        df[["side", "symbol"]],
        prefix=["side", "symbol"],
        drop_first=False,
        dummy_na=False,
    )
    features = pd.concat([features, categorical], axis=1)

    # Drop columns that are entirely NaN
    features = features.dropna(axis=1, how="all")

    return features


def _prepare_xy(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    patterns: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    train_features = _build_feature_frame(train_df, patterns)
    test_features = _build_feature_frame(test_df, patterns)

    # Align columns
    all_columns = sorted(set(train_features.columns) | set(test_features.columns))
    train_features = train_features.reindex(columns=all_columns, fill_value=np.nan)
    test_features = test_features.reindex(columns=all_columns, fill_value=np.nan)

    imputer = SimpleImputer(strategy="mean")
    X_train = imputer.fit_transform(train_features)
    X_test = imputer.transform(test_features)

    y_train = train_df["r_multiple"].to_numpy(dtype=float)
    y_test = test_df["r_multiple"].to_numpy(dtype=float)

    return X_train, X_test, y_train, y_test, all_columns


def evaluate_context(
    context_df_train: pd.DataFrame,
    context_df_test: pd.DataFrame,
    patterns: list[str],
    *,
    random_state: int,
    n_estimators: int,
) -> tuple[dict[str, float], pd.DataFrame | None] | None:
    if len(context_df_train) < 50 or len(context_df_test) < 30:
        return None

    X_train, X_test, y_train, y_test, feature_names = _prepare_xy(
        context_df_train, context_df_test, patterns
    )

    # Random forest regression using engineered features
    rf = RandomForestRegressor(
        n_estimators=n_estimators,
        random_state=random_state,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    y_pred = rf.predict(X_test)

    rf_mae = mean_absolute_error(y_test, y_pred)
    rf_rmse = mean_squared_error(y_test, y_pred) ** 0.5
    rf_r2 = r2_score(y_test, y_pred)
    rf_sign_acc = accuracy_score((y_test > 0).astype(int), (y_pred > 0).astype(int))

    # Logistic regression baseline on sign prediction
    y_train_sign = (y_train > 0).astype(int)
    y_test_sign = (y_test > 0).astype(int)

    log_pipeline = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=random_state,
        ),
    )
    log_pipeline.fit(X_train, y_train_sign)
    sign_pred = log_pipeline.predict(X_test)
    sign_proba = log_pipeline.predict_proba(X_test)[:, 1]

    log_acc = accuracy_score(y_test_sign, sign_pred)
    log_precision = precision_score(y_test_sign, sign_pred, zero_division=0)
    log_recall = recall_score(y_test_sign, sign_pred, zero_division=0)
    log_f1 = (
        2 * log_precision * log_recall / (log_precision + log_recall)
        if (log_precision + log_recall) > 0
        else 0.0
    )
    try:
        log_auc = roc_auc_score(y_test_sign, sign_proba)
    except ValueError:
        log_auc = float("nan")

    tn, fp, fn, tp = confusion_matrix(y_test_sign, sign_pred).ravel()

    importance_df: pd.DataFrame | None = None
    if getattr(rf, "feature_importances_", None) is not None:
        importance_df = pd.DataFrame(
            {
                "feature": feature_names,
                "importance": rf.feature_importances_,
            }
        ).sort_values("importance", ascending=False)

    return {
        "rf_mae": float(rf_mae),
        "rf_rmse": float(rf_rmse),
        "rf_r2": float(rf_r2),
        "rf_sign_accuracy": float(rf_sign_acc),
        "logistic_sign_accuracy": float(log_acc),
        "logistic_precision": float(log_precision),
        "logistic_recall": float(log_recall),
        "logistic_f1": float(log_f1),
        "logistic_sign_auc": float(log_auc),
        "tp": float(tp),
        "fp": float(fp),
        "tn": float(tn),
        "fn": float(fn),
        "n_train": float(len(context_df_train)),
        "n_test": float(len(context_df_test)),
        "n_features": float(len(feature_names)),
    }, importance_df


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    df = load_data(args.enriched_data)
    train_df, test_df = split_data(df)
    patterns = _normalize_patterns(args.patterns)
    if not patterns:
        raise ValueError("At least one pattern must be provided.")

    summary_rows: list[dict[str, object]] = []

    output_dir = args.output_dir
    contexts = (
        df[["execution_timeframe", "strategy_archetype"]]
        .drop_duplicates()
        .itertuples(index=False)
    )

    for context in contexts:
        timeframe = context.execution_timeframe
        archetype = context.strategy_archetype
        key = f"{timeframe}_{archetype}"

        train_subset = train_df[
            (train_df["execution_timeframe"] == timeframe)
            & (train_df["strategy_archetype"] == archetype)
        ]
        test_subset = test_df[
            (test_df["execution_timeframe"] == timeframe)
            & (test_df["strategy_archetype"] == archetype)
        ]

        result = evaluate_context(
            train_subset,
            test_subset,
            patterns,
            random_state=args.random_state,
            n_estimators=args.n_estimators,
        )

        if result is None:
            continue
        metrics, importance_df = result

        row: dict[str, object] = {"context": key}
        row.update(metrics)
        summary_rows.append(row)

        if importance_df is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            importance_path = output_dir / f"{key}_feature_importance.csv"
            importance_df.to_csv(importance_path, index=False)

    output_dir.mkdir(parents=True, exist_ok=True)

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_path = output_dir / "engineered_feature_evaluation.csv"
        summary_df.to_csv(summary_path, index=False)
        print(f"Wrote engineered feature evaluation to {summary_path}")
    else:
        print("No contexts produced evaluation results.")


if __name__ == "__main__":  # pragma: no cover
    main()
