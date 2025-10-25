"""Campaign candidate validation with complete quality gates."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from scipy.stats import ks_2samp

from trading_platform.ai.campaigns.models import (
    CandidateValidation,
    CheckResult,
    ValidationReport,
)
from trading_platform.strategy.indicators_registry import INDICATORS

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

    # Load baseline for drift monitoring (if exists)
    baseline_df = None
    master_log_path = (
        data_root
        / "data"
        / "dvc"
        / "processed"
        / "training_sets"
        / "master_trade_log.parquet"
    )
    if master_log_path.exists():
        try:
            baseline_df = pd.read_parquet(master_log_path)
            logger.info(f"Loaded baseline with {len(baseline_df)} trades")
        except Exception as e:
            logger.warning(f"Failed to load baseline: {e}")

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

        # Indicator registry check
        contextual_features = brief.get("meta", {}).get("contextual_features", [])
        if contextual_features:
            unregistered = []
            for feature in contextual_features:
                indicator_type = feature.get("type")
                if indicator_type and indicator_type not in INDICATORS:
                    unregistered.append(indicator_type)

            if unregistered:
                checks["indicator_registry"] = CheckResult(
                    check_name="indicator_registry",
                    status="failed",
                    message=f"Unregistered indicators: {', '.join(unregistered)}",
                )
                issues.append(f"Unregistered indicators: {', '.join(unregistered)}")
            else:
                checks["indicator_registry"] = CheckResult(
                    check_name="indicator_registry",
                    status="passed",
                    message="All indicators registered",
                )
        else:
            checks["indicator_registry"] = CheckResult(
                check_name="indicator_registry",
                status="passed",
                message="No contextual features to validate",
            )

        # Drift monitoring check (KS-statistic)
        if baseline_df is not None and len(baseline_df) > 0 and len(trades) > 0:
            # Extract r_multiple from candidate trades
            candidate_r_multiples = [
                t.get("r_multiple", 0.0) for t in trades if "r_multiple" in t
            ]

            if candidate_r_multiples and "r_multiple" in baseline_df.columns:
                baseline_r_multiples = baseline_df["r_multiple"].dropna().values

                if len(baseline_r_multiples) > 0 and len(candidate_r_multiples) > 0:
                    ks_stat, _ = ks_2samp(baseline_r_multiples, candidate_r_multiples)

                    if ks_stat > 0.15:
                        checks["drift_monitoring"] = CheckResult(
                            check_name="drift_monitoring",
                            status="warning",
                            message=f"DRIFT DETECTED: KS={ks_stat:.3f}",
                        )
                        issues.append(f"Distribution drift detected: KS={ks_stat:.3f}")
                    else:
                        checks["drift_monitoring"] = CheckResult(
                            check_name="drift_monitoring",
                            status="passed",
                            message=f"No drift detected: KS={ks_stat:.3f}",
                        )
                else:
                    checks["drift_monitoring"] = CheckResult(
                        check_name="drift_monitoring",
                        status="passed",
                        message="Insufficient data for drift monitoring",
                    )
            else:
                checks["drift_monitoring"] = CheckResult(
                    check_name="drift_monitoring",
                    status="passed",
                    message="No r_multiple data for drift monitoring",
                )
        else:
            checks["drift_monitoring"] = CheckResult(
                check_name="drift_monitoring",
                status="passed",
                message="No baseline available for drift monitoring",
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

    # Update audit log
    audit_log_path = data_root / "docs" / "ai" / "logs" / "campaign_audit.md"
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()
    audit_entry = f"""
## {timestamp}

- **Action**: Validation
- **Campaign ID**: {campaign_id}
- **Total Candidates**: {len(results)}
- **Passed**: {passed}
- **Failed**: {failed}
- **Warnings**: {warnings}

"""

    if audit_log_path.exists():
        with open(audit_log_path, "a") as f:
            f.write(audit_entry)
    else:
        with open(audit_log_path, "w") as f:
            f.write("# Campaign Audit Log\n\n")
            f.write(audit_entry)

    logger.info(
        f"Validation complete: {passed} passed, {failed} failed, {warnings} warnings"
    )

    return report
