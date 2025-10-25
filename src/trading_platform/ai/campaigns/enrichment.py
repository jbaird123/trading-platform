"""Campaign enrichment stage - creates intermediate rich trades dataset."""

import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from trading_platform.core import paths

from .models import EnrichmentResult
from .review import get_approved_candidates


def enrich_campaign_dataset(campaign_id: str) -> EnrichmentResult:
    """Enrich approved candidates to create intermediate dataset.

    Args:
        campaign_id: Campaign identifier

    Returns:
        EnrichmentResult with enrichment summary
    """
    # Get approved candidates
    approved_run_ids = get_approved_candidates(campaign_id)

    # Define paths
    candidates_dir = paths.PROJECT_ROOT / "data" / "candidates" / campaign_id
    output_dir = paths.PROJECT_ROOT / "data" / "enriched" / campaign_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "rich_trades.parquet"

    # Create temporary directory for approved briefs only
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy only approved candidate briefs
        for run_id in approved_run_ids:
            src_brief = candidates_dir / run_id / "brief.json"
            if src_brief.exists():
                dst_brief = temp_path / f"{run_id}.json"
                shutil.copy(src_brief, dst_brief)

        # Build ai-curate-data command
        cmd = [
            "poetry",
            "run",
            "tp",
            "ai-curate-data",
            "--source-dir",
            str(temp_path),
            "--output-file",
            str(output_path),
        ]

        # Execute subprocess
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    # Load enriched parquet
    df = pd.read_parquet(output_path)

    # Add campaign metadata columns
    # Build metadata lookup
    metadata_lookup = {}
    for run_id in approved_run_ids:
        brief_path = candidates_dir / run_id / "brief.json"
        if brief_path.exists():
            with open(brief_path) as f:
                brief = json.load(f)

            meta = brief.get("meta", {})
            metadata_lookup[run_id] = {
                "strategy_archetype": meta.get("strategy_archetype", "unknown"),
                "execution_timeframe": meta.get("execution_timeframe", "unknown"),
            }

    # Add metadata columns to dataframe
    df["campaign_id"] = campaign_id
    # Extract run_id from trade_id (assuming format: run_id_tX)
    df["run_id"] = df["trade_id"].str.split("_").str[0:2].str.join("_")

    # Map metadata to dataframe rows
    df["strategy_archetype"] = df["run_id"].map(
        lambda rid: metadata_lookup.get(rid, {}).get("strategy_archetype", "unknown")
    )
    df["execution_timeframe"] = df["run_id"].map(
        lambda rid: metadata_lookup.get(rid, {}).get("execution_timeframe", "unknown")
    )

    # Save updated parquet
    df.to_parquet(output_path)

    # Create result
    result = EnrichmentResult(
        campaign_id=campaign_id,
        approved_candidates=len(approved_run_ids),
        total_trades_enriched=len(df),
        output_path=output_path,
        enriched_at=datetime.now(timezone.utc).isoformat(),
    )

    return result
