"""Campaign configuration models for automated backtest orchestration."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from trading_platform.core.config import FeatureConfig


class RunMatrixEntry(BaseModel):
    """A single entry in the campaign run matrix."""

    model_config = {"extra": "forbid"}

    instrument: str = Field(..., description="Trading instrument symbol")
    start_date: str = Field(..., description="Backtest start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Backtest end date (YYYY-MM-DD)")
    param_overrides: Optional[Dict[str, Any]] = Field(
        default=None, description="Strategy parameter overrides"
    )


class Provenance(BaseModel):
    """Provenance metadata for reproducibility."""

    model_config = {"extra": "forbid"}

    git_commit: str = Field(..., description="Git commit hash")
    poetry_lock_sha256: str = Field(..., description="SHA256 of poetry.lock")
    python_version: str = Field(..., description="Python interpreter version")
    platform: str = Field(..., description="OS platform")
    dvc_version: str = Field(..., description="DVC version")
    data_snapshot_id: str = Field(..., description="DVC data version/snapshot hash")
    captured_at: str = Field(..., description="ISO timestamp of provenance capture")


class CampaignConfig(BaseModel):
    """Campaign configuration for automated backtest execution."""

    model_config = {"extra": "forbid"}

    campaign_id: str = Field(..., description="Unique campaign identifier")
    strategy_path: Path = Field(..., description="Path to strategy YAML file")
    execution_timeframe: str = Field(
        ..., description="Base execution timeframe (e.g., 15m, 1h)"
    )
    strategy_archetype: str = Field(
        ...,
        description=(
            "Strategy type (e.g., trend_following, mean_reversion) - "
            "REQUIRED for model selection"
        ),
    )
    run_matrix: List[RunMatrixEntry] = Field(
        ..., description="Matrix of runs to execute"
    )
    contextual_features: List[FeatureConfig] = Field(
        default_factory=list, description="Multi-timeframe features"
    )
    rem_path: Optional[Path] = Field(default=None, description="Path to REM config")
    rmm_path: Optional[Path] = Field(default=None, description="Path to RMM config")
    description: Optional[str] = Field(default=None, description="Campaign description")
