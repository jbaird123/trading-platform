"""Tests for analytics functions.

# Validates: [JSON-11.5], [JSON-11.6], [JSON-11.7], [JSON-11.8]
"""

from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.analytics import compute_stationarity


def _mock_trade(pnl: float, ts: datetime | None = None) -> Trade:
    """Helper to create mock Trade objects for testing."""
    entry_time = ts or datetime(2024, 1, 1)
    return Trade(
        symbol="TEST",
        entry_time=entry_time,
        exit_time=entry_time + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0 + pnl / 10000,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
    )


def test_compute_stationarity():
    """Test that compute_stationarity returns expected keys and types."""
    # Create mock trades with sufficient data points (20+ trades required)
    trades = [_mock_trade(float(i % 5 - 2)) for i in range(25)]

    result = compute_stationarity(trades)

    # Should return dict with expected keys
    assert isinstance(result, dict)
    assert "adf_p_value" in result
    assert "kpss_p_value" in result

    # Values should be floats between 0 and 1 (p-values)
    assert isinstance(result["adf_p_value"], float)
    assert isinstance(result["kpss_p_value"], float)
    assert 0 <= result["adf_p_value"] <= 1
    assert 0 <= result["kpss_p_value"] <= 1


def test_compute_stationarity_insufficient_data():
    """Test that compute_stationarity returns empty dict with < 20 trades."""
    trades = [_mock_trade(1.0) for _ in range(19)]  # Less than 20 trades

    result = compute_stationarity(trades)

    assert result == {}


def test_compute_stationarity_handles_statsmodels_errors(monkeypatch):
    """Test compute_stationarity returns empty dict when statsmodels fails."""
    import statsmodels.tsa.stattools as stattools
    from trading_platform.reporting import analytics

    trades = [_mock_trade(float(i % 3 - 1)) for i in range(25)]

    def _raise_error(_series):
        raise ValueError("boom")

    monkeypatch.setattr(stattools, "adfuller", _raise_error)

    result = analytics.compute_stationarity(trades)

    assert result == {}


def test_compute_feature_analysis():
    """Test that compute_feature_analysis extracts and correlates features."""
    from trading_platform.reporting.analytics import compute_feature_analysis

    # Create trades with context_at_entry data containing numerical features
    trades = []
    for i in range(5):
        ctx = {
            "ema_fast": 1.2 + i * 0.1,  # Correlated features
            "ema_slow": 1.0 + i * 0.05,
            "rsi": 50.0 + i * 2.0,
            "atr": 0.01 + i * 0.002,
        }
        trade = _mock_trade(float(i - 2))
        # Replace the trade with one that has context
        trade = Trade(
            symbol=trade.symbol,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            side=trade.side,
            size=trade.size,
            pnl=trade.pnl,
            context_at_entry=ctx,
        )
        trades.append(trade)

    result = compute_feature_analysis(trades)

    # Should return dict with feature correlation matrix
    assert isinstance(result, dict)
    assert "feature_correlation_matrix" in result

    corr_matrix = result["feature_correlation_matrix"]
    assert isinstance(corr_matrix, dict)

    # Should have correlations between features
    assert "ema_fast" in corr_matrix
    assert "ema_slow" in corr_matrix
    assert "rsi" in corr_matrix
    assert "atr" in corr_matrix

    # Each feature should have correlations with all features (including itself = 1.0)
    for feature in ["ema_fast", "ema_slow", "rsi", "atr"]:
        assert isinstance(corr_matrix[feature], dict)
        assert corr_matrix[feature][feature] == 1.0  # Self-correlation should be 1.0


def test_compute_feature_analysis_no_context():
    """Test compute_feature_analysis returns empty dict when no context available."""
    from trading_platform.reporting.analytics import compute_feature_analysis

    # Create trades without context_at_entry
    trades = [_mock_trade(1.0) for _ in range(3)]

    result = compute_feature_analysis(trades)

    assert result == {}


def test_compute_feature_analysis_empty_trades():
    """Test compute_feature_analysis handles empty trade list."""
    from trading_platform.reporting.analytics import compute_feature_analysis

    result = compute_feature_analysis([])

    assert result == {}


