"""
Aggregation functions for reporting metrics.

This module contains functions that aggregate trade-level data
into summary statistics for the final brief.
"""

from collections import defaultdict

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.models.exit_analysis import (
    OutcomeDistribution,
    PostExitAnalysis,
    SimulatedHoldAnalysis,
    SimulatedHoldPeriodAnalysis,
)


def aggregate_simulated_hold_analysis(
    trades: list[Trade],
) -> SimulatedHoldAnalysis:
    """
    Aggregate simulated hold data across all trades.

    This function processes all trades' post_exit_analysis data
    and creates aggregate statistics for each hold period
    (e.g., 10 bars, 20 bars, 50 bars).

    Args:
        trades: List of Trade objects with post_exit_analysis data.

    Returns:
        SimulatedHoldAnalysis containing aggregated results
        by hold period.

    Example output structure:
        {
            "by_hold_period": {
                "10": {
                    "avg_pnl_change_realistic": 15.5,
                    "avg_mfe_unrealistic": 2500.0,
                    "outcome_distribution": {
                        "stop_loss_hit": 33.3,
                        "take_profit_hit": 20.0,
                        "held_full_period": 46.7
                    },
                    "avg_pnl_change_by_original_exit_reason": {
                        "opposite_signal": -10.5,
                        "signal": 25.0,
                        "stop-loss": 30.0
                    }
                },
                "20": {...},
                "50": {...}
            }
        }
    """
    # Group simulations by hold period
    by_period: dict[int, list[tuple[Trade, Any]]] = defaultdict(list)

    for trade in trades:
        # Skip trades without post_exit_analysis
        if trade.post_exit_analysis is None:
            continue

        # Handle both dict and PostExitAnalysis types
        if isinstance(trade.post_exit_analysis, PostExitAnalysis):
            simulated_holds = trade.post_exit_analysis.simulated_holds
        elif isinstance(trade.post_exit_analysis, dict):
            # Legacy format - skip it
            continue
        else:
            continue

        # Group each simulation by its hold_bars
        for sim in simulated_holds:
            by_period[sim.hold_bars].append((trade, sim))

    # Build the final analysis for each period
    result = SimulatedHoldAnalysis()

    for hold_bars, trade_sim_pairs in by_period.items():
        # Extract all simulations for this period
        simulations = [sim for _, sim in trade_sim_pairs]
        trades_in_period = [trade for trade, _ in trade_sim_pairs]

        if not simulations:
            continue

        # Calculate averages
        avg_pnl_change = sum(
            s.pnl_change_vs_actual for s in simulations
        ) / len(simulations)
        avg_mfe = sum(s.mfe_during_hold for s in simulations) / len(
            simulations
        )

        # Calculate outcome distribution
        outcome_counts = {
            "stop_loss": sum(
                1 for s in simulations if s.simulated_exit_reason == "stop_loss"
            ),
            "take_profit": sum(
                1
                for s in simulations
                if s.simulated_exit_reason == "take_profit"
            ),
            "held_full_period": sum(
                1
                for s in simulations
                if s.simulated_exit_reason == "held_full_period"
            ),
        }

        total = len(simulations)
        outcome_dist = OutcomeDistribution(
            stop_loss_hit=(outcome_counts["stop_loss"] / total) * 100,
            take_profit_hit=(outcome_counts["take_profit"] / total) * 100,
            held_full_period=(outcome_counts["held_full_period"] / total)
            * 100,
        )

        # Calculate PnL change by original exit reason
        by_exit_reason: dict[str, list[float]] = defaultdict(list)
        for trade, sim in trade_sim_pairs:
            if trade.exit_reason:
                by_exit_reason[trade.exit_reason].append(
                    sim.pnl_change_vs_actual
                )

        avg_by_exit_reason = {
            reason: sum(values) / len(values)
            for reason, values in by_exit_reason.items()
        }

        # Create the period analysis
        period_analysis = SimulatedHoldPeriodAnalysis(
            avg_pnl_change_realistic=avg_pnl_change,
            avg_mfe_unrealistic=avg_mfe,
            outcome_distribution=outcome_dist,
            avg_pnl_change_by_original_exit_reason=avg_by_exit_reason,
        )

        # Add to result (keyed by string for JSON compatibility)
        result.by_hold_period[str(hold_bars)] = period_analysis

    return result
