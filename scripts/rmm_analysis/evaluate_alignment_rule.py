from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

TEST_START = "2022-01-01"

SLOPE_COLUMNS = {
    "h1": "context_at_entry_global_features_h1_ema_50_slope_pct",
    "h4": "context_at_entry_global_features_h4_ema_50_slope_pct",
    "d1": "context_at_entry_global_features_d1_ema_50_slope_pct",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Evaluate deterministic slope-based rules on master trade log.")
    )
    parser.add_argument(
        "--enriched-data",
        required=True,
        type=Path,
        help="Path to master_trade_log.parquet (enriched trades).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="CSV path for rule metrics.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.0,
        help="Slope percentage threshold (default: 0).",
    )
    parser.add_argument(
        "--require-positive",
        action="store_true",
        help=("Require slope strictly greater than threshold for all " "timeframes."),
    )
    return parser.parse_args(argv)


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    return df[df["r_multiple"].notna()].copy()


def split_data(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["entry_time"] >= TEST_START
    return df.loc[mask].copy()


def evaluate_rule(df: pd.DataFrame, threshold: float, strict: bool) -> pd.DataFrame:
    contexts = (
        df[["execution_timeframe", "strategy_archetype"]]
        .drop_duplicates()
        .itertuples(index=False)
    )

    records: list[dict[str, float | str]] = []

    for context in contexts:
        timeframe = context.execution_timeframe
        archetype = context.strategy_archetype
        key = f"{timeframe}_{archetype}"

        subset = df[
            (df["execution_timeframe"] == timeframe)
            & (df["strategy_archetype"] == archetype)
        ].copy()

        if subset.empty:
            continue

        missing = [col for col in SLOPE_COLUMNS.values() if col not in subset.columns]
        if missing:
            continue

        def rule(row: pd.Series) -> bool:
            for col in SLOPE_COLUMNS.values():
                val = row.get(col)
                if val is None or np.isnan(val):
                    return False
                if strict:
                    if val <= threshold:
                        return False
                else:
                    if val < threshold:
                        return False
            return True

        subset["rule_positive"] = subset.apply(rule, axis=1)
        subset["actual_positive"] = subset["r_multiple"] > 0

        rule_positive = subset["rule_positive"]
        actual_positive = subset["actual_positive"]

        tp = int((rule_positive & actual_positive).sum())
        fp = int((rule_positive & ~actual_positive).sum())
        tn = int((~rule_positive & ~actual_positive).sum())
        fn = int((~rule_positive & actual_positive).sum())

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        accuracy = (tp + tn) / max(tp + tn + fp + fn, 1)
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        records.append(
            {
                "context": key,
                "precision": precision,
                "recall": recall,
                "accuracy": accuracy,
                "f1": f1,
                "tp": float(tp),
                "fp": float(fp),
                "tn": float(tn),
                "fn": float(fn),
                "predicted_positive": float(tp + fp),
                "total": float(len(subset)),
            }
        )

    return pd.DataFrame(records)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    df = load_data(args.enriched_data)
    test_df = split_data(df)
    result_df = evaluate_rule(test_df, args.threshold, args.require_positive)

    if result_df.empty:
        print("No contexts produced slope-rule metrics (missing columns?).")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(args.output, index=False)
    print(f"Wrote slope rule metrics to {args.output}")


if __name__ == "__main__":
    main()
