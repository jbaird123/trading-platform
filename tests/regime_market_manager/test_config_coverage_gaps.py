"""
Test coverage gaps in RMM Configuration module.

Targets specific missing lines in regime_market_manager/config.py to improve coverage.
"""
import pytest
from unittest.mock import patch

from trading_platform.regime_market_manager.config import validate_rmm_config, RegimeManagerConfig


def test_validate_rmm_config_non_dict():
    """Test validate_rmm_config with non-dict input. Covers line 49."""
    with pytest.raises(ValueError, match="rmm config must be an object"):
        validate_rmm_config("invalid_string")  # type: ignore[arg-type]
    
    with pytest.raises(ValueError, match="rmm config must be an object"):
        validate_rmm_config([1, 2, 3])  # type: ignore[arg-type]
    
    with pytest.raises(ValueError, match="rmm config must be an object"):
        validate_rmm_config(None)  # type: ignore[arg-type]


def test_validate_rmm_config_missing_jsonschema():
    """Test validate_rmm_config when jsonschema is not available. Covers line 52."""
    valid_config: dict[str, list[str]] = {"regimes": []}
    
    with patch('trading_platform.regime_market_manager.config.jsonschema', None):
        with pytest.raises(ValueError, match="jsonschema is required for RMM validation"):
            validate_rmm_config(valid_config)


def test_validate_rmm_config_regimes_not_list():
    """Test validate_rmm_config with invalid regimes field. Covers line 65."""
    # Test with regimes as string instead of list
    config = {"regimes": "invalid_string"}
    
    with patch('trading_platform.regime_market_manager.config.jsonschema') as mock_jsonschema:
        mock_jsonschema.validate.return_value = None  # Skip schema validation
        
        with pytest.raises(ValueError, match="regimes must be a non-empty array"):
            validate_rmm_config(config)


def test_validate_rmm_config_regimes_empty():
    """Test validate_rmm_config with empty regimes array. Covers line 65."""
    config: dict[str, list[str]] = {"regimes": []}
    
    with patch('trading_platform.regime_market_manager.config.jsonschema') as mock_jsonschema:
        mock_jsonschema.validate.return_value = None
        
        with pytest.raises(ValueError, match="regimes must be a non-empty array"):
            validate_rmm_config(config)


def test_validate_rmm_config_regime_not_dict():
    """Test validate_rmm_config with non-dict regime. Covers line 68."""
    config = {"regimes": ["invalid_regime_string"]}
    
    with patch('trading_platform.regime_market_manager.config.jsonschema') as mock_jsonschema:
        mock_jsonschema.validate.return_value = None
        
        with pytest.raises(ValueError, match="regime must be an object"):
            validate_rmm_config(config)


def test_validate_rmm_config_regime_label_not_string():
    """Test validate_rmm_config with invalid regime label. Covers line 70."""
    config = {
        "regimes": [
            {"label": 123}  # Should be string
        ]
    }
    
    with patch('trading_platform.regime_market_manager.config.jsonschema') as mock_jsonschema:
        mock_jsonschema.validate.return_value = None
        
        with pytest.raises(ValueError, match="regime.label must be a string"):
            validate_rmm_config(config)


def test_validate_rmm_config_regime_confidence_invalid():
    """Test validate_rmm_config with invalid regime confidence. Covers line 73."""
    # Test with string confidence
    config1 = {
        "regimes": [
            {
                "label": "test_regime",
                "confidence": "invalid_string"
            }
        ]
    }
    
    with patch('trading_platform.regime_market_manager.config.jsonschema') as mock_jsonschema:
        mock_jsonschema.validate.return_value = None
        
        with pytest.raises(ValueError, match="regime.confidence must be 0..1"):
            validate_rmm_config(config1)
    
    # Test with out-of-range confidence
    config2 = {
        "regimes": [
            {
                "label": "test_regime", 
                "confidence": 1.5  # Out of range [0,1]
            }
        ]
    }
    
    with patch('trading_platform.regime_market_manager.config.jsonschema') as mock_jsonschema:
        mock_jsonschema.validate.return_value = None
        
        with pytest.raises(ValueError, match="regime.confidence must be 0..1"):
            validate_rmm_config(config2)


