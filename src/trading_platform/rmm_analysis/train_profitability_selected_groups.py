"""Train profitability models for selected feature group combinations."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from trading_platform.rmm_analysis.grid_feature_pattern_search import (
    collect_patterns,
    evaluate_context,
    load_data,
    split_data,
)

DEFAULT_COMBOS = [
    "calendar",
    "structure+volume",
    "alignment+structure",
    "volatility",
    "structure+momentum",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Retrain profitability models for selected feature group " "combinations."
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
        help="Directory to write metrics (CSV files).",
    )
    parser.add_argument(
        "--group-combo",
        action="append",
        default=None,
        help=(
            "Feature-group combination to evaluate (e.g., alignment+structure). "
            "Provide multiple times for multiple combos. "
            f"Defaults to: {', '.join(DEFAULT_COMBOS)}."
        ),
    )
    parser.add_argument(
        "--context",
        action="append",
        default=None,
        help=(
            "Specific context(s) to evaluate (e.g., 15min_trend_following). "
            "If omitted, all contexts present in the dataset are used."
        ),
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
        help=(
            "Write per-context feature importance CSVs alongside metrics for "
            "each combination."
        ),
    )
    return parser.parse_args(argv)


def _parse_combos(combo_values: Iterable[str] | None) -> list[tuple[str, ...]]:
    if not combo_values:
        combo_values = DEFAULT_COMBOS
    combos: list[tuple[str, ...]] = []
    for combo in combo_values:
        parts = combo.split("+")
        combos.append(tuple(parts))
    return combos


def _resolve_contexts(
    df: pd.DataFrame,
    explicit_contexts: Iterable[str] | None,
) -> list[tuple[str, str]]:
    if explicit_contexts:
        contexts: list[tuple[str, str]] = []
        for ctx in explicit_contexts:
            if "_" not in ctx:
                raise ValueError(
                    f"Context '{ctx}' must be formatted as " "<timeframe>_<archetype>."
                )
            timeframe, archetype = ctx.split("_", 1)
            contexts.append((str(timeframe), str(archetype)))
        return contexts
    unique = (
        df[["execution_timeframe", "strategy_archetype"]]
        .drop_duplicates()
        .itertuples(index=False)
    )
    return [
        (str(ctx.execution_timeframe), str(ctx.strategy_archetype)) for ctx in unique
    ]


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    combos = _parse_combos(args.group_combo)
    df = load_data(args.enriched_data)
    train_df, test_df = split_data(df)
    contexts = _resolve_contexts(df, args.context)
    records: list[dict[str, object]] = []
    output_dir = args.output_dir
    for combo in combos:
        patterns = collect_patterns(combo)
        combo_name = "+".join(combo)
        for timeframe, archetype in contexts:
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
                    "context": f"{timeframe}_{archetype}",
                    "group_combo": combo_name,
                    "pattern_count": len(patterns),
                }
            )
            records.append(metrics)
            if args.write_importances and importance_df is not None:
                context_dir = output_dir / "feature_importances" / combo_name
                context_dir.mkdir(parents=True, exist_ok=True)
                path = context_dir / f"{timeframe}_{archetype}.csv"
                importance_df.to_csv(path, index=False)
    if not records:
        print("No evaluations were produced.")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_df = pd.DataFrame(records)
    output_path = output_dir / "selected_group_metrics.csv"
    metrics_df.to_csv(output_path, index=False)
    print(f"Wrote metrics to {output_path}")


__all__ = [
    "DEFAULT_COMBOS",
    "parse_args",
    "_parse_combos",
    "_resolve_contexts",
    "main",
]
