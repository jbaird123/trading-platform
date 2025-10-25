"""Campaign runner for automated backtest orchestration."""

from .enrichment import enrich_campaign_dataset
from .models import (
    ArtifactSummary,
    CampaignConfig,
    CampaignPlan,
    CandidateMetadata,
    CandidateValidation,
    CheckResult,
    EnrichmentResult,
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
    "EnrichmentResult",
    "enrich_campaign_dataset",
]
