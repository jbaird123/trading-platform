from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .utils import gen_run_id


class RunConfig(BaseModel):
    """
    Defines the configuration for a single run of the trading platform.
    This object will be snapshotted into the run directory for reproducibility.
    """

    user_id: str = Field(
        "default_user", description="Identifier for the user or owner of the run."
    )
    run_id: str = Field(
        default_factory=gen_run_id, description="Unique identifier for the run."
    )
    run_seed: int = Field(42, description="Seed for all random number generators.")
    runs_dir: Path = Field(
        default=Path("runs"),
        description="The root directory where run artifacts are stored.",
    )
    log_level: str = Field("INFO", description="The logging level for the run.")

    # Optional runtime snapshots for reporting/traceability
    instrument_definitions: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-symbol instrument metadata snapshot included in briefs.",
    )
    cost_model: dict[str, Any] = Field(
        default_factory=dict,
        description="Global cost model snapshot (e.g., "
        "spread/commission/slippage settings).",
    )
    fill_policy: dict[str, Any] = Field(
        default_factory=dict,
        description="Fill policy snapshot (e.g., market, next-bar, bar-mid, etc.).",
    )
    tie_break_policy: dict[str, Any] = Field(
        default_factory=dict,
        description="Exit tie-break policy snapshot (e.g., stop_then_tp).",
    )
    # Analysis scaffolds (placeholders for brief)
    monte_carlo: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Monte Carlo placeholder (e.g., seed, n_paths) to echo into brief."
        ),
    )
    walk_forward: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Walk-forward placeholder (e.g., splits metadata) to echo into brief."
        ),
    )
    parameter_search: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Parameter search config/results (e.g., grid, random, top result) "
            "to include in brief."
        ),
    )
    strategy: dict[str, Any] = Field(
        default_factory=dict, description="Strategy definition (e.g., from YAML)."
    )
    rmm_config: dict[str, Any] | None = Field(
        default=None, description="Regime Market Manager configuration, if any."
    )
    warmup_bars: int = Field(
        default=0,
        description="Number of initial bars to ignore for entries (indicator warm-up).",
    )
    # Trading window / blackout policy
    blackout_utc: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Static UTC blackout windows as [(start,end)]",
    )
    blackout_events: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Event-based blackout windows with start/end datetimes "
            "and optional metadata."
        ),
    )
