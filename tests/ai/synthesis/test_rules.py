from trading_platform.ai.synthesis.rules import (
    DiagnosticConclusion,
    InefficientExitsRule,
    LowWinRateHighTradesRule,
    OverTradingRule,
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
    rule = StrategyParameterOptimizationOpportunityRule(
        param_defaults={"fast": 12, "slow": 26}
    )
    analysis_data = {"strategy_params": {"fast": 12, "slow": 26}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert conclusion.title == "Strategy Parameter Optimization Opportunity"
    assert "unoptimized or default" in conclusion.summary
    assert conclusion.evidence["unoptimized_params"] == {"fast": 12, "slow": 26}


def test_strategy_param_optimization_rule_not_triggered():
    rule = StrategyParameterOptimizationOpportunityRule(
        param_defaults={"fast": 12, "slow": 26}
    )
    analysis_data = {"strategy_params": {"fast": 10, "slow": 30}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_strategy_param_optimization_rule_partial():
    rule = StrategyParameterOptimizationOpportunityRule(
        param_defaults={"fast": 12, "slow": 26}
    )
    analysis_data = {"strategy_params": {"fast": 12, "slow": 30}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is not None
    assert "unoptimized or default" in conclusion.summary
    assert conclusion.evidence["unoptimized_params"] == {"fast": 12}


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
    analysis_data = {"backtest_metrics": {"n_trades": 80, "win_rate": 0.50}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_low_win_rate_high_trades_rule_not_triggered_high_win_rate():
    rule = LowWinRateHighTradesRule(win_rate_threshold=0.55, n_trades_threshold=100)
    analysis_data = {"backtest_metrics": {"n_trades": 150, "win_rate": 0.60}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_low_win_rate_high_trades_rule_missing_metrics():
    rule = LowWinRateHighTradesRule()
    analysis_data = {}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


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
    analysis_data = {"backtest_metrics": {"n_trades": 600, "win_rate": 0.50}}
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
    analysis_data = {"backtest_metrics": {"n_trades": 400, "win_rate": 0.50}}
    conclusion = rule.evaluate(analysis_data)
    assert conclusion is None


def test_over_trading_rule_not_triggered_high_win_rate():
    rule = OverTradingRule()
    analysis_data = {"backtest_metrics": {"n_trades": 600, "win_rate": 0.60}}
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
    analysis_data = {"model_analysis": {"avg_pnl_left_on_table_at_tp": 15.50}}
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
    analysis_data = {"model_analysis": {"avg_pnl_left_on_table_at_tp": 5.0}}
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
    assert len(rules) == 7
    assert any(isinstance(rule, OverTradingRule) for rule in rules)
    assert any(isinstance(rule, InefficientExitsRule) for rule in rules)
