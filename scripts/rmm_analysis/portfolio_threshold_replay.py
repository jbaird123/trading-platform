"""Portfolio replay comparing baseline vs. threshold-filtered trades."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

if __package__ is None or __package__ == "":  # pragma: no cover
    import sys

    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from scripts.rmm_analysis.grid_feature_pattern_search import (  # noqa: E402
    _prepare_xy,
    collect_patterns,
    load_data,
    split_data,
)


@dataclass
class ContextConfig:
    context: str
    group_combo: str
    threshold: float
    model: str
    gating: str


DEFAULT_MODEL = "logistic"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay profitability trades with threshold filters and compare "
            "baseline vs. filtered portfolio metrics."
        )
    )
    parser.add_argument(
        "--enriched-data",
        required=True,
        type=Path,
        help="Path to master_trade_log.parquet (enriched trades).",
    )
    parser.add_argument(
        "--threshold-config",
        required=True,
        type=Path,
        help="CSV with context, group_combo, threshold columns.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write summary and equity curves.",
    )
    parser.add_argument(
        "--context-model",
        action="append",
        default=None,
        help=(
            "Optional overrides of model per context. Format: context=model. "
            "Supported models: logistic, gb_weighted."
        ),
    )
    parser.add_argument(
        "--context-gate",
        action="append",
        default=None,
        help=(
            "Optional gating expressions per context. Format: context=expr. "
            "Expressions use pandas.eval syntax referencing columns such as "
            "atr_percentile, prior_return, alignment_score, volume_ratio, "
            "session_london, session_newyork, alignment_full."
        ),
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for classifiers (default: 42).",
    )
    return parser.parse_args(argv)


def _parse_overrides(pairs: Iterable[str] | None) -> dict[str, str]:
    overrides: dict[str, str] = {}
    if not pairs:
        return overrides
    for pair in pairs:
        if "=" not in pair:
            continue
        ctx, value = pair.split("=", 1)
        overrides[ctx.strip()] = value.strip()
    return overrides


def _load_threshold_config(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"context", "group_combo", "threshold"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Threshold config missing columns: {missing}")
    return df


def _model_for_context(
    context: str, overrides: dict[str, str], default_model: str
) -> str:
    return overrides.get(context, default_model)


def _gating_for_context(context: str, overrides: dict[str, str]) -> str:
    return overrides.get(context, "true")


def _context_mask(df: pd.DataFrame, context: str) -> pd.Series:
    return (df["execution_timeframe"] + "_" + df["strategy_archetype"]) == context


def _extract_context(df: pd.DataFrame, context: str) -> pd.DataFrame:
    return df.loc[_context_mask(df, context)].copy()


def _train_classifier(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    patterns: Iterable[str],
    model_name: str,
    *,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray]:
    X_train, X_test, y_train, y_test, _ = _prepare_xy(train_df, test_df, patterns)
    y_train_bin = (y_train > 0.0).astype(int)
    model = model_name.lower()

    if model == "logistic":
        pipeline = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                class_weight="balanced",
                max_iter=1000,
                random_state=random_state,
            ),
        )
        pipeline.fit(X_train, y_train_bin)
        proba = pipeline.predict_proba(X_test)[:, 1]
        return proba, y_test

    if model == "gb_weighted":
        gb = GradientBoostingClassifier(random_state=random_state)
        pos = y_train_bin.sum()
        neg = len(y_train_bin) - pos
        weight_pos = len(y_train_bin) / (2.0 * pos) if pos > 0 else 1.0
        weight_neg = len(y_train_bin) / (2.0 * neg) if neg > 0 else 1.0
        sample_weight = np.where(y_train_bin == 1, weight_pos, weight_neg)
        gb.fit(X_train, y_train_bin, sample_weight=sample_weight)
        proba = gb.predict_proba(X_test)[:, 1]
        return proba, y_test

    raise ValueError(f"Unsupported model: {model_name}")


def _resolve_higher_tf_prefix(timeframe: str) -> str:
    mapping = {
        "5min": "m15",
        "15min": "m15",
        "1h": "h1",
        "4h": "h4",
        "1d": "d1",
    }
    return mapping.get(timeframe.lower(), "m15")


def _series_or_default(
    df: pd.DataFrame, column: str, default_value: float | int = 0.0
) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series(default_value, index=df.index, dtype="float64")


def _gating_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            {
                "atr_percentile": [],
                "volume_ratio": [],
                "prior_return": [],
                "alignment_score": [],
                "alignment_full": [],
                "session_london": [],
                "session_newyork": [],
            }
        )

    timeframe = str(df["execution_timeframe"].iloc[0]).lower()
    prefix = _resolve_higher_tf_prefix(timeframe)

    atr_col = f"context_at_entry_global_features_{prefix}_atr_percentile_100"
    vol_col = f"context_at_entry_global_features_{prefix}_volume_sma_ratio_20"
    prior_col = f"context_at_entry_global_features_{prefix}_prior_return_1"
    align_score_col = (
        f"context_at_entry_global_features_{prefix}_trend_alignment_stack_score"
    )
    align_full_col = (
        f"context_at_entry_global_features_{prefix}_trend_alignment_full_alignment"
    )
    session_london_col = (
        f"context_at_entry_global_features_{prefix}_calendar_session_london"
    )
    session_newyork_col = (
        f"context_at_entry_global_features_{prefix}_calendar_session_newyork"
    )

    atr_series = _series_or_default(df, atr_col, default_value=np.nan)
    volume_series = _series_or_default(df, vol_col, default_value=np.nan)
    prior_series = _series_or_default(df, prior_col, default_value=np.nan)
    align_score_series = _series_or_default(df, align_score_col, default_value=np.nan)
    align_full_series = _series_or_default(df, align_full_col, default_value=0.0)
    london_series = _series_or_default(df, session_london_col, default_value=0.0)
    newyork_series = _series_or_default(df, session_newyork_col, default_value=0.0)

    columns = {
        "atr_percentile": atr_series,
        "volume_ratio": volume_series,
        "prior_return": prior_series,
        "alignment_score": align_score_series,
        "alignment_full": (align_full_series > 0.0),
        "session_london": (london_series > 0.0),
        "session_newyork": (newyork_series > 0.0),
    }
    return pd.DataFrame(columns, index=df.index)


def _evaluate_gating(expr: str, gating_df: pd.DataFrame) -> np.ndarray:
    expr_clean = expr.strip().lower()
    if expr_clean in {"", "true", "none"}:
        return np.ones(len(gating_df), dtype=bool)
    return gating_df.eval(expr, engine="python").to_numpy(dtype=bool)


def _metrics(mask: np.ndarray, y: np.ndarray) -> dict[str, float]:
    if mask.sum() == 0:
        return {
            "count": 0.0,
            "fraction": 0.0,
            "mean_r": float("nan"),
            "median_r": float("nan"),
            "win_rate": float("nan"),
            "sum_r": 0.0,
        }
    selected = y[mask]
    return {
        "count": float(mask.sum()),
        "fraction": float(mask.mean()),
        "mean_r": float(np.mean(selected)),
        "median_r": float(np.median(selected)),
        "win_rate": float(np.mean(selected > 0.0)),
        "sum_r": float(np.sum(selected)),
    }


def _equity_curve(
    times: pd.Series, r_values: np.ndarray, mask: np.ndarray
) -> pd.DataFrame:
    order = np.argsort(times.to_numpy())
    baseline_equity = np.cumsum(r_values[order])
    filtered_equity = np.cumsum(r_values[order] * mask[order])
    return pd.DataFrame(
        {
            "entry_time": times.to_numpy()[order],
            "baseline_equity": baseline_equity,
            "filtered_equity": filtered_equity,
            "included": mask[order].astype(int),
        }
    )


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    thresholds_df = _load_threshold_config(args.threshold_config)
    model_override = _parse_overrides(args.context_model)
    gating_override = _parse_overrides(args.context_gate)

    data = load_data(args.enriched_data)
    train_df, test_df = split_data(data)

    summary_rows: list[dict[str, object]] = []
    equity_tables: dict[str, pd.DataFrame] = {}

    for _, row in thresholds_df.iterrows():
        context = row["context"]
        group_combo = row["group_combo"]
        threshold = float(row["threshold"])
        row_model = str(row.get("model", DEFAULT_MODEL))
        row_gating_expr = str(row.get("gating_expression", "true"))
        model_name = _model_for_context(context, model_override, row_model)
        gating_expr = gating_override.get(context, row_gating_expr)

        train_ctx = _extract_context(train_df, context)
        test_ctx = _extract_context(test_df, context)
        if test_ctx.empty:
            continue

        patterns = collect_patterns(group_combo.split("+"))
        proba, y_test = _train_classifier(
            train_ctx,
            test_ctx,
            patterns,
            model_name,
            random_state=args.random_state,
        )

        include_mask = proba >= threshold
        gating_mask = _evaluate_gating(gating_expr, _gating_frame(test_ctx))
        combined_mask = include_mask & gating_mask

        baseline_stats = _metrics(np.ones(len(y_test), dtype=bool), y_test)
        filtered_stats = _metrics(combined_mask, y_test)

        summary_rows.append(
            {
                "context": context,
                "group_combo": group_combo,
                "model": model_name,
                "threshold": threshold,
                "gating_expression": gating_expr,
                "baseline_count": baseline_stats["count"],
                "baseline_fraction": baseline_stats["fraction"],
                "baseline_mean_r": baseline_stats["mean_r"],
                "baseline_median_r": baseline_stats["median_r"],
                "baseline_win_rate": baseline_stats["win_rate"],
                "baseline_sum_r": baseline_stats["sum_r"],
                "filtered_count": filtered_stats["count"],
                "filtered_fraction": filtered_stats["fraction"],
                "filtered_mean_r": filtered_stats["mean_r"],
                "filtered_median_r": filtered_stats["median_r"],
                "filtered_win_rate": filtered_stats["win_rate"],
                "filtered_sum_r": filtered_stats["sum_r"],
            }
        )

        entry_times = pd.to_datetime(test_ctx["entry_time"], utc=True).dt.tz_convert(
            None
        )
        equity_tables[context] = _equity_curve(
            entry_times,
            y_test,
            combined_mask,
        )

    if not summary_rows:
        print("No contexts evaluated; check threshold config or data.")
        return

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_df = pd.DataFrame(summary_rows)
    summary_path = output_dir / "portfolio_threshold_replay_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(summary_df.to_string(index=False))

    equity_dir = output_dir / "equity_curves"
    equity_dir.mkdir(parents=True, exist_ok=True)
    for context, table in equity_tables.items():
        path = equity_dir / f"{context}.csv"
        table.to_csv(path, index=False)


if __name__ == "__main__":  # pragma: no cover
    main()