def test_compute_feature_analysis_handles_pandas_errors(monkeypatch):
    """Test compute_feature_analysis returns empty dict when pandas fails."""
    import pandas as pd
    from trading_platform.reporting import analytics

    trades = []
    for i in range(4):
        ctx = {
            "ema_fast": 1.0 + float(i) * 0.1,
            "ema_slow": 1.1 + float(i) * 0.1,
        }
        trade = _mock_trade(float(i))
        trade = Trade(
            symbol=trade.symbol,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            side=trade.side,
            size=trade.size,
            pnl=trade.pnl,
            context_at_entry=ctx,
        )
        trades.append(trade)

    def _raise_dataframe(_contexts):
        raise ValueError("bad frame")

    monkeypatch.setattr(pd, "DataFrame", _raise_dataframe)

    result = analytics.compute_feature_analysis(trades)

    assert result == {}


def test_compute_activity():
    """Test compute_activity calculates average trades per day."""
    from trading_platform.reporting.analytics import compute_activity

    # Create trades over 4 days (3 trades total = 0.75 trades/day)
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    trades = [
        _mock_trade(100.0, base_time),  # Day 1
        _mock_trade(200.0, base_time + timedelta(days=1)),  # Day 2
        _mock_trade(-50.0, base_time + timedelta(days=3)),  # Day 4
    ]

    result = compute_activity(trades)

    assert isinstance(result, dict)
    assert "average_trades_per_day" in result

    # 3 trades over 4 days (from day 1 to day 4) = 0.75 trades/day
    expected_avg = 3.0 / 4.0
    assert abs(result["average_trades_per_day"] - expected_avg) < 0.001


def test_compute_activity_empty_trades():
    """Test compute_activity handles empty trade list."""
    from trading_platform.reporting.analytics import compute_activity

    result = compute_activity([])

    assert result == {}


def test_compute_activity_single_trade():
    """Test compute_activity with single trade."""
    from trading_platform.reporting.analytics import compute_activity

    trades = [_mock_trade(100.0)]

    result = compute_activity(trades)

    assert result == {"average_trades_per_day": 1.0}


def test_compute_activity_handles_bad_trade():
    """Test compute_activity returns empty dict on data errors."""
    from trading_platform.reporting import analytics

    class BadTrade:
        """Trade stub without valid entry_time."""

        def __init__(self) -> None:
            self.entry_time = None

    bad_trades = [BadTrade(), BadTrade()]

    result = analytics.compute_activity(bad_trades)  # type: ignore

    assert result == {}


def test_compute_timing_buckets():
    """Test compute_timing_buckets calculates PnL and win-rate by time."""
    from trading_platform.reporting.analytics import compute_timing_buckets

    # Create trades at different hours and days of week
    trades = [
        # Monday (weekday 0), 10 AM
        _mock_trade(100.0, datetime(2024, 1, 1, 10, 0, 0)),  # Monday 10am +100
        # Tuesday (weekday 1), 2 PM
        _mock_trade(-50.0, datetime(2024, 1, 2, 14, 0, 0)),  # Tuesday 2pm -50
        # Wednesday (weekday 2), 10 AM
        _mock_trade(200.0, datetime(2024, 1, 3, 10, 0, 0)),  # Wednesday 10am +200
        # Friday (weekday 4), 2 PM
        _mock_trade(-25.0, datetime(2024, 1, 5, 14, 0, 0)),  # Friday 2pm -25
    ]

    result = compute_timing_buckets(trades)

    assert isinstance(result, dict)
    assert "hour_of_day" in result
    assert "day_of_week" in result

    # Check hour buckets
    hour_buckets = result["hour_of_day"]
    assert 10 in hour_buckets  # 10 AM bucket
    assert 14 in hour_buckets  # 2 PM bucket

    # Hour 10: 2 trades, total PnL = +300, win_rate = 1.0 (both wins)
    assert hour_buckets[10]["n_trades"] == 2
    assert hour_buckets[10]["total_pnl"] == 300.0
    assert hour_buckets[10]["win_rate"] == 1.0

    # Hour 14: 2 trades, total PnL = -75, win_rate = 0.0 (both losses)
    assert hour_buckets[14]["n_trades"] == 2
    assert hour_buckets[14]["total_pnl"] == -75.0
    assert hour_buckets[14]["win_rate"] == 0.0

    # Check day buckets
    day_buckets = result["day_of_week"]
    assert 0 in day_buckets  # Monday
    assert 1 in day_buckets  # Tuesday
    assert 2 in day_buckets  # Wednesday
    assert 4 in day_buckets  # Friday


