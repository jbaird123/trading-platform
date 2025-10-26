from __future__ import annotations

import itertools
import subprocess
from pathlib import Path
from typing import Any

import yaml
from trading_platform.core.meta_campaign_config import MetaCampaignConfig


def calculate_cartesian_product(config: MetaCampaignConfig) -> list[dict[str, Any]]:
    """
    Generate the cartesian product of all campaign parameters.

    Args:
        config: MetaCampaignConfig instance

    Returns:
        List of campaign configuration dictionaries, one for each combination
    """
    campaigns = []

    for profile in config.strategy_profiles:
        # Use itertools.product for cartesian product
        for date_range, instrument, timeframe, param_set in itertools.product(
            config.run_grid.date_ranges,
            config.run_grid.instruments,
            config.run_grid.execution_timeframes,
            profile.param_grid,
        ):
            campaign = {
                "meta_campaign_id": config.meta_campaign_id,
                "profile_name": profile.name,
                "date_range": date_range,
                "instrument": instrument,
                "execution_timeframe": timeframe,
                "strategy_path": profile.strategy_path,
                "rem_path": profile.rem_path,
                "archetype": profile.archetype,
                "strategy_params": param_set.strategy_params,
                "rem_params": param_set.rem_params,
            }
            campaigns.append(campaign)

    return campaigns


def generate_campaign_filename(
    meta_campaign_id: str,
    profile_name: str,
    instrument: str,
    timeframe: str,
    param_index: int,
) -> str:
    """
    Generate a filename for a campaign configuration.

    Args:
        meta_campaign_id: ID of the meta-campaign
        profile_name: Name of the strategy profile
        instrument: Instrument symbol
        timeframe: Execution timeframe
        param_index: Index of the parameter set

    Returns:
        Filename string with .yaml extension
    """
    filename = (
        f"{meta_campaign_id}_{profile_name}_{instrument}_"
        f"{timeframe}_{param_index:02d}.yaml"
    )
    return filename


def _get_git_commit() -> str | None:
    """Return the short git commit hash, or None if git fails."""
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .decode("ascii")
            .strip()
        )
    except Exception:
        return None


def campaign_config_to_yaml_dict(campaign: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a campaign configuration to a YAML-compatible dictionary.

    Args:
        campaign: Campaign configuration dict from calculate_cartesian_product

    Returns:
        Dictionary ready to be written as YAML campaign config
    """
    # Load strategy config
    strategy_path = Path(campaign["strategy_path"])
    if strategy_path.exists():
        with open(strategy_path) as f:
            strategy_config = yaml.safe_load(f) or {}
    else:
        strategy_config = {}

    # Merge strategy_params into strategy config
    strategy_config.update(campaign["strategy_params"])

    # Load REM config if present
    rem_config = None
    if campaign["rem_path"] is not None:
        rem_path = Path(campaign["rem_path"])
        if rem_path.exists():
            with open(rem_path) as f:
                rem_config = yaml.safe_load(f) or {}
            # Merge rem_params into rem config
            if campaign["rem_params"] is not None:
                rem_config.update(campaign["rem_params"])

    # Build the final YAML dict
    yaml_dict: dict[str, Any] = {
        "start_date": campaign["date_range"]["start"],
        "end_date": campaign["date_range"]["end"],
        "instrument": campaign["instrument"],
        "execution_timeframe": campaign["execution_timeframe"],
        "strategy": strategy_config,
        "archetype": campaign["archetype"],
        "metadata": {
            "meta_campaign_id": campaign["meta_campaign_id"],
            "profile_name": campaign["profile_name"],
            "git_commit": _get_git_commit(),
        },
    }

    # Only include rem if it exists
    if rem_config is not None:
        yaml_dict["rem"] = rem_config

    return yaml_dict
