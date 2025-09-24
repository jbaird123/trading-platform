# Coverage gaps for portfolio/portfolio.py
# Missing lines: 75-79, 91->94, 95, 98-104, 107-113, 118-124
from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock

import pandas as pd
from trading_platform.portfolio.portfolio import PortfolioManager


def test_portfolio_hit_daily_loss_cap_none_cap():
    """Test hit_daily_loss_cap when cap is None (lines 75-76)."""
    pm = PortfolioManager(initial_cash=1000.0)
    ts = datetime(2024, 1, 1, 10)
    
    # Test with None cap - should return False (line 76)
    result = pm.hit_daily_loss_cap(ts, None)
    assert result is False


def test_portfolio_hit_daily_loss_cap_zero_cap():
    """Test hit_daily_loss_cap when cap is <= 0 (lines 76-77)."""
    pm = PortfolioManager(initial_cash=1000.0)
    ts = datetime(2024, 1, 1, 10)
    
    # Test with zero cap - should return False (line 76)
    result = pm.hit_daily_loss_cap(ts, 0.0)
    assert result is False
    
    # Test with negative cap - should return False (line 76) 
    result = pm.hit_daily_loss_cap(ts, -100.0)
    assert result is False


def test_portfolio_hit_daily_loss_cap_with_loss():
    """Test hit_daily_loss_cap when daily loss exceeds cap (lines 78-79)."""
    pm = PortfolioManager(initial_cash=1000.0)
    
    # Create and close a losing position to generate daily PnL
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1, 9))
    pm.close_position(
        exit_price=1.0900,  # Loss of -100 pips
        exit_time=datetime(2024, 1, 1, 10),
        exit_reason="stop_loss"
    )
    
    # Check if loss cap is hit
    ts = datetime(2024, 1, 1, 11)  # Same date
    result = pm.hit_daily_loss_cap(ts, 50.0)  # Cap smaller than actual loss
    
    # Should return True when daily loss exceeds cap (lines 78-79)
    assert result is True


def test_portfolio_on_bar_no_position():
    """Test on_bar when no position exists (avoids line 92-93)."""
    pm = PortfolioManager(initial_cash=1000.0)
    
    # Create bar data
    bar = pd.Series({
        'open': 1.1000,
        'high': 1.1020,
        'low': 1.0980,
        'close': 1.1010,
        'volume': 1000
    }, name=datetime(2024, 1, 1, 10))
    
    # Call on_bar with no position - should not call _update_position_metrics
    pm.on_bar(bar, "flat")
    
    # Should complete without error
    assert pm.current_position is None


def test_portfolio_check_stop_loss_no_position():
    """Test check_stop_loss when no position exists (lines 98-100)."""
    pm = PortfolioManager(initial_cash=1000.0)
    
    # Create bar data
    bar = pd.Series({
        'open': 1.1000,
        'high': 1.1020,
        'low': 1.0980,
        'close': 1.1010,
        'volume': 1000
    })
    
    # Check stop loss with no position - should return False (line 99)
    result = pm.check_stop_loss(bar, 1.0950)
    assert result is False


def test_portfolio_check_stop_loss_invalid_price():
    """Test check_stop_loss when stop_price <= 0 (lines 98-100)."""
    pm = PortfolioManager(initial_cash=1000.0)
    
    # Create a position
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1, 9))
    
    # Create bar data
    bar = pd.Series({
        'open': 1.1000,
        'high': 1.1020,
        'low': 1.0980,
        'close': 1.1010,
        'volume': 1000
    })
    
    # Check stop loss with invalid price - should return False (line 99)
    result = pm.check_stop_loss(bar, 0.0)
    assert result is False
    
    result = pm.check_stop_loss(bar, -1.0)
    assert result is False


def test_portfolio_check_stop_loss_long_position():
    """Test check_stop_loss for long position (lines 101-102)."""
    pm = PortfolioManager(initial_cash=1000.0)
    
    # Create a long position
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1, 9))
    
    # Create bar data where low hits stop loss
    bar = pd.Series({
        'open': 1.1000,
        'high': 1.1020,
        'low': 1.0950,  # Below stop loss
        'close': 1.1010,
        'volume': 1000
    })
    
    # Check stop loss - should return True (line 102)
    result = pm.check_stop_loss(bar, 1.0960)
    assert result is True