def test_compute_timing_buckets_empty_trades():
    """Test compute_timing_buckets handles empty trade list."""
    from trading_platform.reporting.analytics import compute_timing_buckets

    result = compute_timing_buckets([])

    assert result == {}


def test_compute_timing_buckets_handles_bad_trade():
    """Test compute_timing_buckets returns empty dict on data errors."""
    from trading_platform.reporting import analytics

    class BadTrade:
        """Trade stub missing a usable entry_time."""

        def __init__(self) -> None:
            self.entry_time = None
            self.pnl = 0.0

    result = analytics.compute_timing_buckets([BadTrade()])  # type: ignore

    assert result == {}


def test_brief_integration_with_contrasts():
    """Test that contrasts are integrated into brief generation."""
    import datetime

    from trading_platform.portfolio.trade import Trade
    from trading_platform.reporting.brief import generate_brief

    # Create trades with specific sides using helper function
    def _mock_trade_with_side(pnl: float, side: str) -> Trade:
        entry_time = datetime.datetime(2024, 1, 1)
        return Trade(
            symbol="TEST",
            entry_time=entry_time,
            exit_time=entry_time + timedelta(hours=1),
            entry_price=1.0,
            exit_price=1.0 + pnl / 10000,
            side=side,
            size=1.0,
            pnl=pnl,
        )

    # Create test trades with mixed sides
    trades = [
        _mock_trade_with_side(100.0, "long"),
        _mock_trade_with_side(-50.0, "short"),
    ]

    # Field definitions required for new sections
    field_definitions = {
        "contrasts": {
            "description": "Performance contrasts between long and short trades",
            "long_trades": {"description": "Performance metrics for long positions"},
            "short_trades": {"description": "Performance metrics for short positions"},
        }
    }

    brief = generate_brief(
        meta={},
        params={},
        trades=trades,
        initial_cash=10000,
        field_definitions=field_definitions,
    )

    assert "contrasts" in brief
    assert "long_trades" in brief["contrasts"]
    assert "short_trades" in brief["contrasts"]


def test_compute_stop_tp_candidates():
    """Test compute_stop_tp_candidates calculates percentiles of MFE and MAE."""
    from trading_platform.reporting.analytics import compute_stop_tp_candidates

    # Create trades with MFE and MAE values for helper function
    def _mock_trade_with_mfe_mae(pnl: float, mfe: float, mae: float) -> Trade:
        entry_time = datetime(2024, 1, 1)
        return Trade(
            symbol="TEST",
            entry_time=entry_time,
            exit_time=entry_time + timedelta(hours=1),
            entry_price=1.0,
            exit_price=1.0 + pnl / 10000,
            side="long" if pnl >= 0 else "short",
            size=1.0,
            pnl=pnl,
            mfe_currency=mfe,
            mae_currency=mae,
        )

    # Create test trades with varying MFE/MAE values
    trades = [
        _mock_trade_with_mfe_mae(100.0, 150.0, -25.0),
        _mock_trade_with_mfe_mae(200.0, 250.0, -50.0),
        _mock_trade_with_mfe_mae(50.0, 100.0, -10.0),
        _mock_trade_with_mfe_mae(-100.0, 25.0, -200.0),
    ]

    result = compute_stop_tp_candidates(trades)

    # Check structure
    assert "mfe_percentiles" in result
    assert "mae_percentiles" in result

    # Check MFE percentiles (150, 250, 100, 25 -> sorted: 25, 100, 150, 250)
    mfe_perc = result["mfe_percentiles"]
    assert "25th" in mfe_perc
    assert "50th" in mfe_perc
    assert "75th" in mfe_perc

    # Check MAE percentiles (-25, -50, -10, -200 -> sorted: -200, -50, -25, -10)
    mae_perc = result["mae_percentiles"]
    assert "25th" in mae_perc
    assert "50th" in mae_perc
    assert "75th" in mae_perc


