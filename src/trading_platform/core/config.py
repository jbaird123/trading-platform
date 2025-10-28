from __future__ import annotations

import logging
import re
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from . import paths
from .utils import gen_run_id, normalize_symbol

logger = logging.getLogger(__name__)


class PriceSource(str, Enum):
    """Valid price source fields for technical indicators.

    STRICT VALIDATION: Only these source fields are supported.
    """

    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    HL2 = "hl2"
    OHLC4 = "ohlc4"
    VOLUME = "volume"


class FeatureConfig(BaseModel):
    """Configuration for a single technical indicator/feature.

    STRICT VALIDATION:
    - type must exist in the unified indicator registry
    - source must be from PriceSource enum if provided
    """

    model_config = {"extra": "forbid"}

    name: str = Field(description="Local identifier for the feature.")
    type: str = Field(
        description=(
            "Indicator type registered in the unified indicator registry (e.g., 'EMA')."
        )
    )
    params: dict[str, Any] | None = Field(
        default=None, description="Indicator-specific parameters."
    )
    source: PriceSource | None = Field(
        default=None,
        description="Input price series from PriceSource enum.",
    )
    source_ref: dict[str, Any] | None = Field(
        default=None, description="Reference another feature as input series."
    )
    timeframe: str | None = Field(
        default=None,
        description=(
            "Optional pandas offset alias for higher-timeframe resampling. "
            "When provided, the feature will be computed on resampled data."
        ),
    )

    @field_validator("type")
    @classmethod
    def validate_indicator_type(cls, value: str) -> str:
        from trading_platform.strategy.indicators_registry import INDICATORS

        if value not in INDICATORS:
            allowed = ", ".join(sorted(INDICATORS))
            raise ValueError(
                f"Unknown indicator type '{value}'. Must be one of: {allowed}."
            )
        return value

    @field_validator("name")
    @classmethod
    def validate_name_based_on_context(cls, v: str, info: ValidationInfo) -> str:
        """Validate feature name based on context (global vs strategy)."""
        context = info.context or {}
        is_global = context.get("is_global", False)

        if is_global:
            # Global features MUST have timeframe prefix
            pattern = r"^(m1|m5|m15|h1|h4|d1)_[a-z0-9_]+$"
            if not re.match(pattern, v):
                raise ValueError(
                    f"Global features must have timeframe prefix "
                    f"(m1_, m5_, m15_, h1_, h4_, d1_). Got: {v}"
                )

        return v


class GlobalFeatureSetConfig(BaseModel):
    """Configuration for the global feature set loaded from global.yaml.

    All features in this config MUST have timeframe prefixes.
    This is enforced via the FeatureConfig validator when loaded with
    is_global context.
    """

    model_config = {"extra": "forbid"}

    features: list[FeatureConfig] = Field(
        default_factory=list,
        description="List of global features with timeframe prefixes",
    )

    @model_validator(mode="after")
    def validate_all_features_have_prefix(self) -> GlobalFeatureSetConfig:
        """Ensure all features have timeframe prefix by validating
        with is_global context.
        """
        # Re-validate each feature with is_global context
        for feature in self.features:
            # Trigger re-validation with context
            FeatureConfig.model_validate(
                feature.model_dump(), context={"is_global": True}
            )
        return self


class RunConfig(BaseModel):
    """
    Defines the configuration for a single run of the trading platform.
    This object will be snapshotted into the run directory for reproducibility.
    """

    model_config = {"extra": "forbid"}

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

    @model_validator(mode="before")
    @classmethod
    def _reject_warmup_bars(cls, data: Any) -> Any:
        if isinstance(data, dict) and "warmup_bars" in data:
            raise ValueError(
                "warmup_bars has been removed; ensure market data already "
                "contains enough history for indicator warmup."
            )
        return data
    execution_model: Literal["current_bar_close", "next_bar_open"] = Field(
        "current_bar_close",
        description=(
            "Execution model for entries and exits. "
            "'current_bar_close' executes trades immediately at the "
            "signal bar's close price (unrealistic, but useful for rapid "
            "prototyping). 'next_bar_open' defers execution to the next "
            "bar's open price (realistic, industry standard, matches "
            "TradingView behavior). For golden validation testing, always "
            "use 'next_bar_open'. See docs/architecture/execution_model.md "
            "for details."
        ),
    )
    exit_tie_break: Literal["stop_then_tp", "tp_then_stop"] = Field(
        "stop_then_tp",
        description=(
            "Exit tie-break policy when both stop-loss and take-profit are hit "
            "on the same bar. 'stop_then_tp' (default) checks stop-loss first, "
            "'tp_then_stop' checks take-profit first. This matters for intra-bar "
            "exits where both levels are breached."
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

    @model_validator(mode="after")
    def enforce_workspace_runs_dir(self) -> RunConfig:
        """Ensure runs_dir is within workspace; allow custom subdirs."""
        try:
            # Check if provided path is within the workspace directory
            self.runs_dir.resolve().relative_to(paths.WORKSPACE_DIR.resolve())
        except ValueError:
            # Path is outside workspace, log warning and reset to default
            logger.warning(
                "Ignoring configured `runs_dir` (%s) because it is "
                "outside the project workspace. "
                "Defaulting to: %s",
                self.runs_dir,
                paths.RUNS_DIR,
            )
            self.runs_dir = paths.RUNS_DIR
        return self

    @model_validator(mode="after")
    def validate_instrument_symbol(self) -> RunConfig:
        """Ensure instrument contains a valid, normalized symbol.

        If instrument is not provided, auto-populate it from data_request.
        Rejects redundant fields - instrument definition is single source of truth.
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

        # Store original timeframe before validation
        original_timeframe = self.instrument.get("timeframe")

        # STRICT VALIDATION: Only allow 'symbol' and 'timeframe' in YAML
        # All other fields (pip_location, tick_size, etc.) come from instrument
        # definition
        allowed_fields = {"symbol", "timeframe"}
        extra_fields = set(self.instrument.keys()) - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Instrument config should only contain 'symbol' "
                f"(and optionally 'timeframe'). "
                f"Found extra fields: {sorted(extra_fields)}. "
                f"These fields are auto-populated from the instrument definition "
                f"registry and should not be specified in YAML. "
                f"Remove: {', '.join(sorted(extra_fields))}"
            )

        # ALWAYS enrich from instrument definition (single source of truth)
        from trading_platform.data.instrument import get_instrument_definition

        normalized_symbol = normalize_symbol(symbol)
        instrument_def = get_instrument_definition(normalized_symbol)

        # Replace with complete instrument metadata from definition
        # Use mode='json' to serialize datetime objects properly
        self.instrument = instrument_def.model_dump(mode="json")

        # Preserve timeframe if it was in the original dict or data_request
        if original_timeframe:
            self.instrument["timeframe"] = original_timeframe
        elif self.data_request and "timeframe" in self.data_request:
            self.instrument["timeframe"] = self.data_request["timeframe"]

        return self
