"""Campaign runner for automated backtest orchestration."""

from .collector import collect_campaign_artifacts
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
from .planner import generate_campaign_plan
from .publisher import publish_campaign_dataset
from .review import (
    approve_candidate,
    generate_review_report,
    mark_needs_rework,
    reject_candidate,
)
from .runner import execute_campaign_runs
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
    "generate_campaign_plan",
    "execute_campaign_runs",
    "collect_campaign_artifacts",
    "validate_campaign_candidates",
    "generate_review_report",
    "approve_candidate",
    "reject_candidate",
    "mark_needs_rework",
    "enrich_campaign_dataset",
    "publish_campaign_dataset",
]
