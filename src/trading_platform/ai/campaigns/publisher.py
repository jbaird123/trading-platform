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

    # Check if master log exists and append or create
    master_log_existed = master_log_path.exists()
    if master_log_existed:
        existing_df = pd.read_parquet(master_log_path)
        combined_df = pd.concat([existing_df, enriched_df], ignore_index=True)
        combined_df.to_parquet(master_log_path)
    else:
        enriched_df.to_parquet(master_log_path)

    # Calculate SHA256 checksum
    with open(master_log_path, "rb") as f:
        checksum = hashlib.sha256(f.read()).hexdigest()

    # Execute DVC tracking
    subprocess.run(["dvc", "add", str(master_log_path)], check=True)
    subprocess.run(["dvc", "push"], check=True)
    dvc_tracking_updated = True

    # Update curation history
    history_file = paths.PROJECT_ROOT / "docs" / "ai" / "data_curation_history.md"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()
    history_entry = f"""
## {timestamp}

- **Campaign ID**: {campaign_id}
- **Trades Added**: {len(enriched_df)}
- **Checksum**: {checksum}
- **Actor**: campaign-runner

"""

    if history_file.exists():
        with open(history_file, "a") as f:
            f.write(history_entry)
    else:
        with open(history_file, "w") as f:
            f.write("# Data Curation History\n\n")
            f.write(history_entry)

    # Update audit log
    audit_file = paths.PROJECT_ROOT / "docs" / "ai" / "logs" / "campaign_audit.md"
    audit_file.parent.mkdir(parents=True, exist_ok=True)

    audit_entry = f"""
## {timestamp}

- **Action**: Publish
- **Campaign ID**: {campaign_id}
- **Trades Published**: {len(enriched_df)}
- **Master Log Path**: {master_log_path}
- **Checksum**: {checksum}

"""

    if audit_file.exists():
        with open(audit_file, "a") as f:
            f.write(audit_entry)
    else:
        with open(audit_file, "w") as f:
            f.write("# Campaign Audit Log\n\n")
            f.write(audit_entry)

    # Create result
    result = PublishResult(
        campaign_id=campaign_id,
        total_trades_published=len(enriched_df),
        output_path=master_log_path,
        sha256_checksum=checksum,
        published_at=timestamp,
        master_log_updated=master_log_existed,
        dvc_tracking_updated=dvc_tracking_updated,
    )

    return result
