from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel, Field
from .utils import gen_run_id


class RunConfig(BaseModel):
    """
    Defines the configuration for a single run of the trading platform.
    This object will be snapshotted into the run directory for reproducibility.
    """

    user_id: str = Field("default_user", description="Identifier for the user or owner of the run.")
    run_id: str = Field(default_factory=gen_run_id, description="Unique identifier for the run.")
    runs_dir: Path = Field(default=Path("runs"), description="The root directory where run artifacts are stored.")
    log_level: str = Field("INFO", description="The logging level for the run.")