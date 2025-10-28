"""Campaign enrichment stage - creates intermediate rich trades dataset."""

import json
from datetime import datetime, timezone

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

    # Load campaign plan to get strategy archetype and execution timeframe
    from trading_platform.ai.campaigns.models import CampaignPlan

    campaign_dir = paths.PROJECT_ROOT / "data" / "campaigns" / campaign_id
    plan_path = campaign_dir / "plan.json"
    with open(plan_path) as f:
        plan_dict = json.load(f)
    plan = CampaignPlan.model_validate(plan_dict)

    # Extract trades from approved candidates with metadata
    from trading_platform.ai.feature_engineering.trade_extractor import (
        extract_trades_from_brief,
    )

    dfs = []
    for run_id in approved_run_ids:
        brief_path = candidates_dir / run_id / "brief.json"
        if not brief_path.exists():
            continue

        with open(brief_path) as f:
            brief = json.load(f)

        # Extract trades
        df_trades = extract_trades_from_brief(brief)
        if df_trades.empty:
            continue

        # Add metadata columns from campaign plan
        df_trades["campaign_id"] = campaign_id
        df_trades["run_id"] = run_id
        df_trades["strategy_archetype"] = plan.strategy_archetype
        df_trades["execution_timeframe"] = plan.execution_timeframe

        dfs.append(df_trades)

    if not dfs:
        print("No trades extracted from approved candidates")
        return EnrichmentResult(
            campaign_id=campaign_id,
            approved_candidates=len(approved_run_ids),
            total_trades_enriched=0,
            output_path=output_path,
            enriched_at=datetime.now(timezone.utc).isoformat(),
        )

    # Concatenate all trade DataFrames
    df = pd.concat(dfs, ignore_index=True)

    # Flatten nested post_exit_analysis_simulated_holds into separate columns
    from trading_platform.ai.feature_engineering.unpacking import unpack_simulated_holds

    df = unpack_simulated_holds(df)

    # Drop redundant columns that were flattened by json_normalize
    # (data is preserved in flattened columns like context_at_exit_strategy_features_*)
    columns_to_drop = [
        col for col in ["context_at_exit", "post_exit_analysis"] if col in df.columns
    ]
    if columns_to_drop:
        df = df.drop(columns=columns_to_drop)

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
