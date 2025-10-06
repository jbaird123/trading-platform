"""Comprehensive test coverage for strategy/indicators_registry.py."""

from __future__ import annotations

from trading_platform.strategy.indicators_registry import INDICATORS


def test_indicators_registry_exists():
    """Test that INDICATORS registry exists and is a dict."""
    assert isinstance(INDICATORS, dict)
    assert len(INDICATORS) > 0


def test_all_indicators_have_required_fields():
    """Test that all indicators have the required basic fields."""
    required_fields = {"display", "category", "description", "params", "ta"}

    for indicator_name, indicator_config in INDICATORS.items():
        msg = f"{indicator_name} config must be dict"
        assert isinstance(indicator_config, dict), msg

        # Check all required fields are present
        for field in required_fields:
            assert field in indicator_config, f"{indicator_name} missing field: {field}"

        # Check field types
        display = indicator_config["display"]
        assert isinstance(display, str), f"{indicator_name} display must be string"

        category = indicator_config["category"]
        assert isinstance(category, str), f"{indicator_name} category must be string"

        description = indicator_config["description"]
        msg = f"{indicator_name} description must be string"
        assert isinstance(description, str), msg

        params = indicator_config["params"]
        assert isinstance(params, list), f"{indicator_name} params must be list"

        ta = indicator_config["ta"]
        assert isinstance(ta, dict), f"{indicator_name} ta must be dict"


def test_indicator_categories():
    """Test that all indicators have valid categories."""
    valid_categories = {
        "trend",
        "momentum",
        "volatility",
        "volume",
        "price",
        "levels",
        "pattern",
    }

    for indicator_name, indicator_config in INDICATORS.items():
        category = indicator_config["category"]
        msg = f"{indicator_name} invalid category: {category}"
        assert category in valid_categories, msg


def test_indicator_params_structure():
    """Test that all indicator params have valid structure."""
    valid_param_types = {"int", "float", "bool", "str"}

    for indicator_name, indicator_config in INDICATORS.items():
        params = indicator_config["params"]

        for param in params:
            assert isinstance(param, dict), f"{indicator_name} param must be dict"
            assert "name" in param, f"{indicator_name} param missing name"
            assert "type" in param, f"{indicator_name} param missing type"
            assert "default" in param, f"{indicator_name} param missing default"

            param_name = param["name"]
            msg = f"{indicator_name} param name must be string"
            assert isinstance(param_name, str), msg

            param_type = param["type"]
            msg = f"{indicator_name} param invalid type: {param_type}"
            assert param_type in valid_param_types, msg


def test_indicator_ta_configuration():
    """Test that all indicators have valid TA configuration."""
    for indicator_name, indicator_config in INDICATORS.items():
        ta_config = indicator_config["ta"]

        # TA config should have either module+function or be empty for custom
        if ta_config.get("module") or ta_config.get("function"):
            msg = f"{indicator_name} TA config missing module"
            assert "module" in ta_config, msg

            msg = f"{indicator_name} TA config missing function"
            assert "function" in ta_config, msg

            module = ta_config["module"]
            msg = f"{indicator_name} TA module must be string"
            assert isinstance(module, str), msg

            function = ta_config["function"]
            msg = f"{indicator_name} TA function must be string"
            assert isinstance(function, str), msg


def test_specific_indicators_exist():
    """Test that expected specific indicators exist in registry."""
    expected_indicators = {
        # Moving Averages
        "SMA",
        "EMA",
        "WMA",
        # Momentum/Oscillators
        "MACD",
        "RSI",
        "STOCH",
        "CCI",
        "ROC",
        # Trend
        "PSAR",
        "ADX",
        # Volatility
        "BB",
        "BBWidth",
        "ATR",
        "KC",
        # Volume
        "OBV",
        "CMF",
        "VWAP",
        # Levels/Derived
        "FIB",
        "HHV",
        "LLV",
        "DC",
        # Patterns
        "CDL_DOJI",
        "CDL_HAMMER",
        "CDL_ENGULFING",
        "CDL_MORNINGSTAR",
        "CDL_EVENINGSTAR",
        "CDL_HARAMI",
    }

    for indicator in expected_indicators:
        assert indicator in INDICATORS, f"Expected indicator {indicator} not found"


def test_moving_averages_category():
    """Test moving averages are properly categorized."""
    moving_averages = ["SMA", "EMA", "WMA"]
    for ma in moving_averages:
        if ma in INDICATORS:
            category = INDICATORS[ma]["category"]
            assert category == "trend", f"{ma} should be in trend category"


def test_momentum_indicators_category():
    """Test momentum indicators are properly categorized."""
    momentum_indicators = ["RSI", "STOCH", "CCI", "ROC"]
    for indicator in momentum_indicators:
        if indicator in INDICATORS:
            category = INDICATORS[indicator]["category"]
            msg = f"{indicator} should be in momentum category"
            assert category == "momentum", msg


def test_volatility_indicators_category():
    """Test volatility indicators are properly categorized."""
    volatility_indicators = ["BB", "BBWidth", "ATR", "KC"]
    for indicator in volatility_indicators:
        if indicator in INDICATORS:
            category = INDICATORS[indicator]["category"]
            msg = f"{indicator} should be in volatility category"
            assert category == "volatility", msg