def test_compute_stop_tp_candidates_empty_trades():
    """Test compute_stop_tp_candidates handles empty trade list."""
    from trading_platform.reporting.analytics import compute_stop_tp_candidates

    result = compute_stop_tp_candidates([])

    assert result == {}


def test_brief_integration_with_stop_tp_candidates():
    """Test that stop_tp_candidates are integrated into brief generation."""
    import datetime

    from trading_platform.portfolio.trade import Trade
    from trading_platform.reporting.brief import generate_brief

    # Create trades with MFE and MAE values for helper function
    def _mock_trade_with_mfe_mae(pnl: float, mfe: float, mae: float) -> Trade:
        entry_time = datetime.datetime(2024, 1, 1)
        return Trade(
            symbol="TEST",
            entry_time=entry_time,
            exit_time=entry_time + timedelta(hours=1),
            entry_price=1.0,
            exit_price=1.0 + pnl / 10000,
            side="long" if pnl >= 0 else "short",
            size=1.0,
            pnl=pnl,
            mfe_currency=mfe,
            mae_currency=mae,
        )

    # Create test trades with MFE/MAE values
    trades = [
        _mock_trade_with_mfe_mae(100.0, 150.0, -25.0),
        _mock_trade_with_mfe_mae(200.0, 250.0, -50.0),
    ]

    # Field definitions required for new sections
    field_definitions = {
        "stop_tp_candidates": {
            "description": (
                "Stop-loss and take-profit candidates from MFE/MAE distributions"
            ),
            "mfe_percentiles": {
                "description": "Percentiles of Maximum Favorable Excursion"
            },
            "mae_percentiles": {
                "description": "Percentiles of Maximum Adverse Excursion"
            },
        }
    }

    brief = generate_brief(
        meta={},
        params={},
        trades=trades,
        initial_cash=10000,
        field_definitions=field_definitions,
    )

    assert "stop_tp_candidates" in brief
    assert "mfe_percentiles" in brief["stop_tp_candidates"]
    assert "mae_percentiles" in brief["stop_tp_candidates"]


def test_brief_integration_with_timing_buckets():
    """Test that timing buckets are integrated into brief generation."""
    import datetime

    from trading_platform.portfolio.trade import Trade
    from trading_platform.reporting.brief import generate_brief

    # Create test trades with timing data
    trades = [
        Trade(
            symbol="TEST",
            entry_time=datetime.datetime(2024, 1, 1, 9, 30, 0),
            exit_time=datetime.datetime(2024, 1, 1, 10, 30, 0),
            entry_price=1.0,
            exit_price=1.01,
            side="long",
            size=1000.0,
            pnl=100.0,
        )
    ]

    # Field definitions required for new sections
    field_definitions = {
        "timing_buckets": {
            "description": "Performance analysis by time buckets",
            "hour_of_day": {"description": "Performance by hour of day"},
            "day_of_week": {"description": "Performance by day of week"},
        }
    }

    brief = generate_brief(
        meta={},
        params={},
        trades=trades,
        initial_cash=10000,
        field_definitions=field_definitions,
    )

    assert "timing_buckets" in brief
    assert "hour_of_day" in brief["timing_buckets"]
    assert "day_of_week" in brief["timing_buckets"]


