#!/usr/bin/env python3
"""
Validate that brief context features match the global feature cache.

This script compares context_at_entry and context_at_exit features in campaign
briefs against the corresponding records in the global feature cache to identify
where discrepancies are introduced in the pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.progress import track
from rich.table import Table

console = Console()

TIMEFRAME_TO_CACHE_FILE = {
    "5min": "5min.parquet",
    "15min": "15min.parquet",
    "1H": "1h.parquet",
    "4H": "4h.parquet",
    "1D": "1d.parquet",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate brief context features against global feature cache"
    )
    parser.add_argument(
        "--brief",
        type=Path,
        required=True,
        help="Path to brief.json file",
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
        help="Number of trades to validate (default: all)",
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
        "--timeframe",
        type=str,
        choices=list(TIMEFRAME_TO_CACHE_FILE.keys()),
        required=True,
        help="Execution timeframe for this brief",
    )
    return parser.parse_args()


def load_cache(cache_dir: Path, timeframe: str) -> pd.DataFrame:
    """Load cache file for given timeframe."""
    cache_file = TIMEFRAME_TO_CACHE_FILE[timeframe]
    cache_path = cache_dir / cache_file

    if not cache_path.exists():
        raise FileNotFoundError(f"Cache file not found: {cache_path}")

    df = pd.read_parquet(cache_path)
    df["available_at"] = pd.to_datetime(df["available_at"])
    df = df.set_index("available_at").sort_index()

    return df


def get_cache_record(
    cache: pd.DataFrame,
    timestamp: pd.Timestamp,
) -> pd.Series | None:
    """Get cache record for given timestamp."""
    if timestamp in cache.index:
        return cache.loc[timestamp]
    return None


def compare_features(
    brief_features: dict[str, Any],
    cache_record: pd.Series,
    tolerance: float,
) -> tuple[int, int, list[dict[str, Any]]]:
    """
    Compare brief features against cache record.

    Returns:
        (matches, total_checked, mismatches_list)
    """
    matches = 0
    total = 0
    mismatches = []

    for feature_name, brief_val in brief_features.items():
        if feature_name not in cache_record.index:
            continue

        cache_val = cache_record[feature_name]
        total += 1

        # Handle NaN comparison
        if pd.isna(brief_val) and pd.isna(cache_val):
            matches += 1
            continue

        if pd.isna(brief_val) or pd.isna(cache_val):
            mismatches.append(
                {
                    "feature": feature_name,
                    "brief_value": brief_val,
                    "cache_value": cache_val,
                    "error": "NaN mismatch",
                }
            )
            continue

        # Numeric comparison with tolerance
        try:
            diff = abs(float(brief_val) - float(cache_val))
            if diff <= tolerance:
                matches += 1
            else:
                mismatches.append(
                    {
                        "feature": feature_name,
                        "brief_value": brief_val,
                        "cache_value": cache_val,
                        "diff": diff,
                        "error": f"Value mismatch (diff: {diff:.8f})",
                    }
                )
        except (ValueError, TypeError):
            # Non-numeric comparison
            if brief_val == cache_val:
                matches += 1
            else:
                mismatches.append(
                    {
                        "feature": feature_name,
                        "brief_value": brief_val,
                        "cache_value": cache_val,
                        "error": "Value mismatch",
                    }
                )

    return matches, total, mismatches


def validate_brief(
    brief_path: Path,
    cache: pd.DataFrame,
    sample_size: int | None,
    tolerance: float,
    show_mismatches: bool,
) -> dict[str, Any]:
    """Validate brief trades against cache."""

    console.print(f"\n[cyan]Loading brief from {brief_path}...[/cyan]")

    with open(brief_path) as f:
        brief = json.load(f)

    trades = brief["trades"]
    if sample_size:
        trades = trades[:sample_size]

    console.print(f"  Validating {len(trades)} trades")

    results = {
        "total_trades": len(trades),
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
        enumerate(trades),
        total=len(trades),
        description="Validating trades",
    ):
        entry_time = pd.to_datetime(trade["entry_time"])
        exit_time = pd.to_datetime(trade["exit_time"])

        trade_result = {
            "trade_idx": idx,
            "entry_time": str(entry_time),
            "exit_time": str(exit_time),
            "entry_valid": False,
            "exit_valid": False,
            "entry_mismatches": [],
            "exit_mismatches": [],
        }

        # Validate entry context
        entry_cache = get_cache_record(cache, entry_time)
        if entry_cache is None:
            results["entry_missing_cache"] += 1
            trade_result["entry_error"] = f"Cache record not found for {entry_time}"
        else:
            brief_features = trade["context_at_entry"]["global_features"]
            matches, total, mismatches = compare_features(
                brief_features, entry_cache, tolerance
            )
            results["entry_matches"] += matches
            results["entry_total"] += total
            trade_result["entry_matches"] = matches
            trade_result["entry_total"] = total
            trade_result["entry_valid"] = len(mismatches) == 0
            trade_result["entry_mismatches"] = mismatches

        # Validate exit context
        exit_cache = get_cache_record(cache, exit_time)
        if exit_cache is None:
            results["exit_missing_cache"] += 1
            trade_result["exit_error"] = f"Cache record not found for {exit_time}"
        else:
            brief_features = trade["context_at_exit"]["global_features"]
            matches, total, mismatches = compare_features(
                brief_features, exit_cache, tolerance
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

        # Show mismatches or missing records if requested
        if show_mismatches and (
            trade_result["entry_mismatches"]
            or trade_result["exit_mismatches"]
            or "entry_error" in trade_result
            or "exit_error" in trade_result
        ):
            console.print(f"\n[yellow]Trade {idx}[/yellow]")
            console.print(f"  Entry: {entry_time}")
            console.print(f"  Exit: {exit_time}")

            if "entry_error" in trade_result:
                console.print(f"  [red]{trade_result['entry_error']}[/red]")
            if "exit_error" in trade_result:
                console.print(f"  [red]{trade_result['exit_error']}[/red]")

            if trade_result["entry_mismatches"]:
                console.print("  [red]Entry mismatches:[/red]")
                for mm in trade_result["entry_mismatches"][:5]:  # Show first 5
                    brief_val = mm.get("brief_value", "N/A")
                    cache_val = mm.get("cache_value", "N/A")
                    if isinstance(brief_val, (int, float)) and isinstance(
                        cache_val, (int, float)
                    ):
                        console.print(
                            f"    {mm['feature']}: "
                            f"brief={brief_val:.8f} "
                            f"cache={cache_val:.8f} "
                            f"diff={mm.get('diff', 0):.8e}"
                        )
                    else:
                        console.print(
                            f"    {mm['feature']}: "
                            f"brief={brief_val} cache={cache_val}"
                        )

            if trade_result["exit_mismatches"]:
                console.print("  [red]Exit mismatches:[/red]")
                for mm in trade_result["exit_mismatches"][:5]:  # Show first 5
                    brief_val = mm.get("brief_value", "N/A")
                    cache_val = mm.get("cache_value", "N/A")
                    if isinstance(brief_val, (int, float)) and isinstance(
                        cache_val, (int, float)
                    ):
                        console.print(
                            f"    {mm['feature']}: "
                            f"brief={brief_val:.8f} "
                            f"cache={cache_val:.8f} "
                            f"diff={mm.get('diff', 0):.8e}"
                        )
                    else:
                        console.print(
                            f"    {mm['feature']}: "
                            f"brief={brief_val} cache={cache_val}"
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
        console.print(
            "[green]Briefs match cache perfectly - "
            "issue is in publisher/enrichment[/green]"
        )
    else:
        failed = results["total_trades"] - results["validated_trades"]
        console.print(
            f"\n[bold yellow]⚠ {failed} trades have validation issues[/bold yellow]"
        )
        console.print(
            "[yellow]Briefs don't match cache - issue is in backtester[/yellow]"
        )


def main() -> int:
    args = parse_args()

    # Validate paths
    if not args.brief.exists():
        console.print(f"[red]Error: Brief not found: {args.brief}[/red]")
        return 1

    if not args.cache_dir.exists():
        console.print(f"[red]Error: Cache directory not found: {args.cache_dir}[/red]")
        return 1

    # Load cache
    console.print(f"\n[cyan]Loading {args.timeframe} cache...[/cyan]")
    try:
        cache = load_cache(args.cache_dir, args.timeframe)
        console.print(f"  ✓ Loaded {len(cache):,} cache records")
    except Exception as e:
        console.print(f"[red]Error loading cache: {e}[/red]")
        return 1

    # Run validation
    results = validate_brief(
        args.brief,
        cache,
        args.sample_size,
        args.tolerance,
        args.show_mismatches,
    )

    # Print summary
    print_summary(results)

    # Return exit code
    if results["validated_trades"] == results["total_trades"]:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
