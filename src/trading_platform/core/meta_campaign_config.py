from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class StrategyProfileParamSet:
    """A single parameter set in a strategy profile's param_grid."""

    strategy_params: dict[str, Any]
    rem_params: dict[str, Any] | None = None


@dataclass
class StrategyProfile:
    """
    A strategy profile defines a combination of strategy and risk management
    configuration with a grid of parameters to test.
    """

    name: str
    strategy_path: str
    rem_path: str | None
    archetype: str
    param_grid: list[StrategyProfileParamSet]

    def has_risk(self) -> bool:
        """Return True if this profile includes risk/exit management parameters."""
        return self.rem_path is not None


@dataclass
class RunGrid:
    """Define date ranges, instruments, and timeframes for campaigns."""

    date_ranges: list[dict[str, str]]
    instruments: list[str]
    execution_timeframes: list[str]

    def validate(self) -> None:
        """
        Validate the run grid configuration.

        Raises:
            ValueError: If validation fails
        """
        # Validate date_ranges have required keys
        for dr in self.date_ranges:
            if "start" not in dr or "end" not in dr:
                raise ValueError(f"Date range missing 'start' or 'end' key: {dr}")

        # Validate execution_timeframes are in valid set
        valid_timeframes = {"1min", "5min", "15min", "1H", "4H", "1D"}
        for tf in self.execution_timeframes:
            if tf not in valid_timeframes:
                raise ValueError(
                    f"Invalid execution_timeframe: {tf}. "
                    f"Must be one of {valid_timeframes}"
                )


@dataclass
class MetaCampaignConfig:
    """
    A meta-campaign configuration that defines the full grid of campaigns to generate.
    """

    meta_campaign_id: str
    description: str
    run_grid: RunGrid
    strategy_profiles: list[StrategyProfile]

    @classmethod
    def from_yaml(cls, path: Path) -> MetaCampaignConfig:
        """
        Load a MetaCampaignConfig from a YAML file.

        Args:
            path: Path to the meta-campaign YAML file

        Returns:
            MetaCampaignConfig instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the YAML is invalid or missing required fields
        """
        if not path.exists():
            raise FileNotFoundError(f"Meta-campaign config not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML format in {path}")

        # Extract required fields
        try:
            meta_campaign_id = data["meta_campaign_id"]
            description = data["description"]
            run_grid_data = data["run_grid"]
            strategy_profiles_data = data["strategy_profiles"]
        except KeyError as e:
            raise ValueError(f"Missing required field in meta-campaign config: {e}")

        # Parse RunGrid
        run_grid = RunGrid(
            date_ranges=run_grid_data["date_ranges"],
            instruments=run_grid_data["instruments"],
            execution_timeframes=run_grid_data["execution_timeframes"],
        )

        # Validate the run grid
        run_grid.validate()

        # Parse StrategyProfiles
        strategy_profiles = []
        for profile_data in strategy_profiles_data:
            param_grid = []
            for param_set in profile_data["param_grid"]:
                param_grid.append(
                    StrategyProfileParamSet(
                        strategy_params=param_set.get("strategy_params", {}),
                        rem_params=param_set.get("rem_params"),
                    )
                )

            strategy_profiles.append(
                StrategyProfile(
                    name=profile_data["name"],
                    strategy_path=profile_data["strategy_path"],
                    rem_path=profile_data.get("rem_path"),
                    archetype=profile_data["archetype"],
                    param_grid=param_grid,
                )
            )

        return cls(
            meta_campaign_id=meta_campaign_id,
            description=description,
            run_grid=run_grid,
            strategy_profiles=strategy_profiles,
        )