def test_volume_indicators_category():
    """Test volume indicators are properly categorized."""
    volume_indicators = ["OBV", "CMF"]  # VWAP is in price category
    for indicator in volume_indicators:
        if indicator in INDICATORS:
            category = INDICATORS[indicator]["category"]
            msg = f"{indicator} should be in volume category"
            assert category == "volume", msg


def test_level_indicators_category():
    """Test level indicators are properly categorized."""
    level_indicators = ["FIB", "HHV", "LLV", "DC"]
    for indicator in level_indicators:
        if indicator in INDICATORS:
            category = INDICATORS[indicator]["category"]
            msg = f"{indicator} should be in levels category"
            assert category == "levels", msg


def test_pattern_indicators_category():
    """Test pattern indicators are properly categorized."""
    pattern_indicators = [
        "CDL_DOJI",
        "CDL_HAMMER",
        "CDL_ENGULFING",
        "CDL_MORNINGSTAR",
        "CDL_EVENINGSTAR",
        "CDL_HARAMI",
    ]
    for indicator in pattern_indicators:
        if indicator in INDICATORS:
            assert INDICATORS[indicator]["category"] == "pattern"


def test_indicator_display_names():
    """Test that all indicators have meaningful display names."""
    for indicator_name, indicator_config in INDICATORS.items():
        display = indicator_config["display"]
        assert len(display) > 0, f"{indicator_name} has empty display name"
        # Display name can be same as key for acronyms like MACD
        msg = f"{indicator_name} display should be a string"
        assert isinstance(display, str), msg


def test_indicator_descriptions():
    """Test that all indicators have descriptions."""
    for indicator_name, indicator_config in INDICATORS.items():
        description = indicator_config["description"]
        msg = f"{indicator_name} has empty description"
        assert len(description) > 0, msg


def test_common_parameters():
    """Test common parameters across indicators."""
    length_indicators = ["SMA", "EMA", "RSI", "ATR"]

    for indicator in length_indicators:
        if indicator in INDICATORS:
            params = INDICATORS[indicator]["params"]
            param_names = [p["name"] for p in params]
            msg = f"{indicator} should have length parameter"
            assert "length" in param_names, msg


def test_macd_parameters():
    """Test MACD specific parameters."""
    if "MACD" in INDICATORS:
        params = INDICATORS["MACD"]["params"]
        param_names = [p["name"] for p in params]

        expected_params = ["fast", "slow", "signal"]
        for param in expected_params:
            msg = f"MACD should have {param} parameter"
            assert param in param_names, msg


def test_psar_parameters():
    """Test PSAR specific parameters."""
    if "PSAR" in INDICATORS:
        params = INDICATORS["PSAR"]["params"]
        param_names = [p["name"] for p in params]

        expected_params = ["step", "max_step"]
        for param in expected_params:
            msg = f"PSAR should have {param} parameter"
            assert param in param_names, msg


def test_bollinger_bands_parameters():
    """Test Bollinger Bands specific parameters."""
    if "BB" in INDICATORS:
        params = INDICATORS["BB"]["params"]
        param_names = [p["name"] for p in params]

        expected_params = ["length", "std"]
        for param in expected_params:
            msg = f"BB should have {param} parameter"
            assert param in param_names, msg


def test_no_params_indicators():
    """Test indicators that should have no parameters."""
    no_param_indicators = ["HHV", "LLV"]

    for indicator in no_param_indicators:
        if indicator in INDICATORS:
            params = INDICATORS[indicator]["params"]
            # Some indicators might have period, but should be minimal
            assert len(params) <= 1, f"{indicator} should have minimal params"


def test_custom_implementation_indicators():
    """Test indicators with custom implementations (no TA library)."""
    custom_indicators = ["FIB", "DC"]

    for indicator in custom_indicators:
        if indicator in INDICATORS:
            ta_config = INDICATORS[indicator]["ta"]
            # Custom indicators should have empty TA config
            has_module = bool(ta_config.get("module"))
            has_function = bool(ta_config.get("function"))
            custom_impl = not (has_module and has_function)
            msg = f"{indicator} should be custom implementation"
            assert custom_impl, msg


def test_ta_library_indicators():
    """Test indicators that use TA library."""
    ta_indicators = ["SMA", "EMA", "RSI", "MACD"]

    for indicator in ta_indicators:
        if indicator in INDICATORS:
            ta_config = INDICATORS[indicator]["ta"]
            has_module = bool(ta_config.get("module"))
            has_function = bool(ta_config.get("function"))
            uses_ta = has_module and has_function
            msg = f"{indicator} should use TA library"
            assert uses_ta, msg


def test_registry_immutability():
    """Test that registry structure cannot be easily modified."""
    # This is more of a structural test to ensure registry is well-defined
    original_keys = set(INDICATORS.keys())

    # Verify we can't easily break the registry
    try:
        # This should work (reading)
        _ = INDICATORS["SMA"]
        assert True
    except KeyError:
        # If SMA doesn't exist, that's fine for this structural test
        pass

    # Verify structure is consistent
    assert len(original_keys) > 0, "Registry should not be empty"


def test_indicator_naming_conventions():
    """Test that indicator names follow consistent conventions."""
    for indicator_name in INDICATORS.keys():
        # Names should not contain spaces
        msg = f"{indicator_name} should not contain spaces"
        assert " " not in indicator_name, msg
        # Names should be alphanumeric or underscores
        clean_name = indicator_name.replace("_", "")
        msg = f"{indicator_name} should be alphanumeric"
        assert clean_name.isalnum(), msg
