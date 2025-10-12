"""
Tests for indicator safety classification system.

Validates that the safety registry correctly classifies indicators
and provides appropriate safety checks.
"""

import pytest
from trading_platform.strategy.indicators_registry import (
    LookAheadBiasError,
    SafetyLevel,
    get_safety_level,
    get_safety_summary,
    is_indicator_safe,
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
    """Unknown indicators should require testing."""
    # FIB used to be requires_test but is now validated after passing bias tests
    # Test with an unknown indicator instead
    assert get_safety_level("UNKNOWN_INDICATOR") == SafetyLevel.REQUIRES_TEST


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
    assert is_indicator_safe("FIB") is True  # Now validated after passing bias tests

    # Untested indicators
    assert is_indicator_safe("UNKNOWN") is False


def test_requires_bias_test() -> None:
    """Test bias test requirement check."""
    # Safe/validated don't require testing
    assert requires_bias_test("EMA") is False
    assert requires_bias_test("SWING_HIGH") is False
    assert requires_bias_test("FIB") is False  # Now validated after passing bias tests

    # Unknown requires testing
    assert requires_bias_test("UNKNOWN") is True


def test_validate_indicator_safety_for_safe_indicators() -> None:
    """Safe indicators should pass validation without error."""
    # Should not raise
    validate_indicator_safety("EMA")
    validate_indicator_safety("RSI")
    validate_indicator_safety("SWING_HIGH")


def test_validate_indicator_safety_for_untested_indicators() -> None:
    """Untested indicators should raise error."""
    # FIB is now validated, test with unknown indicator instead
    with pytest.raises(LookAheadBiasError, match="requires bias detection testing"):
        validate_indicator_safety("UNKNOWN_INDICATOR")


def test_get_safety_summary() -> None:
    """Test safety summary generation."""
    summary = get_safety_summary()

    # Should have all categories
    assert "safe" in summary
    assert "validated" in summary
    assert "requires_test" in summary

    # Check some known indicators are in correct categories
    assert "EMA" in summary["safe"]
    assert "RSI" in summary["safe"]
    assert "SWING_HIGH" in summary["validated"]
    assert "SWING_LOW" in summary["validated"]
    assert "FIB" in summary["validated"]  # Now validated after passing bias tests
    assert "CHOP" in summary["validated"]  # Now validated after passing bias tests
    assert (
        "SUPERTREND" in summary["validated"]
    )  # Now validated after passing bias tests

    # All lists should be non-empty
    assert len(summary["safe"]) > 0
    assert len(summary["validated"]) > 0
    # requires_test may be empty if all indicators are classified


def test_safety_registry_completeness() -> None:
    """
    Verify all indicators in indicators_registry.py have
    corresponding safety classifications.
    """
    from trading_platform.strategy.indicators_registry import INDICATORS

    for indicator_name in INDICATORS.keys():
        # Each indicator should have a safety classification
        safety = get_safety_level(indicator_name)

        # All registered indicators should be safe or validated
        # (FIB, CHOP, SUPERTREND are now validated after passing bias tests)
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