def test_compute_contrasts():
    """Test compute_contrasts calculates performance for longs vs shorts."""
    from trading_platform.reporting.analytics import compute_contrasts

    # Create trades with specific sides using helper function
    def _mock_trade_with_side(pnl: float, side: str) -> Trade:
        entry_time = datetime(2024, 1, 1)
        return Trade(
            symbol="TEST",
            entry_time=entry_time,
            exit_time=entry_time + timedelta(hours=1),
            entry_price=1.0,
            exit_price=1.0 + pnl / 10000,
            side=side,
            size=1.0,
            pnl=pnl,
        )

    # Create test trades - mix of long and short positions
    trades = [
        _mock_trade_with_side(100.0, "long"),  # Profitable long
        _mock_trade_with_side(-50.0, "short"),  # Losing short
        _mock_trade_with_side(200.0, "long"),  # Profitable long
        _mock_trade_with_side(-25.0, "short"),  # Losing short
    ]

    result = compute_contrasts(trades)

    # Check structure
    assert "long_trades" in result
    assert "short_trades" in result

    # Check long trades performance
    long_perf = result["long_trades"]
    assert long_perf["n_trades"] == 2
    assert long_perf["win_rate"] == 1.0  # Both long trades profitable
    assert long_perf["avg_pnl"] == 150.0  # (100 + 200) / 2

    # Check short trades performance
    short_perf = result["short_trades"]
    assert short_perf["n_trades"] == 2
    assert short_perf["win_rate"] == 0.0  # Both short trades losing
    assert short_perf["avg_pnl"] == -37.5  # (-50 + -25) / 2


def test_compute_contrasts_empty_trades():
    """Test compute_contrasts handles empty trade list."""
    from trading_platform.reporting.analytics import compute_contrasts

    result = compute_contrasts([])

    assert result == {}


def test_compute_contrasts_handles_bad_trade():
    """Test compute_contrasts returns empty dict when calculations fail."""
    from trading_platform.reporting import analytics

    class BadTrade:
        """Trade stub with failing pnl property."""

        side = "long"

        @property
        def pnl(self) -> float:
            raise ValueError("pnl unavailable")

    result = analytics.compute_contrasts([BadTrade()])  # type: ignore

    assert result == {}


def test_compute_stop_tp_candidates_missing_values():
    """Test compute_stop_tp_candidates handles missing MFE/MAE."""
    from trading_platform.reporting.analytics import compute_stop_tp_candidates

    trade = _mock_trade(50.0)
    trade = Trade(
        symbol=trade.symbol,
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        side=trade.side,
        size=trade.size,
        pnl=trade.pnl,
        mfe_currency=None,
        mae_currency=-10.0,
    )

    result = compute_stop_tp_candidates([trade])

    assert result == {}


def test_compute_stop_tp_candidates_single_value():
    """Test percentiles when only one trade provides excursions."""
    from trading_platform.reporting.analytics import compute_stop_tp_candidates

    trade = _mock_trade(25.0)
    trade = Trade(
        symbol=trade.symbol,
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        side=trade.side,
        size=trade.size,
        pnl=trade.pnl,
        mfe_currency=75.0,
        mae_currency=-30.0,
    )

    result = compute_stop_tp_candidates([trade])

    assert result["mfe_percentiles"]["75th"] == 75.0
    assert result["mae_percentiles"]["25th"] == -30.0


def test_compute_stop_tp_candidates_handles_bad_trade():
    """Test compute_stop_tp_candidates returns empty dict on failure."""
    from trading_platform.reporting import analytics

    class BadTrade:
        """Trade stub with failing excursion accessors."""

        @property
        def mfe_currency(self) -> float:
            raise ValueError("no mfe")

        @property
        def mae_currency(self) -> float:
            return 0.0

    result = analytics.compute_stop_tp_candidates([BadTrade()])  # type: ignore

    assert result == {}


def test_stop_tp_percentiles_empty_list_path():
    """Directly execute percentile helper with empty input."""
    import types

    from trading_platform.reporting import analytics

    helper_code = None
    for const in analytics.compute_stop_tp_candidates.__code__.co_consts:
        is_helper = isinstance(const, types.CodeType)
        if is_helper and const.co_name == "calculate_percentiles":
            helper_code = const
            break

    assert helper_code is not None

    helper = types.FunctionType(
        helper_code, analytics.compute_stop_tp_candidates.__globals__
    )

    assert helper([]) == {"25th": 0.0, "50th": 0.0, "75th": 0.0}


def test_compute_exit_efficiency_empty_trades() -> None:
    """Test exit efficiency with empty trades list."""
    # Validates: [REQ-ANALYTICS-EXIT-001] Handle empty trades
    from trading_platform.reporting.analytics import compute_exit_efficiency

    result = compute_exit_efficiency([])
    assert result == {}


