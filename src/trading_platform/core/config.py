from __future__ import annotations
from pathlib import Path

from pydantic import BaseModel, Field


class RunConfig(BaseModel):
    """
    Defines the configuration for a single run of the trading platform.
    This object will be snapshotted into the run directory for reproducibility.
    """

    run_id: str = Field(..., description="The unique identifier for this run.")
    runs_dir: Path = Field(
        "runs", description="The root directory where run artifacts are stored."
    )
    log_level: str = Field("INFO", description="The logging level for the run.")