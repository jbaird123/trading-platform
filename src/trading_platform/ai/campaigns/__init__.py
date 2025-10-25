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
from .review import (
    approve_candidate,
    generate_review_report,
    mark_needs_rework,
    reject_candidate,
)
from .validator import validate_campaign_candidates

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
    "validate_campaign_candidates",
    "generate_review_report",
    "approve_candidate",
    "reject_candidate",
    "mark_needs_rework",
    "enrich_campaign_dataset",
    "publish_campaign_dataset",
]