def test_compute_exit_efficiency_no_post_exit_data() -> None:
    """Test exit efficiency with trades lacking post_exit_analysis."""
    # Validates: [REQ-ANALYTICS-EXIT-002] Handle no post-exit data
    from dataclasses import replace
    from datetime import datetime

    trade = _mock_trade(100.0, datetime(2024, 1, 1))
    trade = replace(trade, exit_reason="signal", post_exit_analysis=None)

    from trading_platform.reporting.analytics import compute_exit_efficiency
    result = compute_exit_efficiency([trade])
    assert result == {}


def test_compute_exit_efficiency_take_profit_premature() -> None:
    """Test premature take-profit detection."""
    # Validates: [REQ-ANALYTICS-EXIT-003] Detect premature take-profits
    from dataclasses import replace
    from datetime import datetime

    trade = _mock_trade(100.0, datetime(2024, 1, 1))
    trade = replace(
        trade,
        exit_reason="take_profit",
        pnl_gross=100.0,
        post_exit_analysis={
            "5": {"mfe": 250.0, "mae": -10.0},  # MFE > 2x profit = premature
            "10": {"mfe": 300.0, "mae": -20.0},
        },
    )

    from trading_platform.reporting.analytics import compute_exit_efficiency
    result = compute_exit_efficiency([trade])

    assert "by_exit_reason" in result
    assert "take_profit" in result["by_exit_reason"]
    tp_analysis = result["by_exit_reason"]["take_profit"]
    assert tp_analysis["n_trades"] == 1
    assert "premature_exit_rate" in tp_analysis
    assert tp_analysis["premature_exit_rate"] == 1.0


def test_compute_exit_efficiency_stop_loss_false() -> None:
    """Test false stop-loss detection."""
    # Validates: [REQ-ANALYTICS-EXIT-004] Detect false stop-losses
    from dataclasses import replace
    from datetime import datetime

    trade = _mock_trade(-50.0, datetime(2024, 1, 1))
    trade = replace(
        trade,
        exit_reason="stop_loss",
        pnl_gross=-50.0,
        initial_risk_ccy=50.0,
        post_exit_analysis={
            "5": {"mfe": 60.0, "mae": -10.0},  # MFE > initial_risk = false
            "10": {"mfe": 80.0, "mae": -15.0},
        },
    )

    from trading_platform.reporting.analytics import compute_exit_efficiency
    result = compute_exit_efficiency([trade])

    assert "by_exit_reason" in result
    assert "stop_loss" in result["by_exit_reason"]
    sl_analysis = result["by_exit_reason"]["stop_loss"]
    assert sl_analysis["n_trades"] == 1
    assert "false_stop_rate" in sl_analysis
    assert sl_analysis["false_stop_rate"] == 1.0


def test_compute_exit_efficiency_signal_suboptimal() -> None:
    """Test suboptimal signal exit detection."""
    # Validates: [REQ-ANALYTICS-EXIT-005] Detect suboptimal signal exits
    from dataclasses import replace
    from datetime import datetime

    trade = _mock_trade(50.0, datetime(2024, 1, 1))
    trade = replace(
        trade,
        exit_reason="signal",
        pnl_gross=50.0,
        post_exit_analysis={
            "5": {"mfe": 80.0, "mae": -5.0},  # MFE > 1.5x profit = suboptimal
            "10": {"mfe": 100.0, "mae": -10.0},
        },
    )

    from trading_platform.reporting.analytics import compute_exit_efficiency
    result = compute_exit_efficiency([trade])

    assert "by_exit_reason" in result
    assert "signal" in result["by_exit_reason"]
    sig_analysis = result["by_exit_reason"]["signal"]
    assert sig_analysis["n_trades"] == 1
    assert "suboptimal_exit_rate" in sig_analysis


