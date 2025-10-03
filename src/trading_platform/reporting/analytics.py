"""
Analytics functions for computing advanced metrics in backtest briefs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from trading_platform.portfolio.trade import Trade


def compute_stationarity(trades: list[Trade]) -> dict:
    """
    Compute stationarity tests on the PnL series from a list of trades.

    Uses ADF (Augmented Dickey-Fuller) and KPSS tests to assess stationarity.
    Returns empty dict if fewer than 20 trades are provided.

    Args:
        trades: List of Trade objects

    Returns:
        Dictionary with test results or empty dict if insufficient data
    """
    if len(trades) < 20:
        return {}

    # Extract PnL from trades
    pnl_series = [trade.pnl for trade in trades]

    try:
        import warnings

        from statsmodels.tools.sm_exceptions import InterpolationWarning
        from statsmodels.tsa.stattools import adfuller, kpss

        # Run ADF test (null hypothesis: unit root/non-stationary)
        adf_result = adfuller(pnl_series)
        adf_p_value = float(adf_result[1])

        # Run KPSS test (null hypothesis: stationary)
        # Suppress InterpolationWarning when test statistic is outside p-value range
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=InterpolationWarning)
            kpss_result = kpss(pnl_series)
            kpss_p_value = float(kpss_result[1])

        return {
            "adf_p_value": adf_p_value,
            "kpss_p_value": kpss_p_value,
        }
    except Exception:
        # Return empty dict on any error (e.g., import issues, computation errors)
        return {}


def compute_feature_analysis(trades: list[Trade]) -> dict:
    """
    Compute feature correlation analysis from trade entry contexts.

    Extracts numerical features from context_at_entry of each trade and
    calculates a Pearson correlation matrix.

    Args:
        trades: List of Trade objects

    Returns:
        Dictionary with correlation matrix or empty dict if no valid data
    """
    if not trades:
        return {}

    # Extract context_at_entry from trades
    contexts = []
    for trade in trades:
        ctx = getattr(trade, "context_at_entry", None)
        if ctx and isinstance(ctx, dict):
            contexts.append(ctx)

    if not contexts:
        return {}

    try:
        import pandas as pd

        # Convert contexts to DataFrame
        df = pd.DataFrame(contexts)

        # Select only numeric columns
        numeric_df = df.select_dtypes(include=["number"])

        if numeric_df.empty:
            return {}

        # Calculate correlation matrix
        corr_matrix = numeric_df.corr()

        # Convert to nested dict format for JSON serialization
        corr_dict: dict[str, dict[str, float]] = {}
        for col in corr_matrix.columns:
            corr_dict[col] = {}
            for idx in corr_matrix.index:
                corr_dict[col][idx] = float(corr_matrix.loc[idx, col])

        return {"feature_correlation_matrix": corr_dict}

    except Exception:
        # Return empty dict on any error (e.g., import issues, computation errors)
        return {}


def compute_activity(trades: list[Trade]) -> dict:
    """
    Compute trading activity metrics from a list of trades.

    Calculates average trades per day based on the span from first to last trade.

    Args:
        trades: List of Trade objects

    Returns:
        Dictionary with activity metrics or empty dict if no trades
    """
    if not trades:
        return {}

    if len(trades) == 1:
        return {"average_trades_per_day": 1.0}

    try:
        # Get date range from first to last trade
        sorted_trades = sorted(trades, key=lambda t: t.entry_time)
        first_date = sorted_trades[0].entry_time.date()
        last_date = sorted_trades[-1].entry_time.date()

        # Calculate number of days (inclusive)
        days_span = (last_date - first_date).days + 1

        # Calculate average trades per day
        avg_trades_per_day = float(len(trades)) / float(days_span)

        return {"average_trades_per_day": round(avg_trades_per_day, 2)}

    except Exception:
        # Return empty dict on any error
        return {}


def compute_timing_buckets(trades: list[Trade]) -> dict:
    """
    Compute aggregate PnL and win-rate grouped by hour_of_day and day_of_week.

    Groups trades by entry time and calculates performance metrics for each bucket.

    Args:
        trades: List of Trade objects

    Returns:
        Dictionary with timing bucket analysis or empty dict if no trades
    """
    if not trades:
        return {}

    try:
        from collections import defaultdict

        # Initialize buckets
        hour_buckets: dict[int, dict[str, Any]] = defaultdict(
            lambda: {"trades": [], "total_pnl": 0.0}
        )
        day_buckets: dict[int, dict[str, Any]] = defaultdict(
            lambda: {"trades": [], "total_pnl": 0.0}
        )

        # Group trades by time buckets
        for trade in trades:
            hour = trade.entry_time.hour
            day_of_week = trade.entry_time.weekday()  # Monday = 0, Sunday = 6

            hour_buckets[hour]["trades"].append(trade)
            hour_buckets[hour]["total_pnl"] += trade.pnl

            day_buckets[day_of_week]["trades"].append(trade)
            day_buckets[day_of_week]["total_pnl"] += trade.pnl

        # Calculate metrics for each bucket
        def calculate_metrics(bucket_data):
            trades_in_bucket = bucket_data["trades"]
            n_trades = len(trades_in_bucket)
            total_pnl = bucket_data["total_pnl"]
            winning_trades = [t for t in trades_in_bucket if t.pnl > 0]
            win_rate = len(winning_trades) / n_trades if n_trades > 0 else 0.0

            return {
                "n_trades": n_trades,
                "total_pnl": round(total_pnl, 2),
                "win_rate": round(win_rate, 3),
            }

        # Convert to final format
        hour_results = {
            hour: calculate_metrics(data) for hour, data in hour_buckets.items()
        }
        day_results = {
            day: calculate_metrics(data) for day, data in day_buckets.items()
        }

        return {
            "hour_of_day": hour_results,
            "day_of_week": day_results,
        }

    except Exception:
        # Return empty dict on any error
        return {}


def compute_contrasts(trades: list[Trade]) -> dict:
    """
    Compute performance contrasts between long and short trades.

    Calculates detailed performance metrics separately for long and short positions
    to enable comparison of strategy performance by side.

    Args:
        trades: List of Trade objects

    Returns:
        Dictionary with 'long_trades' and 'short_trades' keys, each containing
        performance metrics like n_trades, win_rate, avg_pnl, etc.
        Returns empty dict if no trades or on error.
    """
    try:
        if not trades:
            return {}

        # Separate trades by side
        long_trades = [t for t in trades if t.side == "long"]
        short_trades = [t for t in trades if t.side == "short"]

        def calculate_side_metrics(side_trades):
            """Calculate performance metrics for a list of trades."""
            if not side_trades:
                return {
                    "n_trades": 0,
                    "win_rate": 0.0,
                    "avg_pnl": 0.0,
                    "total_pnl": 0.0,
                    "avg_win": 0.0,
                    "avg_loss": 0.0,
                }

            n_trades = len(side_trades)
            total_pnl = sum(t.pnl for t in side_trades)
            avg_pnl = total_pnl / n_trades

            winning_trades = [t for t in side_trades if t.pnl > 0]
            losing_trades = [t for t in side_trades if t.pnl <= 0]

            win_rate = len(winning_trades) / n_trades
            avg_win = (
                sum(t.pnl for t in winning_trades) / len(winning_trades)
                if winning_trades
                else 0.0
            )
            avg_loss = (
                sum(t.pnl for t in losing_trades) / len(losing_trades)
                if losing_trades
                else 0.0
            )
            avg_win_gross = (
                sum(t.pnl_gross for t in winning_trades) / len(winning_trades)
                if winning_trades
                else 0.0
            )
            avg_loss_gross = (
                sum(t.pnl_gross for t in losing_trades) / len(losing_trades)
                if losing_trades
                else 0.0
            )

            return {
                "n_trades": n_trades,
                "win_rate": round(win_rate, 3),
                "avg_pnl": round(avg_pnl, 2),
                "total_pnl": round(total_pnl, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "avg_win_gross": round(avg_win_gross, 2),
                "avg_loss_gross": round(avg_loss_gross, 2),
            }

        return {
            "long_trades": calculate_side_metrics(long_trades),
            "short_trades": calculate_side_metrics(short_trades),
        }

    except Exception:
        # Return empty dict on any error
        return {}


def compute_stop_tp_candidates(trades: list[Trade]) -> dict:
    """
    Compute stop-loss and take-profit candidates from MFE/MAE distributions.

    Calculates percentiles of Maximum Favorable Excursion (MFE) and Maximum
    Adverse Excursion (MAE) values to suggest potential stop and target levels.

    Args:
        trades: List of Trade objects with mfe_currency and mae_currency values

    Returns:
        Dictionary with 'mfe_percentiles' and 'mae_percentiles' keys containing
        25th, 50th, and 75th percentile values.
        Returns empty dict if no trades or on error.
    """
    try:
        if not trades:
            return {}

        # Extract MFE and MAE values, filtering out None values
        mfe_values = [t.mfe_currency for t in trades if t.mfe_currency is not None]
        mae_values = [t.mae_currency for t in trades if t.mae_currency is not None]

        # If no valid MFE or MAE data, return empty dict
        if not mfe_values or not mae_values:
            return {}

        def calculate_percentiles(values):
            """Calculate 25th, 50th, 75th percentiles of a list of values."""
            if not values:
                return {"25th": 0.0, "50th": 0.0, "75th": 0.0}

            sorted_values = sorted(values)
            n = len(sorted_values)

            def percentile(p):
                """Calculate percentile using linear interpolation method."""
                index = (n - 1) * (p / 100)
                lower = int(index)
                upper = lower + 1

                if upper >= n:
                    return sorted_values[lower]

                weight = index - lower
                return (
                    sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
                )

            return {
                "25th": round(percentile(25), 2),
                "50th": round(percentile(50), 2),  # median
                "75th": round(percentile(75), 2),
            }

        return {
            "mfe_percentiles": calculate_percentiles(mfe_values),
            "mae_percentiles": calculate_percentiles(mae_values),
        }

    except Exception:
        # Return empty dict on any error
        return {}


def compute_exit_efficiency(trades: list[Trade]) -> dict:
    """
    Analyze exit efficiency by comparing actual exits to post-exit price movement.

    For each exit reason (TP, SL, signal, etc.), calculates:
    - Premature exit rate (left profit on table)
    - False exit rate (price reversed favorably)
    - Average opportunity cost at different horizons

    Returns empty dict if trades don't have post_exit_analysis data.
    """
    if not trades:
        return {}

    # Filter trades with post-exit data
    trades_with_analysis = [t for t in trades if t.post_exit_analysis]
    if not trades_with_analysis:
        return {}

    # Determine which horizons are available
    first_trade = trades_with_analysis[0]
    # post_exit_analysis is guaranteed non-None due to filter above
    assert first_trade.post_exit_analysis is not None
    horizons = sorted([int(h) for h in first_trade.post_exit_analysis.keys()])

    def analyze_by_exit_reason(reason: str) -> dict:
        """Analyze trades that exited for a specific reason."""
        reason_trades = [t for t in trades_with_analysis if t.exit_reason == reason]
        if not reason_trades:  # pragma: no cover
            return {}  # pragma: no cover - Defensive: exit_reasons built from trades

        n_trades = len(reason_trades)
        analysis: dict[str, Any] = {"n_trades": n_trades}

        for horizon in horizons:
            h_key = str(horizon)

            # Calculate opportunity cost (what we could have made by holding longer)
            opp_costs = []
            premature_count = 0
            false_exit_count = 0

            for t in reason_trades:
                # post_exit_analysis is guaranteed non-None due to filter
                assert t.post_exit_analysis is not None
                post_data = t.post_exit_analysis.get(h_key, {})
                post_mfe = post_data.get("mfe", 0.0)
                post_data.get("mae", 0.0)

                # Opportunity cost = what we left on the table
                opp_cost = post_mfe  # Positive if price continued favorably
                opp_costs.append(opp_cost)

                # Classify based on exit reason
                if reason in ["take_profit", "tp"]:
                    # Premature TP: price continued significantly after we closed
                    if post_mfe > abs(t.pnl_gross) * 2:  # 2x our profit
                        premature_count += 1

                elif reason in ["stop_loss", "sl", "stop"]:
                    # False stop: price reversed and would have been profitable
                    if t.initial_risk_ccy and post_mfe > abs(t.initial_risk_ccy):
                        false_exit_count += 1

                else:  # Signal exits or other
                    # Good exit if price went against us (post_mae got worse)
                    # Bad exit if price continued favorably (high post_mfe)
                    if post_mfe > abs(t.pnl_gross) * 1.5:  # Left >1.5x profit on table
                        premature_count += 1

            avg_opp_cost = sum(opp_costs) / len(opp_costs) if opp_costs else 0.0
            analysis[f"avg_opportunity_cost_{h_key}bar"] = round(avg_opp_cost, 2)

            # Only include rates on the longest horizon to avoid clutter
            if horizon == horizons[-1]:
                if reason in ["take_profit", "tp"]:
                    analysis["premature_exit_rate"] = round(
                        premature_count / n_trades, 3
                    )
                elif reason in ["stop_loss", "sl", "stop"]:
                    analysis["false_stop_rate"] = round(false_exit_count / n_trades, 3)
                else:
                    analysis["suboptimal_exit_rate"] = round(
                        premature_count / n_trades, 3
                    )

        return analysis

    # Group by exit reason
    exit_reasons = set(t.exit_reason for t in trades_with_analysis if t.exit_reason)
    by_exit_reason = {}
    for reason in exit_reasons:
        reason_analysis = analyze_by_exit_reason(reason)
        if reason_analysis:  # pragma: no cover
            by_exit_reason[reason] = (
                reason_analysis  # pragma: no cover - Always true when
                # exit_reasons from trades
            )

    # Optimal hold duration analysis: what if we held for N bars instead?
    current_avg_pnl = sum(t.pnl for t in trades_with_analysis) / len(
        trades_with_analysis
    )
    optimal_hold: dict[str, Any] = {"current_avg_pnl": round(current_avg_pnl, 2)}

    for horizon in horizons:
        h_key = str(horizon)
        # Calculate what avg PnL would be if we held each trade for this many more bars
        # We take the better of: actual exit or post_exit_mfe
        hypothetical_pnls = []
        for t in trades_with_analysis:
            # post_exit_analysis is guaranteed non-None due to filter
            assert t.post_exit_analysis is not None
            post_data = t.post_exit_analysis.get(h_key, {})
            post_mfe = post_data.get("mfe", 0.0)
            # If we had held longer, we could have captured this extra profit
            # But we also pay costs on the original trade
            hypothetical_pnl = t.pnl + post_mfe
            hypothetical_pnls.append(hypothetical_pnl)

        avg_hypothetical = (
            sum(hypothetical_pnls) / len(hypothetical_pnls)
            if hypothetical_pnls
            else 0.0
        )
        optimal_hold[f"if_held_{h_key}_bars"] = round(avg_hypothetical, 2)

    return {
        "by_exit_reason": by_exit_reason,
        "optimal_hold_analysis": optimal_hold,
    }
