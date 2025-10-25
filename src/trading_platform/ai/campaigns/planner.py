"""Campaign plan generation with full provenance."""

from pathlib import Path

from trading_platform.ai.campaigns.models import (
    CampaignConfig,
    CampaignPlan,
    SingleRun,
)
from trading_platform.ai.campaigns.provenance import ProvenanceCollector


class CampaignPlanner:
    """Generates campaign execution plans with provenance metadata."""

    def __init__(self, project_root: Path | None = None):
        """Initialize campaign planner.

        Args:
            project_root: Root directory of project. Defaults to current directory.
        """
        self.project_root = project_root or Path.cwd()
        self.provenance_collector = ProvenanceCollector(project_root=self.project_root)

    def generate_plan(self, config: CampaignConfig) -> CampaignPlan:
        """Generate campaign execution plan from configuration.

        Args:
            config: Campaign configuration.

        Returns:
            Complete campaign plan with provenance and expanded runs.
        """
        # Capture provenance
        provenance = self.provenance_collector.capture()

        # Expand run matrix into SingleRun objects
        runs = []
        for idx, matrix_entry in enumerate(config.run_matrix):
            run_id = f"{config.campaign_id}_{idx:04d}_{matrix_entry.instrument}"
            output_path = Path(config.campaign_id) / run_id

            single_run = SingleRun(
                run_id=run_id,
                instrument=matrix_entry.instrument,
                start_date=matrix_entry.start_date,
                end_date=matrix_entry.end_date,
                param_overrides=matrix_entry.param_overrides,
                output_path=output_path,
            )
            runs.append(single_run)

        # Create campaign plan
        plan = CampaignPlan(
            campaign_id=config.campaign_id,
            strategy_path=config.strategy_path,
            execution_timeframe=config.execution_timeframe,
            strategy_archetype=config.strategy_archetype,
            runs=runs,
            contextual_features=config.contextual_features,
            provenance=provenance,
            rem_path=config.rem_path,
            rmm_path=config.rmm_path,
        )

        return plan
