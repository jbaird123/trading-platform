"""Grid search over engineered feature pattern groups for profitability models."""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path
from typing import Iterable, Sequence

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

DEFAULT_GROUPS = {
    "alignment": [
        "trend_alignment",
        "ema_50_slope_pct",
        "ema_50_distance_pct",
    ],
    "volatility": [
        "atr_percentile",
        "atr_slope_pct",
        "bb_width_percentile",
        "range_atr_ratio",
        "true_range_zscore",
    ],
    "structure": [
        "close_to_hhv",
        "close_to_llv",
        "hhv_20_slope",
        "llv_20_slope",
    ],
    "momentum": [
        "rsi_bias",
        "rsi_slope",
        "roc_",
        "prior_return",
    ],
    "volume": [
        "volume_sma_ratio",
    ],
    "calendar": [
        "calendar",
        "day_of_week",
    ],
}


def _augment_risk_features(df: pd.DataFrame) -> pd.DataFrame:
    if "initial_stop_loss_price" not in df.columns or "entry_price" not in df.columns:
        df["risk_distance_abs"] = np.nan
        df["risk_distance_pct_entry"] = np.nan
        df["risk_distance_atr_ratio"] = np.nan
        return df
    risk_distance = (df["entry_price"] - df["initial_stop_loss_price"]).abs()
    df["risk_distance_abs"] = risk_distance
    entry_abs = df["entry_price"].abs().replace(0, np.nan)
    df["risk_distance_pct_entry"] = np.divide(risk_distance, entry_abs)
    if "context_at_entry_strategy_features_atr_14" in df.columns:
        atr = df["context_at_entry_strategy_features_atr_14"].replace(0, np.nan)
        df["risk_distance_atr_ratio"] = np.divide(risk_distance, atr)
    else:
        df["risk_distance_atr_ratio"] = np.nan
    return df


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run profitability evaluation across combinations of engineered "
            "feature pattern groups."
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
        help="Directory to write grid search results.",
    )
    parser.add_argument(
        "--groups",
        nargs="*",
        default=list(DEFAULT_GROUPS.keys()),
        help=(
            "Subset of group names to include in the search "
            "(default: alignment volatility structure momentum volume calendar)."
        ),
    )
    parser.add_argument(
        "--max-combo-size",
        type=int,
        default=2,
        help="Maximum number of groups to combine for each evaluation (default: 2).",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=200,
        help="Number of trees for RandomForestRegressor (default: 200).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--write-importances",
        action="store_true",
        help="Write per-context feature importance CSVs for each combination.",
    )
    return parser.parse_args(argv)


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    df = df[df["r_multiple"].notna()].copy()
    df = _augment_risk_features(df)
    return df


def split_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_mask = (df["entry_time"] >= TRAIN_START) & (df["entry_time"] <= TRAIN_END)
    test_mask = df["entry_time"] >= TEST_START
    return df.loc[train_mask].copy(), df.loc[test_mask].copy()


def _collect_features(df: pd.DataFrame, patterns: Iterable[str]) -> pd.DataFrame:
    patterns = list(patterns)
    columns: list[str] = []
    for col in df.columns:
        if not col.startswith("context_at_entry"):
            continue
        lowered = col.lower()
        if any(pattern in lowered for pattern in patterns):
            columns.append(col)
    feature_frame = df[columns].copy()
    feature_frame["risk_distance_abs"] = df["risk_distance_abs"]
    feature_frame["risk_distance_pct_entry"] = df["risk_distance_pct_entry"]
    feature_frame["risk_distance_atr_ratio"] = df["risk_distance_atr_ratio"]
    feature_frame["hour_of_day"] = df["entry_time"].dt.hour
    feature_frame["day_of_week"] = df["entry_time"].dt.dayofweek
    categorical = pd.get_dummies(
        df[["side", "symbol"]],
        prefix=["side", "symbol"],
        drop_first=False,
        dummy_na=False,
    )
    feature_frame = pd.concat([feature_frame, categorical], axis=1)
    return feature_frame.dropna(axis=1, how="all")


def _prepare_xy(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    patterns: Iterable[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    train_features = _collect_features(train_df, patterns)
    test_features = _collect_features(test_df, patterns)
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
    patterns: Iterable[str],
    *,
    random_state: int,
    n_estimators: int,
) -> tuple[dict[str, object], pd.DataFrame | None] | None:
    if len(context_df_train) < 50 or len(context_df_test) < 30:
        return None
    X_train, X_test, y_train, y_test, feature_names = _prepare_xy(
        context_df_train, context_df_test, patterns
    )
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
    tn, fp, fn, tp = confusion_matrix(
        y_test_sign,
        sign_pred,
        labels=[0, 1],
    ).ravel()
    importance_df: pd.DataFrame | None = None
    if getattr(rf, "feature_importances_", None) is not None:
        importance_df = pd.DataFrame(
            {
                "feature": feature_names,
                "importance": rf.feature_importances_,
            }
        ).sort_values("importance", ascending=False)
    metrics: dict[str, object] = {
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
    }
    return metrics, importance_df


def generate_group_combinations(
    groups: list[str],
    max_size: int,
) -> list[tuple[str, ...]]:
    combos: list[tuple[str, ...]] = []
    for size in range(1, max_size + 1):
        combos.extend(itertools.combinations(groups, size))
    return combos


def collect_patterns(group_names: Iterable[str]) -> list[str]:
    patterns: list[str] = []
    for name in group_names:
        patterns.extend(DEFAULT_GROUPS[name])
    return patterns


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    missing_groups = [name for name in args.groups if name not in DEFAULT_GROUPS]
    if missing_groups:
        raise ValueError(f"Unknown group names: {missing_groups}")
    df = load_data(args.enriched_data)
    train_df, test_df = split_data(df)
    combos = generate_group_combinations(args.groups, args.max_combo_size)
    results: list[dict[str, object]] = []
    output_dir = args.output_dir
    contexts = list(
        df[["execution_timeframe", "strategy_archetype"]]
        .drop_duplicates()
        .itertuples(index=False)
    )
    for combo in combos:
        patterns = collect_patterns(combo)
        combo_name = "+".join(combo)
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
            metrics.update(
                {
                    "context": key,
                    "group_combo": combo_name,
                    "pattern_count": len(patterns),
                }
            )
            results.append(metrics)
            if args.write_importances and importance_df is not None:
                context_dir = output_dir / "feature_importances" / combo_name
                context_dir.mkdir(parents=True, exist_ok=True)
                importance_path = context_dir / f"{key}.csv"
                importance_df.to_csv(importance_path, index=False)
    if not results:
        print("No evaluations were produced.")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_df = pd.DataFrame(results)
    summary_path = output_dir / "grid_feature_patterns.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"Wrote grid search results to {summary_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
