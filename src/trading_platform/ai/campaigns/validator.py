"""Campaign candidate validation with complete quality gates."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from trading_platform.ai.campaigns.models import (
    CandidateValidation,
    CheckResult,
    ValidationReport,
)

logger = logging.getLogger(__name__)


def validate_campaign_candidates(
    campaign_id: str, data_root: Path | None = None
) -> ValidationReport:
    """Validate all candidates in a campaign.

    Args:
        campaign_id: Campaign identifier
        data_root: Root directory for data (defaults to current directory)

    Returns:
        ValidationReport with validation results for all candidates
    """
    if data_root is None:
        data_root = Path.cwd()

    candidates_dir = data_root / "data" / "candidates" / campaign_id

    if not candidates_dir.exists():
        logger.warning(f"Candidates directory not found: {candidates_dir}")
        return ValidationReport(
            campaign_id=campaign_id,
            validated_at=datetime.now(timezone.utc).isoformat(),
            total_candidates=0,
            passed=0,
            failed=0,
            warnings=0,
            results=[],
        )

    # Find all candidate directories
    candidate_dirs = [d for d in sorted(candidates_dir.iterdir()) if d.is_dir()]

    if not candidate_dirs:
        logger.info(f"No candidates found in {candidates_dir}")
        return ValidationReport(
            campaign_id=campaign_id,
            validated_at=datetime.now(timezone.utc).isoformat(),
            total_candidates=0,
            passed=0,
            failed=0,
            warnings=0,
            results=[],
        )

    # Initialize counters
    passed = 0
    failed = 0
    warnings = 0
    results = []

    # Validate each candidate
    for candidate_dir in candidate_dirs:
        brief_path = candidate_dir / "brief.json"
        if not brief_path.exists():
            logger.warning(f"brief.json not found in {candidate_dir.name}")
            continue

        # Load brief
        with open(brief_path) as f:
            brief = json.load(f)

        run_id = candidate_dir.name
        checks = {}
        issues = []

        # Schema validation
        required_fields = ["meta", "trades", "backtest_metrics"]
        missing_fields = [f for f in required_fields if f not in brief]
        if missing_fields:
            checks["schema_validation"] = CheckResult(
                check_name="schema_validation",
                status="failed",
                message=f"Missing required fields: {', '.join(missing_fields)}",
            )
            issues.append(f"Missing fields: {', '.join(missing_fields)}")
        else:
            checks["schema_validation"] = CheckResult(
                check_name="schema_validation",
                status="passed",
                message="All required fields present",
            )

        # Data quality check
        data_quality = brief.get("data_quality", {})
        if data_quality.get("has_nans", False):
            checks["data_quality"] = CheckResult(
                check_name="data_quality",
                status="warning",
                message="Data contains NaN values",
            )
            issues.append("Data contains NaN values")
        else:
            checks["data_quality"] = CheckResult(
                check_name="data_quality",
                status="passed",
                message="No data quality issues",
            )

        # Minimum trades check
        trades = brief.get("trades", [])
        if len(trades) < 5:
            checks["min_trades"] = CheckResult(
                check_name="min_trades",
                status="failed",
                message=f"Insufficient trades: {len(trades)} < 5",
            )
            issues.append(f"Insufficient trades: {len(trades)}")
        else:
            checks["min_trades"] = CheckResult(
                check_name="min_trades",
                status="passed",
                message=f"Sufficient trades: {len(trades)}",
            )

        # Duplicate trade ID check
        trade_ids = [t.get("trade_id") for t in trades if "trade_id" in t]
        if len(trade_ids) != len(set(trade_ids)):
            duplicates = [tid for tid in set(trade_ids) if trade_ids.count(tid) > 1]
            checks["duplicate_detection"] = CheckResult(
                check_name="duplicate_detection",
                status="failed",
                message=f"Duplicate trade IDs found: {duplicates}",
            )
            issues.append(f"Duplicate trade IDs: {duplicates}")
        else:
            checks["duplicate_detection"] = CheckResult(
                check_name="duplicate_detection",
                status="passed",
                message="No duplicate trade IDs",
            )

        # Max drawdown check
        backtest_metrics = brief.get("backtest_metrics", {})
        max_drawdown = backtest_metrics.get("max_drawdown", 0.0)
        if max_drawdown < -0.5:  # More than 50% drawdown
            checks["max_drawdown"] = CheckResult(
                check_name="max_drawdown",
                status="failed",
                message=f"Excessive drawdown: {max_drawdown:.1%}",
            )
            issues.append(f"Excessive drawdown: {max_drawdown:.1%}")
        else:
            checks["max_drawdown"] = CheckResult(
                check_name="max_drawdown",
                status="passed",
                message=f"Drawdown acceptable: {max_drawdown:.1%}",
            )

        # Determine overall status
        failed_checks = [c for c in checks.values() if c.status == "failed"]
        warning_checks = [c for c in checks.values() if c.status == "warning"]

        if failed_checks:
            overall_status = "failed"
            failed += 1
        elif warning_checks:
            overall_status = "warning"
            warnings += 1
        else:
            overall_status = "passed"
            passed += 1

        # Create validation result
        validation = CandidateValidation(
            run_id=run_id,
            overall_status=overall_status,
            checks=checks,
            issues=issues,
        )
        results.append(validation)

    # Create report
    report = ValidationReport(
        campaign_id=campaign_id,
        validated_at=datetime.now(timezone.utc).isoformat(),
        total_candidates=len(results),
        passed=passed,
        failed=failed,
        warnings=warnings,
        results=results,
    )

    # Save report
    report_path = candidates_dir / "validation_report.json"
    with open(report_path, "w") as f:
        json.dump(report.model_dump(), f, indent=2)

    logger.info(
        f"Validation complete: {passed} passed, {failed} failed, {warnings} warnings"
    )

    return report
