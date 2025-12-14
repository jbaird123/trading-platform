"""Generate threshold recommendations ranked by shortest drawdown duration.

This module creates threshold_recommendations_drawdown.csv alongside
the existing threshold_recommendations.csv (which ranks by R-multiple).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate threshold recommendations ranked by drawdown duration."
    )
    parser.add_argument(
        "--drawdown-csv",
        required=True,
        type=Path,
        help="Path to threshold_drawdown.csv from drawdown analysis.",
    )
    parser.add_argument(
        "--output-csv",
        required=True,
        type=Path,
        help="CSV path for drawdown-based recommendations.",
    )
    parser.add_argument(
        "--min-n-runs",
        type=int,
        default=3,
        help="Minimum number of runs required for a recommendation (default: 3).",
    )
    parser.add_argument(
        "--min-trades-per-run",
        type=float,
        default=5.0,
        help="Minimum median trades per run (default: 5).",
    )
    parser.add_argument(
        "--require-positive-pnl",
        action="store_true",
        default=True,
        help="Only recommend thresholds with positive mean PnL (default: True).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    df = pd.read_csv(args.drawdown_csv)
    df = df.replace({np.inf: np.nan, -np.inf: np.nan})

    # Filter by minimum quality criteria
    filtered = df[df["n_runs"] >= args.min_n_runs].copy()
    filtered = filtered[filtered["median_n_trades"] >= args.min_trades_per_run]

    if args.require_positive_pnl:
        filtered = filtered[filtered["mean_total_pnl"] > 0]

    if filtered.empty:
        print("No thresholds meet quality criteria. Relaxing filters...")
        filtered = df[df["n_runs"] >= 1].copy()

    # Rank by shortest median max drawdown duration (primary goal)
    # Secondary: lowest time in drawdown
    ranked = (
        filtered.sort_values(
            ["context", "median_max_dd_duration_days", "median_time_in_dd_pct"],
            ascending=[True, True, True],
        )
        .groupby("context")
        .head(1)
    )

    output_cols = [
        "context",
        "threshold",
        "n_runs",
        "median_max_dd_duration_days",
        "max_max_dd_duration_days",
        "median_time_in_dd_pct",
        "mean_total_pnl",
        "median_n_trades",
    ]
    ranked = ranked[[c for c in output_cols if c in ranked.columns]]

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(args.output_csv, index=False)
    print(f"Wrote drawdown-based recommendations to {args.output_csv}")


__all__ = ["parse_args", "main"]
