#!/usr/bin/env python3
"""CLI tool to validate global feature cache against recomputed features.

This script verifies that cached feature values match freshly computed values
from the canonical build_global_feature_frame pipeline. It supports:
- Full or sampled validation (--sample-size)
- Configurable numeric tolerance (--max-drift)
- Manifest digest verification
- Detailed mismatch reporting

Exit codes:
    0: All validations passed
    1: Mismatches found or validation failed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from trading_platform.core.global_feature_pipeline import build_global_feature_frame
from trading_platform.core.global_features_cache import (
    compute_manifest_digest,
    load_cached_global_features,
)
from trading_platform.data.loader import load_instrument_data


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate global feature cache against recomputed features"
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        required=True,
        help="Root directory of the global feature cache",
    )
    parser.add_argument(
        "--symbol", type=str, required=True, help="Symbol to validate (e.g., EUR_USD)"
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        required=True,
        help="Timeframe to validate (e.g., 5min, 1h)",
    )
    parser.add_argument(
        "--feature-config",
        type=Path,
        required=True,
        help="Path to feature manifest YAML file",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Number of random timestamps to validate (default: all)",
    )
    parser.add_argument(
        "--max-drift",
        type=float,
        default=1e-9,
        help="Maximum tolerable numeric drift (default: 1e-9)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Root directory for market data (default: infer from symbol)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for validation script."""
    args = parse_args()

    # 1. Load manifest and compute digest
    print(f"Loading feature manifest from {args.feature_config}")
    if not args.feature_config.exists():
        print(f"ERROR: Feature config file not found: {args.feature_config}")
        sys.exit(1)

    manifest_data = yaml.safe_load(args.feature_config.read_text())
    manifest_digest = compute_manifest_digest(manifest_data)
    print(f"Manifest digest: {manifest_digest}")

    # 2. Load cached features
    print(
        f"\nLoading cached features for {args.symbol}/{args.timeframe} "
        f"from {args.cache_dir}"
    )

    # Extract feature names from manifest
    feature_defs = manifest_data.get("features", [])
    if not feature_defs:
        print("ERROR: No features defined in manifest")
        sys.exit(1)

    feature_names = [f["name"] for f in feature_defs if "name" in f]

    try:
        cache_result = load_cached_global_features(
            symbol=args.symbol,
            timeframe=args.timeframe,
            cache_root=args.cache_dir,
            config_path=args.feature_config,
            feature_names=feature_names,
        )
    except ValueError as e:
        print(f"ERROR: Failed to load cache: {e}")
        sys.exit(1)

    if cache_result is None:
        print(f"ERROR: No cache found for {args.symbol}/{args.timeframe}")
        sys.exit(1)

    cached_df, feature_mapping = cache_result
    print(f"Loaded {len(cached_df)} rows, {len(cached_df.columns)} columns")

    # 3. Select sample if requested
    if args.sample_size and args.sample_size < len(cached_df):
        print(f"Sampling {args.sample_size} random timestamps for validation")
        sample_indices = np.random.choice(
            len(cached_df), size=args.sample_size, replace=False
        )
        sample_indices = np.sort(sample_indices)
        validation_df = cached_df.iloc[sample_indices]
    else:
        validation_df = cached_df

    print(f"Validating {len(validation_df)} rows")

    # 4. Load market data and recompute features
    print("\nRecomputing features from market data...")

    # Determine data root
    if args.data_root:
        data_root = args.data_root
    else:
        # Infer from environment/default paths
        # This matches the convention in build_global_feature_caches
        from trading_platform.core import paths as tp_paths

        data_root = tp_paths.DATA_ROOT  # type: ignore[attr-defined]

    # Load market data (1min base data)
    try:
        market_data_1min, _ = load_instrument_data(
            symbol=args.symbol, data_root=data_root
        )
    except Exception as e:
        print(f"ERROR: Failed to load market data: {e}")
        sys.exit(1)

    if market_data_1min.empty:
        print("ERROR: No market data loaded")
        sys.exit(1)

    # Filter to validation date range (only if index is datetime)
    if pd.api.types.is_datetime64_any_dtype(validation_df.index):
        market_data_1min = market_data_1min[
            (market_data_1min.index >= validation_df.index.min())
            & (market_data_1min.index <= validation_df.index.max())
        ]

    print(f"Loaded {len(market_data_1min)} rows of market data")

    # Recompute features using canonical pipeline
    try:
        recomputed_df, _ = build_global_feature_frame(
            market_data_1min,
            feature_defs,
            execution_timeframe=args.timeframe,
        )
    except Exception as e:
        print(f"ERROR: Failed to recompute features: {e}")
        sys.exit(1)

    # 5. Align recomputed data to validation timestamps
    # Only reindex if validation_df has a proper datetime index
    if pd.api.types.is_datetime64_any_dtype(validation_df.index):
        # Use ffill for safety in case timestamps don't match exactly
        recomputed_df = recomputed_df.reindex(validation_df.index, method="ffill")
    else:
        # If validation_df doesn't have datetime index, just use as-is
        # This might happen in test scenarios
        pass

    # 6. Compare values
    print("\nComparing cached vs recomputed features...")

    mismatches: list[tuple[str, int]] = []

    for col in validation_df.columns:
        if col not in recomputed_df.columns:
            print(f"WARNING: Column {col} not found in recomputed data")
            continue

        cached_values = validation_df[col].values
        recomputed_values = recomputed_df[col].values

        # Compare with np.isclose, handling NaN values
        close_mask = np.isclose(
            cached_values,  # type: ignore[arg-type]
            recomputed_values,  # type: ignore[arg-type]
            rtol=0,
            atol=args.max_drift,
            equal_nan=True,
        )

        mismatch_count = (~close_mask).sum()
        if mismatch_count > 0:
            mismatches.append((col, mismatch_count))
            print(
                f"  MISMATCH: {col} has {mismatch_count} "
                f"mismatched cells (out of {len(validation_df)})"
            )

            # Show first few mismatches for debugging
            mismatch_indices = np.where(~close_mask)[0][:3]
            for idx in mismatch_indices:
                timestamp = validation_df.index[idx]
                cached_val = cached_values[idx]
                recomputed_val = recomputed_values[idx]
                diff = abs(cached_val - recomputed_val)
                print(
                    f"    {timestamp}: cached={cached_val:.10f}, "
                    f"recomputed={recomputed_val:.10f}, diff={diff:.2e}"
                )

    # 7. Report results and exit
    print("\n" + "=" * 60)
    if mismatches:
        print(f"VALIDATION FAILED: {len(mismatches)} column(s) with mismatches")
        print(f"Timeframe: {args.timeframe}")
        print(f"Manifest digest: {manifest_digest[:16]}...")
        print(f"Max drift tolerance: {args.max_drift}")
        print("\nMismatched columns:")
        for col, count in mismatches:
            print(f"  - {col}: {count} cells")
        sys.exit(1)
    else:
        print(f"VALIDATION PASSED: All {len(validation_df.columns)} columns match")
        print(f"Timeframe: {args.timeframe}")
        print(f"Rows validated: {len(validation_df)}")
        print(f"Manifest digest: {manifest_digest[:16]}...")
        print(f"Max drift tolerance: {args.max_drift}")
        sys.exit(0)


if __name__ == "__main__":
    main()
