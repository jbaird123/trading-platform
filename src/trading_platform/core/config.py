from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from . import paths
from .utils import gen_run_id, normalize_symbol

logger = logging.getLogger(__name__)


class FeatureConfig(BaseModel):
    """Configuration for a single technical indicator/feature."""

    name: str = Field(description="Local identifier for the feature.")
    type: str = Field(description="Indicator type (e.g., SMA, EMA, ATR).")
    params: dict[str, Any] | None = Field(
        default=None, description="Indicator-specific parameters."
    )
    source: str | None = Field(
        default=None,
        description="Input price series (e.g., open, high, low, close, hl2).",
    )
    source_ref: dict[str, Any] | None = Field(
        default=None, description="Reference another feature as input series."
    )


# Default contextual features computed on every run
DEFAULT_CONTEXTUAL_FEATURES: list[FeatureConfig] = [
    FeatureConfig(name="ctx_atr", type="ATR", params={"length": 14}),
    FeatureConfig(name="ctx_rsi", type="RSI", params={"length": 14}),
    FeatureConfig(name="ctx_ema_slow", type="EMA", params={"length": 200}),
]


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
        default=paths.RUNS_DIR,
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
    min_hold_bars: int = Field(
        default=0,
        description=(
            "Minimum number of bars a position must be held before any exit "
            "(REM or signal-based) is allowed. Prevents premature exits."
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
        True,
        description=(
            "If True, allows closing a position and opening a new one on the "
            "same bar."
        ),
    )
    daily_loss_cap: float | None = Field(
        default=None, description="Portfolio-level daily loss cap in base currency."
    )
    # Data request for fetching market data
    data_request: dict[str, Any] = Field(
        default_factory=dict,
        description="Data request specification (symbol, timeframe, start, end).",
    )
    # Component configurations
    instrument: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Instrument definition for the run "
            "(auto-populated from data_request if omitted)."
        ),
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

    contextual_features: list[FeatureConfig] | None = Field(
        default=None,
        description=(
            "A list of indicators to compute for context, even if not used "
            "in strategy rules."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def inject_default_contextual_features(cls, data: Any) -> Any:
        """Inject default contextual features if not explicitly provided."""
        if isinstance(data, dict):
            # Only inject defaults if key is missing (None)
            # If user provides [], we respect that (no defaults)
            if "contextual_features" not in data:
                data["contextual_features"] = [
                    f.model_dump() for f in DEFAULT_CONTEXTUAL_FEATURES
                ]
        return data

    @model_validator(mode="after")
    def enforce_workspace_runs_dir(self) -> RunConfig:
        """Ensure runs_dir is always inside the workspace, ignoring user config."""
        expected_runs_dir = paths.RUNS_DIR
        if self.runs_dir.resolve() != expected_runs_dir.resolve():
            logger.warning(
                "Ignoring configured `runs_dir` (%s). "
                "All runs are stored in the workspace: %s",
                self.runs_dir,
                expected_runs_dir,
            )
            self.runs_dir = expected_runs_dir
        return self

    @model_validator(mode="after")
    def validate_instrument_symbol(self) -> RunConfig:
        """Ensure instrument contains a valid, normalized symbol.

        If instrument is not provided, auto-populate it from data_request.
        """
        # Auto-populate instrument from data_request if not provided
        if not self.instrument and self.data_request:
            if "symbol" in self.data_request:
                self.instrument = {
                    "symbol": self.data_request["symbol"],
                    "timeframe": self.data_request.get("timeframe"),
                }

        if not isinstance(self.instrument, dict):
            raise ValueError(
                "instrument symbol is required "
                "(provide instrument or data_request with symbol)"
            )

        symbol = self.instrument.get("symbol", "")
        if not symbol or not symbol.strip():
            raise ValueError("instrument symbol is required")

        # Check if instrument already has all required fields (for testing)
        has_all_required = all(
            key in self.instrument
            for key in ["asset_class", "point_value", "tick_size"]
        )

        # Only enrich from instrument definitions if incomplete
        if not has_all_required:
            # Normalize the symbol and enrich with full instrument definition
            from trading_platform.data.instrument import get_instrument_definition

            normalized_symbol = normalize_symbol(symbol)
            instrument_def = get_instrument_definition(normalized_symbol)

            # Replace the minimal dict with complete instrument metadata
            # Use mode='json' to serialize datetime objects properly
            self.instrument = instrument_def.model_dump(mode="json")

        # Preserve timeframe if it was in the original dict
        if "timeframe" in self.instrument or (
            hasattr(self, "data_request")
            and self.data_request
            and "timeframe" in self.data_request
        ):
            timeframe = self.instrument.get("timeframe") or (
                self.data_request.get("timeframe") if self.data_request else None
            )
            if timeframe:
                self.instrument["timeframe"] = timeframe

        return self
