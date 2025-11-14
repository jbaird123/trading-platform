"""Campaign dataset publishing from enriched stage to master trade log.

Includes automated DVC tracking.
"""

import hashlib
import subprocess
from datetime import datetime, timezone

import pandas as pd

from trading_platform.core import paths

from .models import PublishResult


def publish_campaign_dataset(campaign_id: str) -> PublishResult:
    """Publish enriched dataset to master trade log with DVC tracking.

    Args:
        campaign_id: Campaign identifier

    Returns:
        PublishResult with publishing summary

    Raises:
        FileNotFoundError: If enriched dataset does not exist
    """
    # Define enriched dataset path
    enriched_path = (
        paths.PROJECT_ROOT / "data" / "enriched" / campaign_id / "rich_trades.parquet"
    )

    # Verify enriched dataset exists
    if not enriched_path.exists():
        raise FileNotFoundError(f"Enriched dataset not found: {enriched_path}")

    # Load enriched parquet
    enriched_df = pd.read_parquet(enriched_path)

    # Define master log path
    output_dir = paths.PROJECT_ROOT / "data" / "dvc" / "processed" / "training_sets"
    output_dir.mkdir(parents=True, exist_ok=True)
    master_log_path = output_dir / "master_trade_log.parquet"

    def _drop_all_na_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Remove columns that are entirely null to avoid pandas concat warning."""
        if df.empty:
            return df
        non_null_mask = df.notna().any(axis=0)
        return df.loc[:, non_null_mask]

    new_trades_count = len(enriched_df)
    cleaned_enriched = _drop_all_na_columns(enriched_df)

    # Check if master log exists and append or create
    master_log_existed = master_log_path.exists()
    if master_log_existed:
        existing_df = pd.read_parquet(master_log_path)
        cleaned_existing = _drop_all_na_columns(existing_df)
        combined_df = pd.concat([cleaned_existing, cleaned_enriched], ignore_index=True)
        combined_df.to_parquet(master_log_path)
    else:
        cleaned_enriched.to_parquet(master_log_path)

    # Calculate SHA256 checksum
    with open(master_log_path, "rb") as f:
        checksum = hashlib.sha256(f.read()).hexdigest()

    # Execute DVC tracking (use poetry run to match project workflow)
    subprocess.run(["poetry", "run", "dvc", "add", str(master_log_path)], check=True)
    subprocess.run(["poetry", "run", "dvc", "push"], check=True)
    dvc_tracking_updated = True

    # Update curation history
    history_file = paths.PROJECT_ROOT / "docs" / "ai" / "data_curation_history.md"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()
    history_entry = (
        f"\n## {timestamp}\n\n"
        f"- **Campaign ID**: {campaign_id}\n"
        f"- **Trades Added**: {new_trades_count}\n"
        f"- **Checksum**: {checksum}\n"
        f"- **Actor**: campaign-runner\n\n"
    )

    if history_file.exists():
        with history_file.open("a", encoding="utf-8") as fh:
            fh.write(history_entry)
    else:
        with history_file.open("w", encoding="utf-8") as fh:
            fh.write("# Data Curation History\n\n")
            fh.write(history_entry)

    # Update audit log
    audit_file = paths.PROJECT_ROOT / "docs" / "ai" / "logs" / "campaign_audit.md"
    audit_file.parent.mkdir(parents=True, exist_ok=True)

    audit_entry = (
        f"\n## {timestamp}\n\n"
        f"- **Action**: Publish\n"
        f"- **Campaign ID**: {campaign_id}\n"
        f"- **Trades Published**: {new_trades_count}\n"
        f"- **Master Log Path**: {master_log_path}\n"
        f"- **Checksum**: {checksum}\n\n"
    )

    if audit_file.exists():
        with audit_file.open("a", encoding="utf-8") as fh:
            fh.write(audit_entry)
    else:
        with audit_file.open("w", encoding="utf-8") as fh:
            fh.write("# Campaign Audit Log\n\n")
            fh.write(audit_entry)

    # Create result
    result = PublishResult(
        campaign_id=campaign_id,
        total_trades_published=new_trades_count,
        output_path=master_log_path,
        sha256_checksum=checksum,
        published_at=timestamp,
        master_log_updated=master_log_existed,
        dvc_tracking_updated=dvc_tracking_updated,
    )

    return result
