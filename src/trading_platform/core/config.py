from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .utils import gen_run_id, normalize_symbol


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
    entry_window_bars: int = Field(
        default=0,
        description=(
            "Number of bars after a signal transition during which entry attempts "
            "are allowed. 0 = only on exact transition bar (event-based), "
            ">0 = allow RMM-blocked entries to execute if unblocked within window, "
            "-1 = infinite (always try when signal is active, state-based)."
        ),
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
    # Backtester-specific parameters
    initial_cash: float = Field(
        100000.0, description="The starting cash for the portfolio."
    )
    # Position sizing (simple fixed-size for now)
    position_size: float = Field(
        1.0,
        description=(
            "Fixed trade size (units/contracts/shares) used when opening a position."
        ),
    )
    allow_flip_on_bar: bool = Field(
        False,
        description=(
            "If True, allows closing a position and opening a new one on the "
            "same bar."
        ),
    )
    daily_loss_cap: float | None = Field(
        default=None, description="Portfolio-level daily loss cap in base currency."
    )
    # Component configurations
    instrument: dict[str, Any] | None = Field(
        default=None, description="Instrument definition for the run."
    )
    pm_limits: dict[str, int] | None = Field(
        default=None, description="Position manager limits (e.g., max_open_long)."
    )
    rem_config: dict[str, Any] | None = Field(
        default=None, description="Risk & Exit Manager configuration."
    )
    # Counterfactual computation mode for skipped entries
    counterfactual_mode: Literal["fast", "exact"] = Field(
        default="fast",
        description=(
            "How to compute counterfactuals for skipped entries: "
            "'fast' uses a vectorized hold-to-end approximation; "
            "'exact' re-simulates bar-by-bar with REM."
        ),
    )

    post_exit_analysis: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Post-exit price tracking configuration for exit efficiency analysis. "
            "Example: {'enabled': True, 'horizons': [10, 20, 50]}"
        ),
    )

    @model_validator(mode="after")
    def validate_instrument_symbol(self) -> RunConfig:
        """Ensure instrument contains a valid, normalized symbol."""
        if not isinstance(self.instrument, dict):
            raise ValueError("instrument symbol is required")

        symbol = self.instrument.get("symbol", "")
        if not symbol or not symbol.strip():
            raise ValueError("instrument symbol is required")

        # Normalize the symbol and store it back
        self.instrument["symbol"] = normalize_symbol(symbol)
        return self
