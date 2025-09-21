import pytest
from src.trading_platform.ai.synthesis.rules import DiagnosticConclusion, OverTradingRule, InefficientExitsRule, get_all_rules

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

# --- Tests for OverTradingRule ---

def test_over_trading_rule_triggered():
    rule = OverTradingRule()
    analysis_data = {
        "backtest_metrics": {"n_trades": 600, "win_rate": 0.50}
    }
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert conclusion.title == "Potential Over-Trading Detected"
    assert "unusually high number of trades (600)" in conclusion.summary
    assert "low win rate (50.00%)" in conclusion.summary
    assert conclusion.evidence == {
        "n_trades": 600,
        "win_rate": 0.50,
        "thresholds": {"n_trades": 500, "win_rate": 0.55},
    }

def test_over_trading_rule_not_triggered_low_trades():
    rule = OverTradingRule()
    analysis_data = {
        "backtest_metrics": {"n_trades": 400, "win_rate": 0.50}
    }
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None

def test_over_trading_rule_not_triggered_high_win_rate():
    rule = OverTradingRule()
    analysis_data = {
        "backtest_metrics": {"n_trades": 600, "win_rate": 0.60}
    }
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None

def test_over_trading_rule_missing_backtest_metrics():
    rule = OverTradingRule()
    analysis_data = {}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None

def test_over_trading_rule_missing_n_trades():
    rule = OverTradingRule()
    analysis_data = {"backtest_metrics": {"win_rate": 0.50}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None

def test_over_trading_rule_missing_win_rate():
    rule = OverTradingRule()
    analysis_data = {"backtest_metrics": {"n_trades": 600}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None

# --- Tests for InefficientExitsRule ---

def test_inefficient_exits_rule_triggered():
    rule = InefficientExitsRule()
    analysis_data = {
        "model_analysis": {"avg_pnl_left_on_table_at_tp": 15.50}
    }
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
    analysis_data = {
        "model_analysis": {"avg_pnl_left_on_table_at_tp": 5.0}
    }
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None

def test_inefficient_exits_rule_missing_model_analysis():
    rule = InefficientExitsRule()
    analysis_data = {}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None

def test_inefficient_exits_rule_missing_pnl_metric():
    rule = InefficientExitsRule()
    analysis_data = {"model_analysis": {"some_other_metric": 100}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None

# --- Tests for get_all_rules ---

def test_get_all_rules():
    rules = get_all_rules()
    assert isinstance(rules, list)
    assert len(rules) == 2
    assert any(isinstance(rule, OverTradingRule) for rule in rules)
    assert any(isinstance(rule, InefficientExitsRule) for rule in rules)
