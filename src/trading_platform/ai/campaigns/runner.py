"""Campaign batch execution engine with failure artifact generation."""

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import time

import yaml

from trading_platform.ai.campaigns.models import (
    CampaignPlan,
    ExecutionResults,
    RunResult,
)


def execute_campaign_runs(
    plan: CampaignPlan,
    runs_dir: Path,
    campaign_dir: Path,
    fail_fast: bool = True,
    continue_on_error: bool = False,
) -> ExecutionResults:
    """Execute all runs in a campaign plan.

    Args:
        plan: Campaign execution plan
        runs_dir: Base directory for run outputs
        campaign_dir: Campaign-specific directory for logs and metadata
        fail_fast: Stop on first failure (default True)
        continue_on_error: Continue even if runs fail (overrides fail_fast)

    Returns:
        ExecutionResults with summary and individual run results

    Raises:
        RuntimeError: If a run fails and continue_on_error=False and fail_fast=False
    """
    # Create campaign directory structure
    campaign_dir.mkdir(parents=True, exist_ok=True)
    failures_dir = campaign_dir / "failures"
    failures_dir.mkdir(exist_ok=True)

    # Create execution log
    log_path = campaign_dir / "execution.log"
    log_file = open(log_path, "w")

    # Initialize tracking
    successful = 0
    failed = 0
    run_results = []
    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time()

    try:
        for run in plan.runs:
            run_start = time()

            # Log run start
            log_file.write(
                f"[{datetime.now(timezone.utc).isoformat()}] "
                f"Starting run: {run.run_id}\n"
            )
            log_file.flush()

            # Build command to execute backtest
            # For now, we'll use a simple approach - in production this would
            # invoke the actual backtest execution
            cmd = [
                "poetry",
                "run",
                "tp",
                "run-backtest",
                "--run-id",
                run.run_id,
                "--instrument",
                run.instrument,
                "--start-date",
                run.start_date,
                "--end-date",
                run.end_date,
                "--campaign-id",
                plan.campaign_id,
            ]

            # Execute the run
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            run_end = time()
            execution_time = run_end - run_start

            # Process results
            if result.returncode == 0:
                status = "success"
                successful += 1
                log_file.write(
                    f"[{datetime.now(timezone.utc).isoformat()}] "
                    f"Completed: {run.run_id} (success)\n"
                )
            else:
                status = "failed"
                failed += 1
                log_file.write(
                    f"[{datetime.now(timezone.utc).isoformat()}] "
                    f"Failed: {run.run_id} (exit code {result.returncode})\n"
                )

                # Create failure report
                failure_report = {
                    "run_id": run.run_id,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                    "exit_code": result.returncode,
                    "stderr": result.stderr,
                    "stdout": result.stdout,
                    "config_snapshot": {
                        "instrument": run.instrument,
                        "start_date": run.start_date,
                        "end_date": run.end_date,
                        "param_overrides": run.param_overrides,
                        "strategy_path": str(plan.strategy_path),
                        "execution_timeframe": plan.execution_timeframe,
                        "strategy_archetype": plan.strategy_archetype,
                    },
                    "environment": {
                        "python_version": (
                            f"{sys.version_info[0]}."
                            f"{sys.version_info[1]}."
                            f"{sys.version_info[2]}"
                        ),
                        "platform": platform.platform(),
                        "git_commit": plan.provenance.git_commit,
                    },
                }

                # Save failure report
                failure_path = failures_dir / f"{run.run_id}_failure_report.json"
                with open(failure_path, "w") as f:
                    json.dump(failure_report, f, indent=2)

            log_file.flush()

            # Create run result
            run_result = RunResult(
                run_id=run.run_id,
                status=status,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time_seconds=execution_time,
            )
            run_results.append(run_result)

            # Handle failures
            if status == "failed":
                if fail_fast and not continue_on_error:
                    log_file.write(
                        f"[{datetime.now(timezone.utc).isoformat()}] "
                        "Stopping execution (fail_fast=True)\n"
                    )
                    break
                elif not continue_on_error and not fail_fast:
                    log_file.close()
                    raise RuntimeError(
                        f"Run {run.run_id} failed with exit code "
                        f"{result.returncode}"
                    )

    finally:
        log_file.close()

    # Record completion
    completed_at = datetime.now(timezone.utc).isoformat()
    total_runtime = time() - start_time

    # Create completion summary
    completion_summary = {
        "campaign_id": plan.campaign_id,
        "total_runs": len(plan.runs),
        "successful": successful,
        "failed": failed,
        "total_runtime_seconds": total_runtime,
        "completed_at": completed_at,
    }

    summary_path = campaign_dir / "campaign_complete.yaml"
    with open(summary_path, "w") as f:
        yaml.dump(completion_summary, f, default_flow_style=False)

    # Create and return results
    return ExecutionResults(
        campaign_id=plan.campaign_id,
        total_runs=len(plan.runs),
        successful=successful,
        failed=failed,
        execution_log_path=log_path,
        started_at=started_at,
        completed_at=completed_at,
        run_results=run_results,
    )
