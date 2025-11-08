"""Campaign plan generation with full provenance."""

from pathlib import Path

from trading_platform.ai.campaigns.models import (
    CampaignConfig,
    CampaignPlan,
    SingleRun,
)
from trading_platform.ai.campaigns.provenance import ProvenanceCollector
from trading_platform.core import paths


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
        global_features_path = config.global_features_config_path
        if global_features_path is None:
            default_global = paths.PROJECT_ROOT / "config" / "features" / "global.yaml"
            if default_global.exists():
                global_features_path = default_global

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
            global_features_config_path=global_features_path,
        )

        return plan


def generate_campaign_plan(
    config: CampaignConfig, output_dir: Path | None = None
) -> CampaignPlan:
    """Generate campaign plan and save to output directory.

    Args:
        config: Campaign configuration
        output_dir: Directory to save plan.json. If None, plan is not saved.

    Returns:
        Generated campaign plan with provenance
    """
    planner = CampaignPlanner()
    plan = planner.generate_plan(config)

    if output_dir:
        import json

        output_dir.mkdir(parents=True, exist_ok=True)
        plan_path = output_dir / "plan.json"

        with open(plan_path, "w") as f:
            json.dump(plan.model_dump(mode="json"), f, indent=2)

    return plan
