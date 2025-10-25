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


class SingleRun(BaseModel):
    """A single backtest run within a campaign."""

    model_config = {"extra": "forbid"}

    run_id: str = Field(..., description="Unique run identifier")
    instrument: str = Field(..., description="Trading instrument symbol")
    start_date: str = Field(..., description="Backtest start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Backtest end date (YYYY-MM-DD)")
    param_overrides: Optional[Dict[str, Any]] = Field(
        default=None, description="Strategy parameter overrides"
    )
    output_path: Path = Field(..., description="Output directory for this run")


class CampaignPlan(BaseModel):
    """Complete campaign execution plan with provenance."""

    model_config = {"extra": "forbid"}

    campaign_id: str = Field(..., description="Unique campaign identifier")
    strategy_path: Path = Field(..., description="Path to strategy YAML file")
    execution_timeframe: str = Field(
        ..., description="Base execution timeframe (e.g., 15m, 1h)"
    )
    strategy_archetype: str = Field(
        ..., description="Strategy type for model selection"
    )
    runs: List[SingleRun] = Field(..., description="List of individual runs")
    contextual_features: List[FeatureConfig] = Field(
        default_factory=list, description="Multi-timeframe features"
    )
    provenance: Provenance = Field(..., description="Provenance metadata")
    rem_path: Optional[Path] = Field(default=None, description="Path to REM config")
    rmm_path: Optional[Path] = Field(default=None, description="Path to RMM config")


class RunResult(BaseModel):
    """Result of a single backtest run execution."""

    model_config = {"extra": "forbid"}

    run_id: str = Field(..., description="Unique run identifier")
    status: str = Field(..., description="Execution status (success/failed)")
    exit_code: int = Field(..., description="Process exit code")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    execution_time_seconds: float = Field(
        ..., description="Execution duration in seconds"
    )


class ExecutionResults(BaseModel):
    """Results of campaign batch execution."""

    model_config = {"extra": "forbid"}

    campaign_id: str = Field(..., description="Campaign identifier")
    total_runs: int = Field(..., description="Total number of runs")
    successful: int = Field(..., description="Number of successful runs")
    failed: int = Field(..., description="Number of failed runs")
    execution_log_path: Path = Field(..., description="Path to execution log")
    started_at: str = Field(..., description="ISO timestamp of start")
    completed_at: str = Field(..., description="ISO timestamp of completion")
    run_results: List["RunResult"] = Field(
        default_factory=list, description="Individual run results"
    )


class CandidateMetadata(BaseModel):
    """Metadata extracted from a candidate backtest."""

    model_config = {"extra": "forbid"}

    run_id: str = Field(..., description="Unique run identifier")
    strategy_archetype: str = Field(..., description="Strategy type")
    execution_timeframe: str = Field(..., description="Execution timeframe")
    total_pnl: float = Field(..., description="Total profit/loss")
    sharpe_ratio: Optional[float] = Field(default=None, description="Sharpe ratio")
    win_rate: float = Field(..., description="Win rate (0-1)")
    total_trades: int = Field(..., description="Total number of trades")
    max_drawdown: float = Field(..., description="Maximum drawdown")


class ArtifactSummary(BaseModel):
    """Summary of collected campaign artifacts."""

    model_config = {"extra": "forbid"}

    campaign_id: str = Field(..., description="Campaign identifier")
    total_candidates: int = Field(..., description="Number of candidates collected")
    candidates_dir: Path = Field(
        ..., description="Path to candidates directory (data/candidates/<campaign_id>)"
    )
    collected_at: str = Field(..., description="ISO timestamp of collection")
    candidates: List[CandidateMetadata] = Field(
        default_factory=list, description="List of candidate metadata"
    )


class CheckResult(BaseModel):
    """Result of a validation check."""

    model_config = {"extra": "forbid"}

    check_name: str = Field(..., description="Name of the validation check")
    status: str = Field(..., description="Check status (passed/failed/warning)")
    message: Optional[str] = Field(default=None, description="Check message or issue")


class CandidateValidation(BaseModel):
    """Validation results for a single candidate."""

    model_config = {"extra": "forbid"}

    run_id: str = Field(..., description="Candidate run identifier")
    overall_status: str = Field(
        ..., description="Overall status (passed/failed/warning)"
    )
    checks: Dict[str, CheckResult] = Field(
        default_factory=dict, description="Individual check results"
    )
    issues: List[str] = Field(
        default_factory=list, description="List of validation issues"
    )


class ValidationReport(BaseModel):
    """Campaign validation report."""

    model_config = {"extra": "forbid"}

    campaign_id: str = Field(..., description="Campaign identifier")
    validated_at: str = Field(..., description="ISO timestamp of validation")
    total_candidates: int = Field(..., description="Total candidates validated")
    passed: int = Field(..., description="Number passed")
    failed: int = Field(..., description="Number failed")
    warnings: int = Field(..., description="Number with warnings")
    results: List[CandidateValidation] = Field(
        default_factory=list, description="Individual validation results"
    )


class EnrichmentResult(BaseModel):
    """Result of campaign enrichment."""

    model_config = {"extra": "forbid"}

    campaign_id: str = Field(..., description="Campaign identifier")
    approved_candidates: int = Field(..., description="Number of approved candidates")
    total_trades_enriched: int = Field(
        ..., description="Total trades in enriched dataset"
    )
    output_path: Path = Field(..., description="Path to enriched parquet file")
    enriched_at: str = Field(..., description="ISO timestamp of enrichment")
