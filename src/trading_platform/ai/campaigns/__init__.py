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
    PublishResult,
    RunMatrixEntry,
    RunResult,
    SingleRun,
    ValidationReport,
)
from .publisher import publish_campaign_dataset

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
    "PublishResult",
    "enrich_campaign_dataset",
    "publish_campaign_dataset",
]