def test_portfolio_check_stop_loss_short_position():
    """Test check_stop_loss for short position (lines 103-104)."""
    pm = PortfolioManager(initial_cash=1000.0)
    
    # Create a short position
    pm.create_new_position("EURUSD", "short", 1.1000, 1.0, datetime(2024, 1, 1, 9))
    
    # Create bar data where high hits stop loss
    bar = pd.Series({
        'open': 1.1000,
        'high': 1.1050,  # Above stop loss
        'low': 1.0980,
        'close': 1.1010,
        'volume': 1000
    })
    
    # Check stop loss - should return True (line 104)
    result = pm.check_stop_loss(bar, 1.1040)
    assert result is True


def test_portfolio_check_take_profit_no_position():
    """Test check_take_profit when no position exists (lines 107-109)."""
    pm = PortfolioManager(initial_cash=1000.0)
    
    # Create bar data
    bar = pd.Series({
        'open': 1.1000,
        'high': 1.1020,
        'low': 1.0980,
        'close': 1.1010,
        'volume': 1000
    })
    
    # Check take profit with no position - should return False (line 108)
    result = pm.check_take_profit(bar, 1.1050)
    assert result is False


def test_portfolio_check_take_profit_invalid_price():
    """Test check_take_profit when profit_price <= 0 (lines 107-109)."""
    pm = PortfolioManager(initial_cash=1000.0)
    
    # Create a position
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1, 9))
    
    # Create bar data
    bar = pd.Series({
        'open': 1.1000,
        'high': 1.1020,
        'low': 1.0980,
        'close': 1.1010,
        'volume': 1000
    })
    
    # Check take profit with invalid price - should return False (line 108)
    result = pm.check_take_profit(bar, 0.0)
    assert result is False


def test_portfolio_check_take_profit_long_position():
    """Test check_take_profit for long position (lines 111-112)."""
    pm = PortfolioManager(initial_cash=1000.0)
    
    # Create a long position
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1, 9))
    
    # Create bar data where high hits take profit
    bar = pd.Series({
        'open': 1.1000,
        'high': 1.1080,  # Above take profit
        'low': 1.0980,
        'close': 1.1010,
        'volume': 1000
    })
    
    # Check take profit - should return True (line 112)
    result = pm.check_take_profit(bar, 1.1070)
    assert result is True


def test_portfolio_check_take_profit_short_position():
    """Test check_take_profit for short position (lines 113-114)."""
    pm = PortfolioManager(initial_cash=1000.0)
    
    # Create a short position
    pm.create_new_position("EURUSD", "short", 1.1000, 1.0, datetime(2024, 1, 1, 9))
    
    # Create bar data where low hits take profit
    bar = pd.Series({
        'open': 1.1000,
        'high': 1.1020,
        'low': 1.0920,  # Below take profit
        'close': 1.1010,
        'volume': 1000
    })
    
    # Check take profit - should return True (line 114)
    result = pm.check_take_profit(bar, 1.0930)
    assert result is True


def test_portfolio_handle_signal_change_no_flip():
    """Test _handle_signal_change when allow_flip_on_bar is False (lines 118-124)."""
    pm = PortfolioManager(initial_cash=1000.0)
    
    # Create a long position
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1, 9))
    
    # Create bar data
    bar = pd.Series({
        'open': 1.1000,
        'high': 1.1020,
        'low': 1.0980,
        'close': 1.1010,
        'volume': 1000
    }, name=datetime(2024, 1, 1, 10))
    
    # Call on_bar with different signal and no flip allowed
    pm.on_bar(bar, "short", allow_flip_on_bar=False)
    
    # Position should be closed but no new position created (lines 123-124)
    assert pm.current_position is None
    assert len(pm.trades) == 1
    assert pm.trades[0].exit_reason == "signal"