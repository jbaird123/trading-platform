"""Campaign batch execution engine with failure artifact generation."""

import argparse
import io
import json
import platform
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from time import time
from typing import Any

import yaml

from trading_platform.ai.campaigns.models import (
    CampaignPlan,
    ExecutionResults,
    RunResult,
)
from trading_platform.cli import _run_backtest_logic


def _normalize_param_overrides(
    strategy_data: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    """Map legacy parameter aliases onto concrete strategy parameters."""

    if not overrides:
        return {}

    params = strategy_data.get("parameters") or {}
    normalized = dict(overrides)
    alias_map = {
        "fast_length": "ema_fast_length",
        "slow_length": "ema_slow_length",
    }

    for alias, canonical in alias_map.items():
        if alias in normalized and (
            canonical in params or alias in params  # detect expected schema
        ):
            normalized[canonical] = normalized.pop(alias)

    return normalized


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

            # Create RunConfig for this run
            run_config_dir = runs_dir / run.run_id
            run_config_dir.mkdir(parents=True, exist_ok=True)
            run_config_path = run_config_dir / "run_config.yaml"

            # Load base strategy and apply parameter overrides
            from pathlib import Path as PathType

            strategy_path_resolved = (
                PathType(plan.strategy_path)
                if not PathType(plan.strategy_path).is_absolute()
                else plan.strategy_path
            )
            with open(strategy_path_resolved) as f:
                strategy_data = yaml.safe_load(f)

            # Apply parameter overrides to strategy
            if run.param_overrides:
                if "parameters" not in strategy_data:
                    strategy_data["parameters"] = {}
                normalized_overrides = _normalize_param_overrides(
                    strategy_data, run.param_overrides
                )
                strategy_data["parameters"].update(normalized_overrides)

            # Build RunConfig data structure
            run_config_data: dict[str, Any] = {
                "run_id": run.run_id,
                "user_id": "campaign_runner",
                "runs_dir": str(runs_dir.parent),
                "data_request": {
                    "symbol": run.instrument,
                    "timeframe": plan.execution_timeframe,
                    "start": run.start_date,
                    "end": run.end_date,
                },
                "strategy": strategy_data,
                "execution_model": "next_bar_open",
                "post_exit_analysis": {
                    "enabled": True,
                    "horizons": [10, 20, 50],
                },
            }

            # Add contextual features if specified
            if plan.contextual_features:
                features_list: list[dict[str, Any]] = [
                    f.model_dump() for f in plan.contextual_features
                ]
                run_config_data["contextual_features"] = features_list

            # Add REM config if specified
            if plan.rem_path:
                run_config_data["rem_path"] = str(plan.rem_path)

            # Add RMM config if specified
            if plan.rmm_path:
                run_config_data["rmm_path"] = str(plan.rmm_path)

            # Save RunConfig to YAML
            with open(run_config_path, "w") as f:
                yaml.dump(run_config_data, f, default_flow_style=False)

            # Execute the run in-process to leverage shared caches
            args = argparse.Namespace(
                config=str(run_config_path),
                demo=False,
                user="campaign_runner",
                output_dir=None,
                clear_cache=False,
            )

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            exit_code = 0
            try:
                with redirect_stdout(stdout_buffer):
                    with redirect_stderr(stderr_buffer):
                        exit_code = _run_backtest_logic(args)
            except SystemExit as exc:  # pragma: no cover - defensive
                code = exc.code
                if isinstance(code, int):
                    exit_code = code
                else:
                    exit_code = 1
                    stderr_buffer.write(f"SystemExit: {code}\n")
            except Exception:  # pragma: no cover - defensive
                exit_code = 1
                stderr_buffer.write(traceback.format_exc())

            stdout_text = stdout_buffer.getvalue()
            stderr_text = stderr_buffer.getvalue()
            stdout_buffer.close()
            stderr_buffer.close()

            run_end = time()
            execution_time = run_end - run_start

            # Process results
            if exit_code == 0:
                status = "success"
                successful += 1
                log_file.write(
                    f"[{datetime.now(timezone.utc).isoformat()}] "
                    f"Completed: {run.run_id} (success)\n"
                )

                # Copy brief.json to candidates directory for validation
                import shutil

                from trading_platform.core import paths

                brief_src = (
                    paths.RUNS_DIR / "campaign_runner" / run.run_id / "brief.json"
                )
                if brief_src.exists():
                    candidates_dir = (
                        paths.PROJECT_ROOT
                        / "data"
                        / "candidates"
                        / plan.campaign_id
                        / run.run_id
                    )
                    candidates_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy(brief_src, candidates_dir / "brief.json")
                    log_file.write(
                        f"[{datetime.now(timezone.utc).isoformat()}] "
                        f"Copied brief to candidates: {candidates_dir}\n"
                    )
            else:
                status = "failed"
                failed += 1
                log_file.write(
                    f"[{datetime.now(timezone.utc).isoformat()}] "
                    f"Failed: {run.run_id} (exit code {exit_code})\n"
                )

                # Create failure report
                failure_report = {
                    "run_id": run.run_id,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                    "exit_code": exit_code,
                    "stderr": stderr_text,
                    "stdout": stdout_text,
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
                exit_code=exit_code,
                stdout=stdout_text,
                stderr=stderr_text,
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
                        f"Run {run.run_id} failed with exit code {exit_code}"
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
