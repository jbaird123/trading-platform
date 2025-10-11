"""ML data curation pipeline for extracting training data from backtest results."""

import json
from pathlib import Path

import pandas as pd

from trading_platform.ai.feature_engineering.trade_extractor import (
    extract_trades_from_brief,
)


def run_curation_pipeline(source_dir: Path, output_file: Path) -> None:
    """
    Aggregate trade data from multiple brief.json files into a single dataset.

    Args:
        source_dir: Directory to recursively search for brief.json files
        output_file: Path where the aggregated parquet file will be saved
    """
    # Find all brief.json files
    brief_files = list(source_dir.rglob("brief.json"))

    if not brief_files:
        print(f"No brief.json files found in {source_dir}")
        return

    # Collect DataFrames from each brief
    dfs = []
    for brief_path in brief_files:
        try:
            with open(brief_path) as f:
                brief_data = json.load(f)

            df = extract_trades_from_brief(brief_data)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            print(f"Warning: Failed to process {brief_path}: {e}")
            continue

    if not dfs:
        print("No trades extracted from any briefs")
        return

    # Concatenate all DataFrames
    aggregated_df = pd.concat(dfs, ignore_index=True)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save to parquet
    aggregated_df.to_parquet(output_file)
    print(
        f"Curated {len(aggregated_df)} trades from {len(brief_files)} "
        f"briefs to {output_file}"
    )
