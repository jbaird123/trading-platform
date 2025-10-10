"""
Tests for indicator safety classification system.

Validates that the safety registry correctly classifies indicators
and provides appropriate safety checks.
"""

import pytest
from trading_platform.strategy.indicator_safety import (
    LookAheadBiasError,
    SafetyLevel,
    get_safety_level,
    get_safety_summary,
    is_indicator_safe,
    is_lookahead_allowed,
    requires_bias_test,
    validate_indicator_safety,
)


def test_get_safety_level_for_safe_indicators() -> None:
    """Built-in pandas-ta indicators should be classified as safe."""
    assert get_safety_level("EMA") == SafetyLevel.SAFE
    assert get_safety_level("RSI") == SafetyLevel.SAFE
    assert get_safety_level("ATR") == SafetyLevel.SAFE
    assert get_safety_level("ADX") == SafetyLevel.SAFE
    assert get_safety_level("MACD") == SafetyLevel.SAFE


def test_get_safety_level_for_validated_indicators() -> None:
    """Custom reviewed indicators should be classified as validated."""
    assert get_safety_level("SWING_HIGH") == SafetyLevel.VALIDATED
    assert get_safety_level("SWING_LOW") == SafetyLevel.VALIDATED
    assert get_safety_level("HHV") == SafetyLevel.VALIDATED
    assert get_safety_level("LLV") == SafetyLevel.VALIDATED
    assert get_safety_level("EMASlope") == SafetyLevel.VALIDATED


def test_get_safety_level_for_requires_test_indicators() -> None:
    """Unimplemented indicators should require testing."""
    assert get_safety_level("FIB") == SafetyLevel.REQUIRES_TEST


def test_get_safety_level_for_unknown_indicators() -> None:
    """Unknown indicators should default to requires_test."""
    assert get_safety_level("UNKNOWN_INDICATOR") == SafetyLevel.REQUIRES_TEST


def test_is_indicator_safe() -> None:
    """Test safe indicator check."""
    # Safe indicators
    assert is_indicator_safe("EMA") is True
    assert is_indicator_safe("RSI") is True

    # Validated indicators (also considered safe)
    assert is_indicator_safe("SWING_HIGH") is True

    # Untested indicators
    assert is_indicator_safe("FIB") is False
    assert is_indicator_safe("UNKNOWN") is False


def test_requires_bias_test() -> None:
    """Test bias test requirement check."""
    # Safe/validated don't require testing
    assert requires_bias_test("EMA") is False
    assert requires_bias_test("SWING_HIGH") is False

    # Unknown requires testing
    assert requires_bias_test("FIB") is True
    assert requires_bias_test("UNKNOWN") is True


def test_is_lookahead_allowed() -> None:
    """Test lookahead permission check."""
    # Regular indicators don't allow lookahead
    assert is_lookahead_allowed("EMA") is False
    assert is_lookahead_allowed("SWING_HIGH") is False

    # No indicators currently allow lookahead
    assert is_lookahead_allowed("UNKNOWN") is False


def test_validate_indicator_safety_for_safe_indicators() -> None:
    """Safe indicators should pass validation without error."""
    # Should not raise
    validate_indicator_safety("EMA")
    validate_indicator_safety("RSI")
    validate_indicator_safety("SWING_HIGH")


def test_validate_indicator_safety_for_untested_indicators() -> None:
    """Untested indicators should raise error."""
    with pytest.raises(LookAheadBiasError, match="requires bias detection testing"):
        validate_indicator_safety("FIB")

    with pytest.raises(LookAheadBiasError, match="requires bias detection testing"):
        validate_indicator_safety("UNKNOWN_INDICATOR")


def test_get_safety_summary() -> None:
    """Test safety summary generation."""
    summary = get_safety_summary()

    # Should have all categories
    assert "safe" in summary
    assert "validated" in summary
    assert "requires_test" in summary
    assert "allow_lookahead" in summary

    # Check some known indicators are in correct categories
    assert "EMA" in summary["safe"]
    assert "RSI" in summary["safe"]
    assert "SWING_HIGH" in summary["validated"]
    assert "SWING_LOW" in summary["validated"]
    assert "FIB" in summary["requires_test"]

    # All lists should be non-empty except possibly allow_lookahead
    assert len(summary["safe"]) > 0
    assert len(summary["validated"]) > 0
    assert len(summary["requires_test"]) > 0


def test_safety_registry_completeness() -> None:
    """
    Verify all indicators in indicators_registry.py have
    corresponding safety classifications.
    """
    from trading_platform.strategy.indicators_registry import INDICATORS

    for indicator_name in INDICATORS.keys():
        # Each indicator should have a safety classification
        safety = get_safety_level(indicator_name)

        # Should not default to requires_test for known indicators
        # (except FIB which is explicitly requires_test)
        if indicator_name != "FIB":
            assert safety in (
                SafetyLevel.SAFE,
                SafetyLevel.VALIDATED,
            ), f"{indicator_name} has no explicit safety classification"


def test_safety_metadata_in_registry() -> None:
    """
    Verify all indicators in indicators_registry.py have
    the 'safety' metadata field.
    """
    from trading_platform.strategy.indicators_registry import INDICATORS

    for indicator_name, metadata in INDICATORS.items():
        # Each indicator should have 'safety' field in metadata
        assert (
            "safety" in metadata
        ), f"{indicator_name} missing 'safety' field in registry"

        # Safety value should match the classification
        expected_safety = get_safety_level(indicator_name).value
        actual_safety = metadata["safety"]

        assert actual_safety == expected_safety, (
            f"{indicator_name}: registry safety='{actual_safety}' "
            f"but classification='{expected_safety}'"
        )


def test_safety_level_enum_values() -> None:
    """Test SafetyLevel enum has expected values."""
    assert SafetyLevel.SAFE.value == "safe"
    assert SafetyLevel.VALIDATED.value == "validated"
    assert SafetyLevel.REQUIRES_TEST.value == "requires_test"
    assert SafetyLevel.ALLOW_LOOKAHEAD.value == "allow_lookahead"
