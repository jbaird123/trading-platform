# Coverage gaps for risk_manager/rem.py  
# Missing lines: 56, 61-63, 74, 76, 79
from __future__ import annotations

import tempfile
from io import StringIO

from trading_platform.risk_manager.rem import RiskExitManager


def test_rem_distance_invalid_rule_type():
    """Test _distance when rule is not a dict (line 56)."""
    # Create minimal config
    config = StringIO("""
    stop_loss: {}
    take_profit: {}
    """)
    rem = RiskExitManager(config)
    
    # Test with None rule - should return None (line 56)
    result = rem._distance(None, 1.0)
    assert result is None
    
    # Test with string rule - should return None (line 56) 
    result = rem._distance("invalid", 1.0)  # type: ignore[arg-type]
    assert result is None


def test_rem_distance_atr_multiple_no_atr():
    """Test _distance with atr_multiple but no atr value (lines 61-63)."""
    config = StringIO("""
    stop_loss: {}
    take_profit: {}
    """)
    rem = RiskExitManager(config)
    
    # Test atr_multiple with None atr - should return None (line 63)
    rule = {"atr_multiple": 2.0}
    result = rem._distance(rule, None)
    assert result is None


def test_rem_distance_atr_multiple_with_atr():
    """Test _distance with atr_multiple and valid atr (lines 61-62)."""
    config = StringIO("""
    stop_loss: {}
    take_profit: {}
    """)
    rem = RiskExitManager(config)
    
    # Test atr_multiple with valid atr - should calculate properly (line 62)
    rule = {"atr_multiple": 2.0}
    result = rem._distance(rule, 0.001)
    expected = 2.0 * 0.001
    assert result == expected


def test_rem_level_price_invalid_rule_type():
    """Test _level_price when rule is not a dict (line 74)."""
    config = StringIO("""
    stop_loss: {}
    take_profit: {}
    """)
    rem = RiskExitManager(config)
    
    # Test with None rule - should return None (line 74)
    result = rem._level_price("long", 1.1000, None, None)
    assert result is None
    
    # Test with invalid rule type - should return None (line 74)
    result = rem._level_price("long", 1.1000, "invalid", None)  # type: ignore[arg-type]
    assert result is None


def test_rem_level_price_distance_none():
    """Test _level_price when distance calculation returns None (lines 76, 79)."""
    config = StringIO("""
    stop_loss: {}
    take_profit: {}
    """)
    rem = RiskExitManager(config)
    
    # Test with rule that has no valid distance fields - should return None (line 79)
    rule = {"invalid_field": "value"}
    result = rem._level_price("long", 1.1000, rule, None)
    assert result is None


def test_rem_level_price_absolute_price():
    """Test _level_price with absolute_price rule (line 76)."""
    config = StringIO("""
    stop_loss: {}
    take_profit: {}
    """)
    rem = RiskExitManager(config)
    
    # Test absolute_price rule - should return the absolute price (line 76)
    rule = {"absolute_price": 1.0950}
    result = rem._level_price("long", 1.1000, rule, None)
    assert result == 1.0950