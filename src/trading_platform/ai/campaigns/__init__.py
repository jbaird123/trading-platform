"""Campaign runner for automated backtest orchestration."""

from .models import (
    ArtifactSummary,
    CampaignConfig,
    CampaignPlan,
    CandidateMetadata,
    CandidateValidation,
    CheckResult,
    ExecutionResults,
    Provenance,
    RunMatrixEntry,
    RunResult,
    SingleRun,
    ValidationReport,
)

__all__ = [
    "CampaignConfig",
    "RunMatrixEntry",
    "Provenance",
    "SingleRun",
    "CampaignPlan",
    "RunResult",
    "ExecutionResults",
    "CandidateMetadata",
    "ArtifactSummary",
    "CheckResult",
    "CandidateValidation",
    "ValidationReport",
]
