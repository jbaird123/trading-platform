#!/usr/bin/env python3
"""
Validate that trade context features match the global feature cache.

This script compares all context_at_entry and context_at_exit features in the
master trade log against the corresponding records in the global feature cache
to ensure data consistency and integrity.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.progress import track
from rich.table import Table

console = Console()

# Timeframe mapping from execution timeframe to cache file
TIMEFRAME_TO_CACHE_FILE = {
    "5min": "5min.parquet",
    "15min": "15min.parquet",
    "1H": "1h.parquet",
    "4H": "4h.parquet",
    "1D": "1d.parquet",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate trade context features against global feature cache"
    )
    parser.add_argument(
        "--trade-log",
        type=Path,
        default=Path("data/dvc/processed/training_sets/master_trade_log.parquet"),
        help="Path to master trade log parquet file",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(
            "data/cache/global_features/eurusd/"
            "bed9c0d739baefcc0a27cb4ad6896f502a7ad23579172579efa2be53c55f3874"
        ),
        help="Path to global feature cache directory",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Number of trades to sample (default: all trades)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-6,
        help="Tolerance for floating point comparison (default: 1e-6)",
    )
    parser.add_argument(
        "--show-mismatches",
        action="store_true",
        help="Show detailed mismatch information",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path to save detailed validation report CSV",
    )
    return parser.parse_args()


def load_cache_files(cache_dir: Path) -> dict[str, pd.DataFrame]:
    """Load all cache files indexed by timeframe."""
    console.print(f"\n[cyan]Loading cache files from {cache_dir}...[/cyan]")

    caches = {}
    for timeframe, filename in TIMEFRAME_TO_CACHE_FILE.items():
        cache_path = cache_dir / filename
        if not cache_path.exists():
            console.print(
                f"[yellow]Warning: Cache file not found: {cache_path}[/yellow]"
            )
            continue

        df = pd.read_parquet(cache_path)
        # Convert available_at to datetime and set as index for fast lookup
        df["available_at"] = pd.to_datetime(df["available_at"])
        df = df.set_index("available_at").sort_index()
        caches[timeframe] = df
        console.print(f"  ✓ Loaded {timeframe}: {len(df):,} records")

    return caches


def get_cache_record(
    caches: dict[str, pd.DataFrame],
    timeframe: str,
    timestamp: pd.Timestamp,
) -> pd.Series | None:
    """Get cache record for given timeframe and timestamp."""
    if timeframe not in caches:
        return None

    cache = caches[timeframe]

    # Try exact match first
    if timestamp in cache.index:
        return cache.loc[timestamp]

    return None


def compare_features(
    trade_features: dict[str, Any],
    cache_record: pd.Series,
    prefix: str,
    tolerance: float,
) -> tuple[int, int, list[dict[str, Any]]]:
    """
    Compare trade features against cache record.

    Returns:
        (matches, total_checked, mismatches_list)
    """
    matches = 0
    total = 0
    mismatches = []

    for trade_col, trade_val in trade_features.items():
        # Extract the feature name from trade column
        # e.g., "context_at_entry_global_features_15min_ema_50" -> "15min_ema_50"
        if not trade_col.startswith(prefix):
            continue

        feature_name = trade_col.replace(f"{prefix}_global_features_", "")

        # Skip strategy features (they're not in cache)
        if "strategy_features" in trade_col:
            continue

        if feature_name not in cache_record.index:
            continue

        cache_val = cache_record[feature_name]
        total += 1

        # Handle NaN comparison
        if pd.isna(trade_val) and pd.isna(cache_val):
            matches += 1
            continue

        if pd.isna(trade_val) or pd.isna(cache_val):
            mismatches.append(
                {
                    "feature": feature_name,
                    "trade_value": trade_val,
                    "cache_value": cache_val,
                    "error": "NaN mismatch",
                }
            )
            continue

        # Numeric comparison with tolerance
        try:
            if abs(float(trade_val) - float(cache_val)) <= tolerance:
                matches += 1
            else:
                diff_val = abs(float(trade_val) - float(cache_val))
                mismatches.append(
                    {
                        "feature": feature_name,
                        "trade_value": trade_val,
                        "cache_value": cache_val,
                        "error": f"Value mismatch (diff: {diff_val:.8f})",
                    }
                )
        except (ValueError, TypeError):
            # Non-numeric comparison
            if trade_val == cache_val:
                matches += 1
            else:
                mismatches.append(
                    {
                        "feature": feature_name,
                        "trade_value": trade_val,
                        "cache_value": cache_val,
                        "error": "Value mismatch",
                    }
                )

    return matches, total, mismatches


def validate_trades(
    trades_df: pd.DataFrame,
    caches: dict[str, pd.DataFrame],
    tolerance: float,
    show_mismatches: bool,
) -> dict[str, Any]:
    """Validate all trades against cache."""

    console.print("\n[cyan]Validating trades against cache...[/cyan]")

    results = {
        "total_trades": len(trades_df),
        "validated_trades": 0,
        "entry_matches": 0,
        "entry_total": 0,
        "entry_missing_cache": 0,
        "exit_matches": 0,
        "exit_total": 0,
        "exit_missing_cache": 0,
        "trade_details": [],
    }

    for idx, trade in track(
        trades_df.iterrows(),
        total=len(trades_df),
        description="Validating trades",
    ):
        timeframe = trade["execution_timeframe"]
        entry_time = pd.to_datetime(trade["entry_time"])
        exit_time = pd.to_datetime(trade["exit_time"])

        trade_result = {
            "trade_idx": idx,
            "timeframe": timeframe,
            "entry_time": str(entry_time),
            "exit_time": str(exit_time),
            "entry_valid": False,
            "exit_valid": False,
            "entry_mismatches": [],
            "exit_mismatches": [],
        }

        # Validate entry context
        entry_cache = get_cache_record(caches, timeframe, entry_time)
        if entry_cache is None:
            results["entry_missing_cache"] += 1
            trade_result["entry_error"] = "Cache record not found"
        else:
            trade_features = {k: v for k, v in trade.items() if "context_at_entry" in k}
            matches, total, mismatches = compare_features(
                trade_features, entry_cache, "context_at_entry", tolerance
            )
            results["entry_matches"] += matches
            results["entry_total"] += total
            trade_result["entry_matches"] = matches
            trade_result["entry_total"] = total
            trade_result["entry_valid"] = len(mismatches) == 0
            trade_result["entry_mismatches"] = mismatches

        # Validate exit context
        exit_cache = get_cache_record(caches, timeframe, exit_time)
        if exit_cache is None:
            results["exit_missing_cache"] += 1
            trade_result["exit_error"] = "Cache record not found"
        else:
            trade_features = {k: v for k, v in trade.items() if "context_at_exit" in k}
            matches, total, mismatches = compare_features(
                trade_features, exit_cache, "context_at_exit", tolerance
            )
            results["exit_matches"] += matches
            results["exit_total"] += total
            trade_result["exit_matches"] = matches
            trade_result["exit_total"] = total
            trade_result["exit_valid"] = len(mismatches) == 0
            trade_result["exit_mismatches"] = mismatches

        if trade_result["entry_valid"] and trade_result["exit_valid"]:
            results["validated_trades"] += 1

        results["trade_details"].append(trade_result)

        # Show mismatches if requested
        if show_mismatches and (
            trade_result["entry_mismatches"] or trade_result["exit_mismatches"]
        ):
            console.print(f"\n[yellow]Trade {idx} ({timeframe})[/yellow]")
            if trade_result["entry_mismatches"]:
                console.print("  Entry mismatches:")
                for mm in trade_result["entry_mismatches"][:5]:  # Show first 5
                    console.print(
                        f"    {mm['feature']}: "
                        f"trade={mm['trade_value']:.6f} "
                        f"cache={mm['cache_value']:.6f}"
                    )
            if trade_result["exit_mismatches"]:
                console.print("  Exit mismatches:")
                for mm in trade_result["exit_mismatches"][:5]:  # Show first 5
                    console.print(
                        f"    {mm['feature']}: "
                        f"trade={mm['trade_value']:.6f} "
                        f"cache={mm['cache_value']:.6f}"
                    )

    return results


def print_summary(results: dict[str, Any]) -> None:
    """Print validation summary."""
    console.print("\n[bold cyan]Validation Summary[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total Trades", f"{results['total_trades']:,}")
    table.add_row("Fully Validated Trades", f"{results['validated_trades']:,}")

    # Entry validation
    table.add_section()
    table.add_row("[bold]Entry Context", "")
    table.add_row("  Features Checked", f"{results['entry_total']:,}")
    table.add_row("  Matches", f"{results['entry_matches']:,}")
    if results["entry_total"] > 0:
        entry_pct = (results["entry_matches"] / results["entry_total"]) * 100
        table.add_row("  Match Rate", f"{entry_pct:.2f}%")
    table.add_row("  Missing Cache Records", f"{results['entry_missing_cache']:,}")

    # Exit validation
    table.add_section()
    table.add_row("[bold]Exit Context", "")
    table.add_row("  Features Checked", f"{results['exit_total']:,}")
    table.add_row("  Matches", f"{results['exit_matches']:,}")
    if results["exit_total"] > 0:
        exit_pct = (results["exit_matches"] / results["exit_total"]) * 100
        table.add_row("  Match Rate", f"{exit_pct:.2f}%")
    table.add_row("  Missing Cache Records", f"{results['exit_missing_cache']:,}")

    console.print(table)

    # Overall status
    if results["validated_trades"] == results["total_trades"]:
        console.print("\n[bold green]✓ All trades validated successfully![/bold green]")
    else:
        failed = results["total_trades"] - results["validated_trades"]
        console.print(
            f"\n[bold yellow]⚠ {failed} trades have validation issues[/bold yellow]"
        )


def save_report(results: dict[str, Any], output_path: Path) -> None:
    """Save detailed validation report to CSV."""
    rows = []
    for detail in results["trade_details"]:
        row = {
            "trade_idx": detail["trade_idx"],
            "timeframe": detail["timeframe"],
            "entry_time": detail["entry_time"],
            "exit_time": detail["exit_time"],
            "entry_valid": detail["entry_valid"],
            "exit_valid": detail["exit_valid"],
            "entry_matches": detail.get("entry_matches", 0),
            "entry_total": detail.get("entry_total", 0),
            "exit_matches": detail.get("exit_matches", 0),
            "exit_total": detail.get("exit_total", 0),
            "entry_mismatch_count": len(detail["entry_mismatches"]),
            "exit_mismatch_count": len(detail["exit_mismatches"]),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    console.print(f"\n[green]Detailed report saved to: {output_path}[/green]")


def main() -> int:
    args = parse_args()

    # Validate paths
    if not args.trade_log.exists():
        console.print(f"[red]Error: Trade log not found: {args.trade_log}[/red]")
        return 1

    if not args.cache_dir.exists():
        console.print(f"[red]Error: Cache directory not found: {args.cache_dir}[/red]")
        return 1

    # Load data
    console.print(f"\n[cyan]Loading trade log from {args.trade_log}...[/cyan]")
    trades_df = pd.read_parquet(args.trade_log)

    if args.sample_size:
        trades_df = trades_df.sample(n=min(args.sample_size, len(trades_df)))
        console.print(f"  Sampled {len(trades_df):,} trades for validation")
    else:
        console.print(f"  Loaded {len(trades_df):,} trades")

    caches = load_cache_files(args.cache_dir)

    if not caches:
        console.print("[red]Error: No cache files loaded[/red]")
        return 1

    # Run validation
    results = validate_trades(trades_df, caches, args.tolerance, args.show_mismatches)

    # Print summary
    print_summary(results)

    # Save report if requested
    if args.output:
        save_report(results, args.output)

    # Return exit code
    if results["validated_trades"] == results["total_trades"]:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