def test_compute_exit_efficiency_optimal_hold_duration() -> None:
    """Test optimal hold duration analysis."""
    # Validates: [REQ-ANALYTICS-EXIT-006] Calculate optimal hold
    from dataclasses import replace
    from datetime import datetime

    trade1 = _mock_trade(50.0, datetime(2024, 1, 1))
    trade1 = replace(
        trade1,
        exit_reason="signal",
        post_exit_analysis={
            "5": {"mfe": 20.0, "mae": -5.0},
            "10": {"mfe": 40.0, "mae": -10.0},
        },
    )

    trade2 = _mock_trade(30.0, datetime(2024, 1, 3))
    trade2 = replace(
        trade2,
        exit_reason="signal",
        post_exit_analysis={
            "5": {"mfe": 10.0, "mae": -3.0},
            "10": {"mfe": 20.0, "mae": -5.0},
        },
    )

    from trading_platform.reporting.analytics import compute_exit_efficiency
    result = compute_exit_efficiency([trade1, trade2])

    assert "optimal_hold_analysis" in result
    opt_hold = result["optimal_hold_analysis"]
    assert "current_avg_pnl" in opt_hold
    assert opt_hold["current_avg_pnl"] == 40.0  # (50 + 30) / 2
    assert "if_held_5_bars" in opt_hold
    assert opt_hold["if_held_5_bars"] == 55.0  # (50+20 + 30+10) / 2
    assert "if_held_10_bars" in opt_hold
    assert opt_hold["if_held_10_bars"] == 70.0  # (50+40 + 30+20) / 2


def test_compute_exit_efficiency_no_matching_exit_reason() -> None:
    """Test exit efficiency when no trades match a specific exit reason."""
    # Validates: [REQ-ANALYTICS-EXIT-007] Handle no matching trades
    from dataclasses import replace
    from datetime import datetime

    # Create trade with "signal" exit
    trade = _mock_trade(50.0, datetime(2024, 1, 1))
    trade = replace(
        trade,
        exit_reason="signal",
        pnl_gross=50.0,
        post_exit_analysis={
            "5": {"mfe": 10.0, "mae": -5.0},
        },
    )

    from trading_platform.reporting.analytics import compute_exit_efficiency
    result = compute_exit_efficiency([trade])

    # Should have "signal" in by_exit_reason, but not "take_profit" or "stop_loss"
    assert "by_exit_reason" in result
    assert "signal" in result["by_exit_reason"]
    # No take_profit trades, so shouldn't appear (or should be empty)
    if "take_profit" in result["by_exit_reason"]:
        assert result["by_exit_reason"]["take_profit"] == {}


def test_compute_exit_efficiency_all_trades_different_exit_reasons() -> None:
    """Test exit efficiency when all trades have different exit reasons."""
    # Validates: [REQ-ANALYTICS-EXIT-008] Handle trades with no common exit reason
    from dataclasses import replace
    from datetime import datetime

    # Create 3 trades with 3 different exit reasons
    trade1 = _mock_trade(50.0, datetime(2024, 1, 1))
    trade1 = replace(
        trade1,
        exit_reason="take_profit",
        pnl_gross=50.0,
        post_exit_analysis={"5": {"mfe": 10.0, "mae": -5.0}},
    )

    trade2 = _mock_trade(-30.0, datetime(2024, 1, 2))
    trade2 = replace(
        trade2,
        exit_reason="stop_loss",
        pnl_gross=-30.0,
        initial_risk_ccy=30.0,
        post_exit_analysis={"5": {"mfe": 5.0, "mae": -10.0}},
    )

    trade3 = _mock_trade(20.0, datetime(2024, 1, 3))
    trade3 = replace(
        trade3,
        exit_reason="time_exit",
        pnl_gross=20.0,
        post_exit_analysis={"5": {"mfe": 8.0, "mae": -3.0}},
    )

    from trading_platform.reporting.analytics import compute_exit_efficiency
    result = compute_exit_efficiency([trade1, trade2, trade3])

    # Should have all three exit reasons
    assert "by_exit_reason" in result
    assert "take_profit" in result["by_exit_reason"]
    assert "stop_loss" in result["by_exit_reason"]
    assert "time_exit" in result["by_exit_reason"]

    # Each should have n_trades = 1, triggering the empty return path line 397
    assert result["by_exit_reason"]["take_profit"]["n_trades"] == 1
    assert result["by_exit_reason"]["stop_loss"]["n_trades"] == 1
    assert result["by_exit_reason"]["time_exit"]["n_trades"] == 1
