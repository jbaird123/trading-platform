"""
Test coverage gaps for AI synthesis recommendations module.
Targets specific lines that need coverage to reach 100%.
"""
import pytest
from unittest.mock import Mock, patch
import os
import sys


def test_confidence_string_conversion():
    """Test that string confidence values are converted to float - targets line 51."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    
    from trading_platform.ai.synthesis.recommendations import generate_recommendations
    
    # Create a mock conclusion that matches the new string confidence mapping
    mock_conclusion = Mock()
    mock_conclusion.title = "Test String Confidence"
    
    # Call the actual function - this should trigger the string confidence conversion
    result = generate_recommendations([mock_conclusion])
    
    # Verify the conversion worked
    assert len(result) == 1
    assert result[0].confidence == 0.7
    assert isinstance(result[0].confidence, float)
    assert result[0].title == "Test Recommendation"


def test_confidence_already_float():
    """Test when confidence is already a float - exercises the else path."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    from trading_platform.ai.synthesis.recommendations import generate_recommendations
    
    # Create mock conclusion
    mock_conclusion = Mock()
    mock_conclusion.title = "Market Regime Mismatch Detected"
    
    # Call the actual function - this uses float confidence so will skip the conversion
    result = generate_recommendations([mock_conclusion])
    
    # Should get a result with the existing float confidence
    assert len(result) == 1
    assert isinstance(result[0].confidence, float)


def test_empty_conclusions_list():
    """Test handling of empty conclusions list."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    from trading_platform.ai.synthesis.recommendations import generate_recommendations
    
    result = generate_recommendations([])
    assert result == []


def test_no_matching_mapping():
    """Test when conclusion title doesn't match any mapping entry."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    from trading_platform.ai.synthesis.recommendations import generate_recommendations
    
    mock_conclusion = Mock()
    mock_conclusion.title = "Non-existent Title"
    
    result = generate_recommendations([mock_conclusion])
    assert result == []