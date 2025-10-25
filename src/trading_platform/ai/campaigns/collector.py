"""Campaign artifact collection using prescribed data/candidates/ structure."""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from trading_platform.ai.campaigns.models import ArtifactSummary, CandidateMetadata

logger = logging.getLogger(__name__)


def collect_campaign_artifacts(
    campaign_id: str, runs_dir: Path, data_root: Path | None = None
) -> ArtifactSummary:
    """Collect campaign artifacts to data/candidates/<campaign_id>/ structure.

    Args:
        campaign_id: Campaign identifier
        runs_dir: Base directory containing run outputs
        data_root: Root directory for data (defaults to current directory)

    Returns:
        ArtifactSummary with collection results
    """
    if data_root is None:
        data_root = Path.cwd()

    # Define candidates directory using prescribed structure
    candidates_dir = data_root / "data" / "candidates" / campaign_id
    candidates_dir.mkdir(parents=True, exist_ok=True)

    # Find all run directories for this campaign
    campaign_runs_dir = runs_dir / "campaigns" / campaign_id
    if not campaign_runs_dir.exists():
        logger.warning(f"Campaign runs directory not found: {campaign_runs_dir}")
        return ArtifactSummary(
            campaign_id=campaign_id,
            total_candidates=0,
            candidates_dir=Path("data/candidates") / campaign_id,
            collected_at=datetime.now(timezone.utc).isoformat(),
            candidates=[],
        )

    candidates = []

    # Process each run directory
    for run_dir in sorted(campaign_runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue

        brief_path = run_dir / "brief.json"
        if not brief_path.exists():
            logger.warning(f"brief.json not found in {run_dir.name}, skipping")
            continue

        # Load brief.json
        with open(brief_path) as f:
            brief = json.load(f)

        # Extract run_id from directory name
        run_id = run_dir.name

        # Extract metadata from brief
        meta = brief.get("meta", {})
        backtest_metrics = brief.get("backtest_metrics", {})
        trades = brief.get("trades", [])

        metadata = CandidateMetadata(
            run_id=run_id,
            strategy_archetype=meta.get("strategy_archetype", "unknown"),
            execution_timeframe=meta.get("execution_timeframe", "unknown"),
            total_pnl=backtest_metrics.get("total_pnl", 0.0),
            sharpe_ratio=backtest_metrics.get("sharpe_ratio"),
            win_rate=backtest_metrics.get("win_rate", 0.0),
            total_trades=len(trades),
            max_drawdown=backtest_metrics.get("max_drawdown", 0.0),
        )

        # Create candidate directory
        candidate_dir = candidates_dir / run_id
        candidate_dir.mkdir(parents=True, exist_ok=True)

        # Copy brief.json to candidate directory
        shutil.copy2(brief_path, candidate_dir / "brief.json")

        # Save metadata.json
        metadata_path = candidate_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata.model_dump(), f, indent=2)

        candidates.append(metadata)

        logger.info(f"Collected artifacts for {run_id}")

    # Create index.json
    index_path = candidates_dir / "index.json"
    with open(index_path, "w") as f:
        json.dump([c.model_dump() for c in candidates], f, indent=2)

    # Create and return summary
    return ArtifactSummary(
        campaign_id=campaign_id,
        total_candidates=len(candidates),
        candidates_dir=Path("data/candidates") / campaign_id,
        collected_at=datetime.now(timezone.utc).isoformat(),
        candidates=candidates,
    )
