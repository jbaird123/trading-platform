"""Main orchestration script for data synchronization."""

from __future__ import annotations

import argparse
import glob
from datetime import date, timedelta
from pathlib import Path

from trading_platform.data.instrument import _INSTRUMENT_DEFINITIONS
from trading_platform.data.sync_service import (
    download_and_save_data,
    get_last_sync_date,
)


def main(args: list[str] | None = None) -> None:
    """Main function for data synchronization script.

    Args:
        args: Command line arguments. If None, uses sys.argv
    """
    parser = argparse.ArgumentParser(description="Synchronize market data")
    parser.add_argument("--symbol", type=str, help="Symbol to sync (e.g., EUR/USD)")
    parser.add_argument(
        "--all", action="store_true", help="Sync all defined instruments"
    )
    parser.add_argument(
        "--data-root", type=str, required=True, help="Root directory for data files"
    )

    parsed_args = parser.parse_args(args)

    data_root = Path(parsed_args.data_root)

    # Determine which symbols to process
    if parsed_args.all:
        symbols = list(_INSTRUMENT_DEFINITIONS.keys())
    elif parsed_args.symbol:
        symbols = [parsed_args.symbol]
    else:
        parser.error("Either --symbol or --all must be specified")

    # Process each symbol
    for symbol in symbols:
        process_symbol(symbol, data_root)


def process_symbol(symbol: str, data_root: Path) -> None:
    """Process synchronization for a single symbol.

    Args:
        symbol: The financial instrument symbol
        data_root: Root directory for data files
    """
    # Normalize symbol for file pattern matching
    # Convert "EUR/USD" to "eurusd" for filename matching
    normalized_symbol = symbol.replace("/", "").lower()

    # Find all existing data files for this symbol
    # Look in both full and incremental directories
    full_dir = data_root / "full"
    incremental_dir = data_root / "incremental" / normalized_symbol

    # Collect all CSV files
    files: list[Path] = []

    if full_dir.exists():
        pattern = f"{normalized_symbol}_*.csv"
        files.extend(Path(f) for f in glob.glob(str(full_dir / pattern)))

    if incremental_dir.exists():
        pattern = "*.csv"
        files.extend(Path(f) for f in glob.glob(str(incremental_dir / pattern)))

    # Get the last sync date
    last_sync_date = get_last_sync_date(files)

    if last_sync_date is None:
        # No existing data - could start from a default date
        # For now, skip symbols with no existing data
        return

    # Calculate new date range
    start_date = last_sync_date + timedelta(days=1)
    end_date = date.today() - timedelta(days=1)  # Yesterday

    # Only proceed if there are new days to fetch
    if start_date <= end_date:
        download_and_save_data(symbol, start_date, end_date, data_root)


if __name__ == "__main__":
    main()
