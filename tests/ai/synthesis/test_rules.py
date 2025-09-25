# --- Imports ---
from typing import Any, Dict

from trading_platform.ai.synthesis.rules import (
    DataQualityImpactRule,
    DiagnosticConclusion,
    InefficientExitsRule,
    LowWinRateHighTradesRule,
    MarketRegimeMismatchRule,
    SignalPersistenceRule,
    StrategyParameterOptimizationOpportunityRule,
    get_all_rules,
)


# --- Tests for SignalPersistenceRule ---
def test_signal_persistence_rule_triggered():
    rule = SignalPersistenceRule(persistence_threshold=0.8)
    analysis_data = {"signal_quality_analysis": {"signal_persistence_pct": 0.85}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert conclusion.title == "Signal Persistence Detected"
    assert "persistent 85% of the time" in conclusion.summary
    assert conclusion.evidence["signal_persistence_pct"] == 0.85


def test_signal_persistence_rule_not_triggered():
    rule = SignalPersistenceRule(persistence_threshold=0.8)
    analysis_data = {"signal_quality_analysis": {"signal_persistence_pct": 0.5}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


# --- Tests for StrategyParameterOptimizationOpportunityRule ---
def test_strategy_param_optimization_rule_triggered():
    rule = StrategyParameterOptimizationOpportunityRule()
    analysis_data = {"strategy_params": {"fast": None, "slow": 26}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert conclusion.title == "Strategy Parameter Optimization Opportunity"
    assert "unset (None)" in conclusion.summary
    assert conclusion.evidence["none_params"] == {"fast": None}


def test_strategy_param_optimization_rule_not_triggered():
    rule = StrategyParameterOptimizationOpportunityRule()
    analysis_data = {"strategy_params": {"fast": 10, "slow": 30}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_strategy_param_optimization_rule_partial():
    rule = StrategyParameterOptimizationOpportunityRule()
    analysis_data = {"strategy_params": {"fast": None, "slow": 30}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert "unset (None)" in conclusion.summary
    assert conclusion.evidence["none_params"] == {"fast": None}


def test_inefficient_exits_rule_triggered_by_trades():
    rule = InefficientExitsRule()
    trades = [
        {"mfe_currency": 12.0, "mae_currency": 5.0},
        {"mfe_currency": 8.0, "mae_currency": 15.0},
        {"mfe_currency": 3.0, "mae_currency": 2.0},
    ]
    analysis_data = {"trades": trades}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert conclusion.title == "Inefficient Exits Detected (Trade Analysis)"
    assert "1 trades had MFE > $10.0" in conclusion.summary
    assert "1 trades had MAE > $10.0" in conclusion.summary
    assert conclusion.evidence["high_mfe_trades"] == 1
    assert conclusion.evidence["high_mae_trades"] == 1


# --- Tests for LowWinRateHighTradesRule ---
def test_low_win_rate_high_trades_rule_triggered():
    rule = LowWinRateHighTradesRule(win_rate_threshold=0.55, n_trades_threshold=100)
    analysis_data = {"backtest_metrics": {"n_trades": 150, "win_rate": 0.50}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert conclusion.title == "Low Win Rate with High Trade Count"
    assert "150 trades with a low win rate (50.00%)" in conclusion.summary
    assert conclusion.evidence == {
        "n_trades": 150,
        "win_rate": 0.50,
        "thresholds": {"n_trades": 100, "win_rate": 0.55},
    }


def test_low_win_rate_high_trades_rule_not_triggered_low_trades():
    rule = LowWinRateHighTradesRule(win_rate_threshold=0.55, n_trades_threshold=100)
    analysis_data: dict = {"backtest_metrics": {"n_trades": 80, "win_rate": 0.50}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_low_win_rate_high_trades_rule_not_triggered_high_win_rate():
    rule = LowWinRateHighTradesRule(win_rate_threshold=0.55, n_trades_threshold=100)
    analysis_data: dict = {"backtest_metrics": {"n_trades": 150, "win_rate": 0.60}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_low_win_rate_high_trades_rule_missing_key():
    """Rule should return None when analysis_data missing required keys."""
    analysis_data: Dict[str, Any] = {}
    rule = LowWinRateHighTradesRule()
    result = rule.evaluate(analysis_data)
    assert result is None


def test_market_regime_mismatch_rule_missing_key():
    """Rule should return None when analysis_data missing required keys."""
    analysis_data: Dict[str, Any] = {}
    rule = MarketRegimeMismatchRule()
    result = rule.evaluate(analysis_data)
    assert result is None


def test_data_quality_impact_rule_missing_key():
    """Rule should return None when analysis_data missing required keys."""
    analysis_data: Dict[str, Any] = {}
    rule = DataQualityImpactRule()
    result = rule.evaluate(analysis_data)
    assert result is None


# --- Tests for DiagnosticConclusion ---


def test_diagnostic_conclusion_init():
    title = "Test Title"
    summary = "Test Summary"
    evidence = {"key": "value"}
    conclusion = DiagnosticConclusion(title, summary, evidence)
    assert conclusion.title == title
    assert conclusion.summary == summary
    assert conclusion.evidence == evidence


def test_diagnostic_conclusion_to_dict():
    title = "Test Title"
    summary = "Test Summary"
    evidence = {"key": "value"}
    conclusion = DiagnosticConclusion(title, summary, evidence)
    expected_dict = {"title": title, "summary": summary, "evidence": evidence}
    assert conclusion.to_dict() == expected_dict


# --- Tests for InefficientExitsRule ---


def test_inefficient_exits_rule_triggered():
    rule = InefficientExitsRule()
    analysis_data: dict = {"model_analysis": {"avg_pnl_left_on_table_at_tp": 15.50}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert conclusion.title == "Inefficient Take-Profit Exits Detected"
    assert "$15.50 of potential profit was left on the table" in conclusion.summary
    assert conclusion.evidence == {
        "avg_pnl_left_on_table_at_tp": 15.50,
        "threshold": 10.0,
    }


def test_inefficient_exits_rule_not_triggered():
    rule = InefficientExitsRule()
    analysis_data: dict = {"model_analysis": {"avg_pnl_left_on_table_at_tp": 5.0}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_inefficient_exits_rule_missing_model_analysis():
    rule = InefficientExitsRule()
    analysis_data: dict = {}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_inefficient_exits_rule_missing_pnl_metric():
    rule = InefficientExitsRule()
    analysis_data: dict = {"model_analysis": {"some_other_metric": 100}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


# --- Tests for get_all_rules ---


def test_get_all_rules():
    rules = get_all_rules()
    assert isinstance(rules, list)
    # Updated rule count after removals
    assert len(rules) == 6
    assert any(isinstance(rule, InefficientExitsRule) for rule in rules)


# --- Additional tests to cover missing lines ---


def test_base_diagnostic_rule_abstract_method():
    """
    Tests that the BaseDiagnosticRule abstract method raises NotImplementedError.
    This covers line 38.
    """
    from trading_platform.ai.synthesis.rules import BaseDiagnosticRule

    # Create a concrete class that doesn't implement evaluate
    class TestRule(BaseDiagnosticRule):
        pass

    # Should not be able to instantiate due to abstract method
    try:
        rule = TestRule()  # type: ignore[abstract]
        # If we somehow get here, calling evaluate should raise NotImplementedError
        rule.evaluate({})
        assert False, "Should have raised NotImplementedError"
    except TypeError:
        # Expected: Can't instantiate abstract class
        pass


def test_inefficient_exits_rule_with_trades_above_threshold():
    """
    Tests InefficientExitsRule when trades exceed MFE/MAE thresholds.
    This covers lines 86->104.
    """
    rule = InefficientExitsRule()
    analysis_data = {
        "trades": [
            {"mfe_currency": 15.0, "mae_currency": 5.0},  # High MFE
            {"mfe_currency": 8.0, "mae_currency": 12.0},  # High MAE
            {"mfe_currency": 5.0, "mae_currency": 6.0},  # Normal
            {"mfe_currency": 20.0, "mae_currency": 15.0},  # Both high
        ]
    }

    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert "Inefficient Exits Detected (Trade Analysis)" in conclusion.title
    assert "2 trades had MFE > $10.0" in conclusion.summary
    assert "2 trades had MAE > $10.0" in conclusion.summary
    assert conclusion.evidence["high_mfe_trades"] == 2
    assert conclusion.evidence["high_mae_trades"] == 2
    assert conclusion.evidence["threshold"] == 10.0


def test_strategy_parameter_optimization_rule_with_none_params():
    """
    Tests StrategyParameterOptimizationOpportunityRule with None parameters.
    This covers line 171.
    """
    rule = StrategyParameterOptimizationOpportunityRule()
    analysis_data = {
        "strategy_params": {
            "param1": 10,
            "param2": None,
            "param3": 20,
            "param4": None,
        }
    }

    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert "Strategy Parameter Optimization Opportunity" in conclusion.title
    assert "param2" in conclusion.summary
    assert "param4" in conclusion.summary
    assert "unset (None)" in conclusion.summary
    assert conclusion.evidence["none_params"] == {"param2": None, "param4": None}


def test_strategy_parameter_optimization_rule_empty_params():
    """Test StrategyParameterOptimizationOpportunityRule empty params - line 171."""
    rule = StrategyParameterOptimizationOpportunityRule()
    analysis_data: dict = {"strategy_params": {}}  # Empty params dict

    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_inefficient_exits_rule_no_inefficient_trades():
    """Test InefficientExitsRule when no trades exceed thresholds - branch 86->104."""
    rule = InefficientExitsRule()
    analysis_data = {
        "trades": [
            {"mfe_currency": 5.0, "mae_currency": 3.0},  # Low MFE and MAE
            {"mfe_currency": 8.0, "mae_currency": 7.0},  # Still below threshold
            {"mfe_currency": 2.0, "mae_currency": 4.0},  # All below 10.0 threshold
        ]
    }

    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None  # No inefficient trades found


def test_base_diagnostic_rule_pass_statement():
    """Test the pass statement in BaseDiagnosticRule.evaluate - covers line 38."""
    from trading_platform.ai.synthesis.rules import BaseDiagnosticRule
    
    # Create a minimal concrete implementation that explicitly calls the abstract method
    class TestRule(BaseDiagnosticRule):
        def evaluate(self, analysis_data):
            # Directly invoke the abstract method implementation to hit the pass statement
            return BaseDiagnosticRule.evaluate(self, analysis_data)
    
    rule = TestRule()
    # The base class evaluate method just has 'pass', so returns None
    result = rule.evaluate({})
    assert result is None
def test_data_quality_impact_rule_triggered():
    """
    Tests DataQualityImpactRule when both quality score and win rate are low.
    This covers lines 232-255.
    """
    rule = DataQualityImpactRule(quality_threshold=0.7, perf_threshold=0.0)
    analysis_data = {
        "data_quality": {"quality_score": 0.6},
        "backtest_metrics": {"win_rate": -0.1},  # Below perf_threshold of 0.0
    }

    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert "Data Quality Impact Detected" in conclusion.title
    assert "Data quality score is low (0.60)" in conclusion.summary
    assert "win rate is also low (-10.00%)" in conclusion.summary
    assert conclusion.evidence["quality_score"] == 0.6
    assert conclusion.evidence["win_rate"] == -0.1


def test_data_quality_impact_rule_high_quality_score():
    """
    Tests DataQualityImpactRule when quality score is high (should not trigger).
    """
    rule = DataQualityImpactRule(quality_threshold=0.7, perf_threshold=0.0)
    analysis_data = {
        "data_quality": {"quality_score": 0.8},  # Above quality_threshold
        "backtest_metrics": {"win_rate": -0.1},
    }

    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_data_quality_impact_rule_high_win_rate():
    """
    Tests DataQualityImpactRule when win rate is high (should not trigger).
    """
    rule = DataQualityImpactRule(quality_threshold=0.7, perf_threshold=0.0)
    analysis_data = {
        "data_quality": {"quality_score": 0.6},  # Below quality_threshold
        "backtest_metrics": {"win_rate": 0.1},  # Above perf_threshold
    }

    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_market_regime_mismatch_rule_triggered():
    """
    Tests MarketRegimeMismatchRule when regimes underperform.
    This covers lines 281-286.
    """
    rule = MarketRegimeMismatchRule(min_trades=5, win_rate_threshold=0.4)
    analysis_data = {
        "regimes": {
            "trending_up": {"n_trades": 10, "win_rate": 0.3},  # Low win rate
            "trending_down": {"n_trades": 8, "win_rate": 0.5},  # Good win rate
            "sideways": {"n_trades": 3, "win_rate": 0.2},  # Too few trades
        }
    }

    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert "Market Regime Mismatch Detected" in conclusion.title
    assert "trending_up" in conclusion.summary
    assert "trending_down" not in conclusion.summary  # Should not be in mismatches
    assert "sideways" not in conclusion.summary  # Too few trades

    mismatches = conclusion.evidence["regime_mismatches"]
    assert "trending_up" in mismatches
    assert mismatches["trending_up"]["n_trades"] == 10
    assert mismatches["trending_up"]["win_rate"] == 0.3


def test_market_regime_mismatch_rule_no_regimes():
    """
    Tests MarketRegimeMismatchRule with no regime data.
    """
    rule = MarketRegimeMismatchRule()
    analysis_data: dict[str, dict[str, float]] = {"regimes": {}}

    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_market_regime_mismatch_rule_all_regimes_performing_well():
    """
    Tests MarketRegimeMismatchRule when all regimes perform well.
    """
    rule = MarketRegimeMismatchRule(min_trades=5, win_rate_threshold=0.4)
    analysis_data = {
        "regimes": {
            "trending_up": {"n_trades": 10, "win_rate": 0.6},
            "trending_down": {"n_trades": 8, "win_rate": 0.5},
            "sideways": {"n_trades": 7, "win_rate": 0.45},
        }
    }

    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None
