"""Pydantic models for realistic exit analysis."""

from typing import Literal

from pydantic import BaseModel, Field


class SimulatedHold(BaseModel):
    """
    Represents the outcome of a simulated hold period.

    This model captures what would have happened if a trade was
    held for N additional bars after the actual exit, accounting
    for stop-loss and take-profit triggers.
    """

    hold_bars: int = Field(
        ..., description="The duration of the simulation in bars."
    )
    simulated_pnl: float = Field(
        ...,
        description=(
            "The realistic PnL achieved during the simulated hold."
        ),
    )
    pnl_change_vs_actual: float = Field(
        ...,
        description=(
            "The difference between simulated_pnl and the trade's "
            "original PnL."
        ),
    )
    simulated_exit_reason: Literal[
        "stop_loss", "take_profit", "held_full_period"
    ] = Field(
        ..., description="The reason the simulated hold ended."
    )
    simulated_exit_bar_offset: int = Field(
        ...,
        description="How many bars into the simulation the exit occurred.",
    )
    mfe_during_hold: float = Field(
        ..., description="MFE observed during the actual simulated hold."
    )
    mfe_bar_offset: int = Field(
        ...,
        description=(
            "Bar offset where the MFE occurred during the hold."
        ),
    )
    mae_during_hold: float = Field(
        ..., description="MAE observed during the actual simulated hold."
    )
    mae_bar_offset: int = Field(
        ...,
        description=(
            "Bar offset where the MAE occurred during the hold."
        ),
    )


class PostExitAnalysis(BaseModel):
    """
    Container for all simulated hold periods for a single trade.

    This replaces the old dict-based post_exit_analysis structure
    with a properly typed model that contains realistic simulation
    results instead of just raw MFE/MAE values.
    """

    simulated_holds: list[SimulatedHold] = []


class OutcomeDistribution(BaseModel):
    """Distribution of simulation outcomes (as percentages)."""

    stop_loss_hit: float = 0.0
    take_profit_hit: float = 0.0
    held_full_period: float = 0.0


class SimulatedHoldPeriodAnalysis(BaseModel):
    """
    Aggregate analysis for a specific hold period across all trades.

    Example: For all trades that were simulated with 10 extra bars,
    this contains the average outcomes.
    """

    avg_pnl_change_realistic: float = Field(
        ...,
        description=(
            "Average change in PnL if held this many extra bars "
            "(accounting for stops)."
        ),
    )
    avg_mfe_unrealistic: float = Field(
        ...,
        description=(
            "Average MFE during the hold period (for comparison "
            "with old metrics)."
        ),
    )
    outcome_distribution: OutcomeDistribution = Field(
        ...,
        description=(
            "Breakdown of how simulations ended (stop/tp/full hold)."
        ),
    )
    avg_pnl_change_by_original_exit_reason: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Average PnL change broken down by the trade's original "
            "exit reason."
        ),
    )


class SimulatedHoldAnalysis(BaseModel):
    """
    Top-level container for all simulated hold analysis.

    This will appear in the brief under exit_efficiency as
    'simulated_hold_analysis'.
    """

    by_hold_period: dict[str, SimulatedHoldPeriodAnalysis] = Field(
        default_factory=dict,
        description=(
            "Analysis keyed by hold period (e.g., '10', '20', '50')."
        ),
    )
