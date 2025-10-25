"""Campaign review and approval workflow with three decision states."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import yaml


def generate_review_report(campaign_id: str, data_root: Path | None = None) -> Path:
    """Generate markdown review report for campaign candidates.

    Args:
        campaign_id: Campaign identifier
        data_root: Root directory for data

    Returns:
        Path to generated review_report.md
    """
    if data_root is None:
        data_root = Path.cwd()

    candidates_dir = data_root / "data" / "candidates" / campaign_id
    candidates_dir.mkdir(parents=True, exist_ok=True)

    index_path = candidates_dir / "index.json"

    # Load candidates
    if index_path.exists():
        with open(index_path) as f:
            candidates = json.load(f)
    else:
        candidates = []

    # Sort and select top/bottom performers
    if candidates:
        sorted_by_sharpe = sorted(
            candidates, key=lambda c: c.get("sharpe_ratio", 0), reverse=True
        )
        top_performers = sorted_by_sharpe[:10]
        bottom_performers = sorted_by_sharpe[-5:]
    else:
        top_performers = []
        bottom_performers = []

    # Build markdown report
    report_lines = [
        f"# Review Report: {campaign_id}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Total Candidates: {len(candidates)}",
        "",
        "## Top Performers",
        "",
        "| Run ID | Total PnL | Sharpe | Win Rate | Trades |",
        "|--------|-----------|--------|----------|--------|",
    ]

    if top_performers:
        for c in top_performers:
            report_lines.append(
                f"| {c['run_id']} | "
                f"{c.get('total_pnl', 0):.2f} | "
                f"{c.get('sharpe_ratio', 0):.2f} | "
                f"{c.get('win_rate', 0):.2%} | "
                f"{c.get('n_trades', 0)} |"
            )
    else:
        report_lines.append("| No candidates found | - | - | - | - |")

    report_lines.extend(
        [
            "",
            "## Bottom Performers",
            "",
            "| Run ID | Total PnL | Sharpe | Win Rate | Trades |",
            "|--------|-----------|--------|----------|--------|",
        ]
    )

    if bottom_performers:
        for c in bottom_performers:
            report_lines.append(
                f"| {c['run_id']} | "
                f"{c.get('total_pnl', 0):.2f} | "
                f"{c.get('sharpe_ratio', 0):.2f} | "
                f"{c.get('win_rate', 0):.2%} | "
                f"{c.get('n_trades', 0)} |"
            )

    report_lines.extend(
        [
            "",
            "## Review Instructions",
            "",
            "Use the following functions to record decisions:",
            "- `approve_candidate(campaign_id, run_id, notes)` - Approve",
            "- `reject_candidate(campaign_id, run_id, reason)` - Reject permanently",
            "- `mark_needs_rework(campaign_id, run_id, reason, suggestions)` - "
            "Needs modification",
        ]
    )

    # Save report
    report_path = candidates_dir / "review_report.md"
    report_path.write_text("\n".join(report_lines))

    return report_path


def approve_candidate(
    campaign_id: str,
    run_id: str,
    notes: str,
    reviewer: str = "user",
    data_root: Path | None = None,
) -> None:
    """Approve a candidate for publication.

    Args:
        campaign_id: Campaign identifier
        run_id: Run identifier
        notes: Approval notes
        reviewer: Reviewer name
        data_root: Root directory for data
    """
    _add_decision(
        campaign_id=campaign_id,
        run_id=run_id,
        status="approved",
        reviewer=reviewer,
        data_root=data_root,
        notes=notes,
    )


def reject_candidate(
    campaign_id: str,
    run_id: str,
    reason: str,
    reviewer: str = "user",
    data_root: Path | None = None,
) -> None:
    """Reject a candidate.

    Args:
        campaign_id: Campaign identifier
        run_id: Run identifier
        reason: Rejection reason
        reviewer: Reviewer name
        data_root: Root directory for data
    """
    _add_decision(
        campaign_id=campaign_id,
        run_id=run_id,
        status="rejected",
        reviewer=reviewer,
        data_root=data_root,
        reason=reason,
    )


def mark_needs_rework(
    campaign_id: str,
    run_id: str,
    reason: str,
    suggestions: str,
    reviewer: str = "user",
    data_root: Path | None = None,
) -> None:
    """Mark a candidate as needing rework.

    Args:
        campaign_id: Campaign identifier
        run_id: Run identifier
        reason: Why rework is needed
        suggestions: Suggestions for improvement
        reviewer: Reviewer name
        data_root: Root directory for data
    """
    _add_decision(
        campaign_id=campaign_id,
        run_id=run_id,
        status="needs-rework",
        reviewer=reviewer,
        data_root=data_root,
        reason=reason,
        suggestions=suggestions,
    )


def get_approved_candidates(
    campaign_id: str, data_root: Path | None = None
) -> List[str]:
    """Get list of approved candidate run_ids.

    Args:
        campaign_id: Campaign identifier
        data_root: Root directory for data

    Returns:
        List of approved run_ids
    """
    return _get_candidates_by_status(campaign_id, "approved", data_root)


def get_needs_rework_candidates(
    campaign_id: str, data_root: Path | None = None
) -> List[str]:
    """Get list of needs-rework candidate run_ids.

    Args:
        campaign_id: Campaign identifier
        data_root: Root directory for data

    Returns:
        List of needs-rework run_ids
    """
    return _get_candidates_by_status(campaign_id, "needs-rework", data_root)


def _add_decision(
    campaign_id: str,
    run_id: str,
    status: str,
    reviewer: str,
    data_root: Path | None,
    **kwargs,
) -> None:
    """Add a decision to campaign decision.yaml."""
    if data_root is None:
        data_root = Path.cwd()

    candidates_dir = data_root / "data" / "candidates" / campaign_id
    candidates_dir.mkdir(parents=True, exist_ok=True)

    decision_path = candidates_dir / "decision.yaml"

    # Load existing or create new
    if decision_path.exists():
        with open(decision_path) as f:
            decision_data = yaml.safe_load(f)
    else:
        decision_data = {
            "campaign_id": campaign_id,
            "reviewed_by": reviewer,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "decisions": [],
        }

    # Add new decision
    new_decision = {"run_id": run_id, "status": status, **kwargs}
    decision_data["decisions"].append(new_decision)

    # Save
    with open(decision_path, "w") as f:
        yaml.dump(decision_data, f, default_flow_style=False)


def _get_candidates_by_status(
    campaign_id: str, status: str, data_root: Path | None
) -> List[str]:
    """Get candidates filtered by status."""
    if data_root is None:
        data_root = Path.cwd()

    decision_path = data_root / "data" / "candidates" / campaign_id / "decision.yaml"

    if not decision_path.exists():
        return []

    with open(decision_path) as f:
        decision_data = yaml.safe_load(f)

    decisions = decision_data.get("decisions", [])
    return [d["run_id"] for d in decisions if d.get("status") == status]
