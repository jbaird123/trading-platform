"""Generate diagnostic summaries for trained models.

Wraps trading_platform.ai.pipeline.diagnostic_collector.collect_diagnostic_contexts
so we can capture feature bounds and top features for existing models without
rerunning the entire pipeline.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from trading_platform.ai.models import ModelRegistry
from trading_platform.ai.pipeline.diagnostic_collector import (
    collect_diagnostic_contexts,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export diagnostic summaries using existing models."
    )
    parser.add_argument(
        "--enriched-data",
        required=True,
        type=Path,
        help="Path to enriched trade log (e.g., master_trade_log.parquet).",
    )
    parser.add_argument(
        "--model-dir",
        required=True,
        type=Path,
        help="Model directory (e.g., data/dvc/ml/models).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Where to write diagnostic summaries (JSON).",
    )
    parser.add_argument(
        "--lower-quantile",
        type=float,
        default=0.25,
        help="Lower quantile for feature bounds (default: 0.25).",
    )
    parser.add_argument(
        "--upper-quantile",
        type=float,
        default=0.75,
        help="Upper quantile for feature bounds (default: 0.75).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    registry = ModelRegistry(model_dir=args.model_dir)
    registry.load()
    collect_diagnostic_contexts(
        enriched_path=args.enriched_data,
        registry=registry,
        output_dir=args.output_dir,
        lower_quantile=args.lower_quantile,
        upper_quantile=args.upper_quantile,
    )
    print(f"Diagnostic summaries written to {args.output_dir}")


if __name__ == "__main__":  # pragma: no cover
    main()
