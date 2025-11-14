"""Select per-context recommendations from profitability metrics."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

DEFAULT_MIN_FRACTION = 0.01


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Select per-context threshold recommendations from profitability "
            "analysis results."
        )
    )
    parser.add_argument(
        "--profitability-csv",
        required=True,
        type=Path,
        help="Path to threshold_profitability.csv output.",
    )
    parser.add_argument(
        "--output-csv",
        required=True,
        type=Path,
        help="Path to write recommendations CSV.",
    )
    parser.add_argument(
        "--min-selected-fraction",
        type=float,
        default=DEFAULT_MIN_FRACTION,
        help="Minimum coverage fraction to consider (default: 0.01).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    df = pd.read_csv(args.profitability_csv)
    df = df.replace({np.inf: np.nan, -np.inf: np.nan})

    filtered = df[df["selected_fraction"] >= args.min_selected_fraction].copy()
    if filtered.empty:
        filtered = df.copy()

    ranked = (
        filtered.sort_values(
            ["context", "mean_r_multiple_selected", "win_rate_selected"],
            ascending=[True, False, False],
        )
        .groupby("context")
        .head(1)
    )

    output_cols = ["context", "group_combo"]
    if "model" in ranked.columns:
        output_cols.append("model")
    output_cols.extend(
        [
            "threshold",
            "selected_fraction",
            "mean_r_multiple_selected",
            "win_rate_selected",
            "lift_mean_r_multiple",
            "lift_win_rate",
        ]
    )
    ranked = ranked[output_cols]
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(args.output_csv, index=False)
    print(f"Wrote threshold recommendations to {args.output_csv}")


__all__ = ["DEFAULT_MIN_FRACTION", "parse_args", "main"]