def test_validate_rmm_config_regime_conditions_not_dict():
    """Test validate_rmm_config with invalid regime conditions. Covers line 76."""
    config = {
        "regimes": [
            {
                "label": "test_regime",
                "confidence": 0.8,
                "conditions": "invalid_string"  # Should be dict
            }
        ]
    }
    
    with patch('trading_platform.regime_market_manager.config.jsonschema') as mock_jsonschema:
        mock_jsonschema.validate.return_value = None
        
        with pytest.raises(ValueError, match="regime.conditions must be an object"):
            validate_rmm_config(config)


def test_validate_rmm_config_conditions_missing_all_of_any_of():
    """Test validate_rmm_config with conditions missing all_of/any_of. Covers line 79."""
    config = {
        "regimes": [
            {
                "label": "test_regime",
                "confidence": 0.8,
                "conditions": {
                    "invalid_field": []  # Missing all_of or any_of
                }
            }
        ]
    }
    
    with patch('trading_platform.regime_market_manager.config.jsonschema') as mock_jsonschema:
        mock_jsonschema.validate.return_value = None
        
        with pytest.raises(ValueError, match="regime.conditions requires all_of or any_of"):
            validate_rmm_config(config)


def test_validate_rmm_config_predicate_list_invalid():
    """Test validate_rmm_config with invalid predicate list. Covers line 82."""
    # Test with empty predicate list
    config1 = {
        "regimes": [
            {
                "label": "test_regime",
                "confidence": 0.8,
                "conditions": {
                    "all_of": []  # Empty array
                }
            }
        ]
    }
    
    with patch('trading_platform.regime_market_manager.config.jsonschema') as mock_jsonschema:
        mock_jsonschema.validate.return_value = None
        
        with pytest.raises(ValueError, match="predicate list must be a non-empty array"):
            validate_rmm_config(config1)
    
    # Test with non-list predicate
    config2 = {
        "regimes": [
            {
                "label": "test_regime",
                "confidence": 0.8,
                "conditions": {
                    "any_of": "invalid_string"  # Should be list
                }
            }
        ]
    }
    
    with patch('trading_platform.regime_market_manager.config.jsonschema') as mock_jsonschema:
        mock_jsonschema.validate.return_value = None
        
        with pytest.raises(ValueError, match="predicate list must be a non-empty array"):
            validate_rmm_config(config2)


def test_validate_rmm_config_valid():
    """Test validate_rmm_config with valid configuration."""
    config = {
        "regimes": [
            {
                "label": "trending",
                "confidence": 0.8,
                "conditions": {
                    "all_of": [
                        {
                            "condition": "gt",
                            "left": "ADX(14)",
                            "right": 25.0
                        }
                    ]
                }
            }
        ]
    }
    
    with patch('trading_platform.regime_market_manager.config.jsonschema') as mock_jsonschema:
        mock_jsonschema.validate.return_value = None
        
        # Should not raise any exception
        validate_rmm_config(config)


def test_regime_manager_config_creation():
    """Test RegimeManagerConfig model creation."""
    # Test with defaults
    config = RegimeManagerConfig()
    assert config.trend_indicator == "ADX(14)"
    assert config.trend_threshold_high == 25.0
    assert config.trend_threshold_low == 20.0
    assert config.slope_indicator == "EMA(200)_slope"
    assert config.slope_threshold == 0.1
    
    # Test with custom values
    config = RegimeManagerConfig(
        trend_indicator="RSI(14)",
        trend_threshold_high=30.0,
        trend_threshold_low=15.0,
        slope_indicator="SMA(50)_slope",
        slope_threshold=0.2
    )
    assert config.trend_indicator == "RSI(14)"
    assert config.trend_threshold_high == 30.0
    assert config.trend_threshold_low == 15.0
    assert config.slope_indicator == "SMA(50)_slope"
    assert config.slope_threshold == 0.2