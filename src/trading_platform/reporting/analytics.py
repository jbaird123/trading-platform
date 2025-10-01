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
        from statsmodels.tsa.stattools import adfuller, kpss

        # Run ADF test (null hypothesis: unit root/non-stationary)
        adf_result = adfuller(pnl_series)
        adf_p_value = float(adf_result[1])

        # Run KPSS test (null hypothesis: stationary)
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
