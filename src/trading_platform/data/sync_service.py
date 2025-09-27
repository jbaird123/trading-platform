"""Data synchronization service for automated market data updates."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path


def get_last_sync_date(files: list[Path]) -> date | None:
    """Extract the most recent 'toDate' from a list of data filenames.

    Args:
        files: List of Path objects representing data files with date ranges

    Returns:
        The most recent end date found in the filenames, or None if no dates found

    Example:
        Given files like ['eurusd_interval_min_1_20240101_20240531.csv'],
        extracts and returns date(2024, 5, 31)
    """
    if not files:
        return None

    # Pattern to match the date range in filenames like:
    # eurusd_interval_min_1_20240101_20240531.csv
    # Group 2 captures the 'toDate' (second date)
    date_pattern = r"(\d{8})_(\d{8})"

    latest_date = None

    for file_path in files:
        filename = file_path.name
        match = re.search(date_pattern, filename)

        if match:
            # Extract the toDate (second date group)
            to_date_str = match.group(2)

            # Parse the date string (YYYYMMDD format)
            try:
                file_date = datetime.strptime(to_date_str, "%Y%m%d").date()

                # Keep track of the most recent date
                if latest_date is None or file_date > latest_date:
                    latest_date = file_date

            except ValueError:
                # Skip files with invalid date formats
                continue

    return latest_date


def download_and_save_data(
    symbol: str, start_date: date, end_date: date, data_root: Path
) -> None:
    """Download and save market data for a given symbol and date range.

    Uses the dukascopy-python library to fetch minute-level data from
    Dukascopy and saves it in the expected format for the trading platform.

    Args:
        symbol: The financial instrument symbol (e.g., "EUR/USD")
        start_date: Start date for data download
        end_date: End date for data download
        data_root: Root directory where data files should be saved
    """
    from datetime import datetime

    from dukascopy_python import INTERVAL_MIN_1, OFFER_SIDE_BID, fetch

    # Validate date range
    today = date.today()
    if start_date > today:
        print(f"! Start date {start_date} is in the future")
        return

    if end_date > today:
        print(f"! Adjusting end date from {end_date} to {today}")
        end_date = today

    # Normalize symbol for file naming
    normalized_symbol = symbol.replace("/", "").lower()

    print(f"Downloading {symbol} data from {start_date} to {end_date}")

    try:
        # Convert dates to datetime objects for dukascopy-python
        # Note: end_date is interpreted as start of that day (not end of day)
        # to match reference implementation behavior
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())

        # Fetch data using dukascopy-python library
        print("  Fetching data from Dukascopy...")
        df = fetch(
            instrument=symbol,
            interval=INTERVAL_MIN_1,
            offer_side=OFFER_SIDE_BID,
            start=start_dt,
            end=end_dt,
        )

        if df is not None and not df.empty:
            print(f"    ✓ Got {len(df)} minute candles")

            # Save to incremental directory
            incremental_dir = data_root / "incremental" / normalized_symbol
            incremental_dir.mkdir(parents=True, exist_ok=True)

            filename = (
                f"{normalized_symbol}_interval_minute_1_"
                f"{start_date.strftime('%Y%m%d')}_"
                f"{end_date.strftime('%Y%m%d')}.csv"
            )
            output_path = incremental_dir / filename

            # Save DataFrame with timestamp index as column (to match expected format)
            df.reset_index().to_csv(output_path, index=False)
            print(f"✓ Saved {len(df)} minute candles to {output_path}")
        else:
            print("! No data was returned from Dukascopy")

    except Exception as e:
        print(f"! Error fetching data from Dukascopy: {e}")
        import traceback

        traceback.print_exc()
