"""Diagnostic analysis for trading strategies.

This module contains rule-based diagnostic analysis tools:
- RuleBasedAnalyzer: Heuristic rules for quick strategy insights
- Diagnostic rules: Pattern detection for common strategy issues
- Recommendations: Actionable suggestions based on analysis
"""

from trading_platform.reporting.diagnostics.rule_based import RuleBasedAnalyzer

__all__ = ["RuleBasedAnalyzer"]
