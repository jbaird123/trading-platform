# RuleBasedAnalyzer - Heuristic Diagnostic Analysis

## Overview

`RuleBasedAnalyzer` provides **rule-based diagnostic analysis** using heuristics and pattern detection. Unlike ML models, these rules provide immediate insights without requiring training data.

### Key Characteristics

- **No Training Required**: Rules are hand-crafted heuristics, not learned patterns
- **Immediate Insights**: Run analysis on any backtest or campaign results
- **Complementary to ML**: Works alongside ProfitabilityModel and PerformanceDiagnosticModel
- **Location**: `src/trading_platform/reporting/diagnostics/` (separate from ML models)

## Purpose

RuleBasedAnalyzer answers questions like:
- Are exits systematically inefficient?
- Is win rate inconsistent with expectancy?
- Are there suspicious patterns in the results?
- What quick improvements can be made?

## Architecture

### Separation from ML Models

```
src/trading_platform/
├── ai/
│   └── models/              # Machine learning models
│       ├── profitability.py
│       ├── performance_diagnostic.py
│       └── registry.py
└── reporting/
    └── diagnostics/         # Rule-based analysis
        ├── rule_based.py    # Main analyzer
        ├── rules.py         # Diagnostic rules
        └── recommendations.py
```

This separation makes it clear:
- **ML models** require training, learn from data
- **Rule-based analysis** uses fixed heuristics, no training needed

### Available Rules

Current diagnostic rules:

1. **InefficientExitsRule**: Detects if exits leave money on the table
2. **LowWinRateHighTradesRule**: Flags strategies with low win rate but high trade count
3. **StrategyParameterOptimizationOpportunityRule**: Suggests parameter tuning opportunities
4. **SignalPersistenceRule**: Identifies potential signal timing issues
5. **MarketRegimeMismatchRule**: Detects regime-strategy misalignment
6. **DataQualityImpactRule**: Flags data quality issues affecting results

## Basic Usage

### Analyzing a Backtest

```python
from trading_platform.reporting.diagnostics import RuleBasedAnalyzer
import json

# Load backtest results (brief.json format)
with open("path/to/brief.json") as f:
    brief_data = json.load(f)

# Initialize analyzer
analyzer = RuleBasedAnalyzer(analysis_data=brief_data)

# Run all diagnostic rules
analyzer.run()

# Generate reports
markdown_report = analyzer.generate_report_markdown()
json_report = analyzer.generate_report_json()

print(markdown_report)
```

### CLI Usage

```bash
# Analyze a campaign brief
poetry run tp ai-diagnose --brief path/to/brief.json

# This generates:
# - ai_diagnostic_report.md   (human-readable)
# - ai_diagnostic_report.json (machine-readable)
```

## Input Data Format

The analyzer expects analysis data in the format of `brief.json`:

```json
{
  "backtest_metrics": {
    "n_trades": 650,
    "win_rate": 0.51,
    "sharpe_ratio": 1.2,
    "total_pnl": 1500.0
  },
  "trades": [
    {
      "id": 1,
      "pnl": 10.5,
      "entry_context": {...},
      "exit_context": {...},
      "mfe_currency": 15.0,
      "mae_currency": 5.0
    }
  ],
  "model_analysis": {
    "avg_pnl_left_on_table_at_tp": 12.5
  }
}
```

## Output Format

### Markdown Report

```markdown
# AI Diagnostic Report

## Suggested Parameters
- fast_length: 12
- slow_length: 26

## Recommendations

### Tighten Take-Profit Exits
Exit timing appears suboptimal based on post-exit price movement.

- Category: exit_optimization
- Confidence: high

## Inefficient Take-Profit Exits Detected

$12.50 of potential profit was left on the table by take-profit exits,
suggesting inefficient exit logic.

**Evidence:**
- avg_pnl_left_on_table_at_tp: 12.5
- threshold: 10.0
```

### JSON Report

```json
{
  "conclusions": [
    {
      "title": "Inefficient Take-Profit Exits Detected",
      "summary": "$12.50 of potential profit was left on the table...",
      "evidence": {
        "avg_pnl_left_on_table_at_tp": 12.5,
        "threshold": 10.0
      }
    }
  ],
  "recommendations": [
    {
      "title": "Tighten Take-Profit Exits",
      "summary": "Exit timing appears suboptimal...",
      "category": "exit_optimization",
      "confidence": "high"
    }
  ],
  "model_insights": [...],
  "suggested_parameters": {
    "fast_length": 12,
    "slow_length": 26
  }
}
```

## Diagnostic Rules in Detail

### 1. Inefficient Exits Rule

**Detects**: Exits that leave money on the table

**Evidence Used**:
- `avg_pnl_left_on_table_at_tp` from model analysis
- `mfe_currency` and `mae_currency` from trades

**Triggers When**:
- Average PnL left > $10.00
- Many trades with MFE > threshold

**Recommendation**: Adjust take-profit levels or use trailing stops

### 2. Low Win Rate High Trades Rule

**Detects**: Strategies with low win rate but many trades

**Evidence Used**:
- `win_rate` from backtest metrics
- `n_trades` from backtest metrics

**Triggers When**:
- Win rate < 45%
- Trade count > 100

**Recommendation**: Improve entry filters or signal quality

### 3. Strategy Parameter Optimization Rule

**Detects**: Opportunities for parameter tuning

**Evidence Used**:
- Strategy parameter values
- Performance metrics

**Triggers When**:
- Parameters appear sub-optimal based on results
- Clear improvement opportunity identified

**Recommendation**: Specific parameter values to try

### 4. Signal Persistence Rule

**Detects**: Potential signal timing issues

**Evidence Used**:
- Entry/exit timing patterns
- Signal duration statistics

**Triggers When**:
- Signals disappear too quickly
- Entry execution delays impact performance

**Recommendation**: Adjust entry window or signal filtering

### 5. Market Regime Mismatch Rule

**Detects**: Strategy-regime misalignment

**Evidence Used**:
- Market regime indicators
- Strategy performance by regime

**Triggers When**:
- Strategy underperforms in current regime
- Clear regime-performance correlation

**Recommendation**: Add regime filters or adjust strategy

### 6. Data Quality Impact Rule

**Detects**: Data quality issues affecting results

**Evidence Used**:
- Missing data indicators
- Data consistency checks
- Outlier detection

**Triggers When**:
- Significant data gaps
- Suspicious patterns suggesting data issues

**Recommendation**: Review data quality, re-run backtest

## Integration with ML Models

RuleBasedAnalyzer can work with ML model outputs:

```python
from pathlib import Path

# If profitability_model.joblib exists in run directory,
# analyzer automatically loads it and generates insights

analysis_data = {
    "backtest_metrics": {...},
    "trades": [...],
    "_brief_path": "path/to/run/directory"  # Contains profitability_model.joblib
}

analyzer = RuleBasedAnalyzer(analysis_data=analysis_data)
analyzer.run()

# Report includes model insights:
# - Feature importances
# - Prediction confidence
# - Trade-level predictions
```

## Customization

### Adding New Rules

Create a new rule class:

```python
from trading_platform.reporting.diagnostics.rules import BaseDiagnosticRule, DiagnosticConclusion

class MyCustomRule(BaseDiagnosticRule):
    """Detect custom pattern in results."""

    def evaluate(self, analysis_data):
        metrics = analysis_data.get("backtest_metrics", {})

        # Your custom logic
        if metrics.get("some_metric") > threshold:
            return DiagnosticConclusion(
                title="Custom Issue Detected",
                summary="Description of the issue...",
                evidence={
                    "some_metric": metrics["some_metric"],
                    "threshold": threshold
                }
            )

        return None  # Rule didn't trigger
```

Register it in `rules.py`:

```python
def get_all_rules():
    return [
        InefficientExitsRule(),
        LowWinRateHighTradesRule(),
        MyCustomRule(),  # Add your rule
        # ...
    ]
```

## Use Cases

### 1. Post-Campaign Quick Analysis

```bash
# After running a campaign, quickly check for issues
poetry run tp ai-diagnose --brief data/campaigns/campaign_id/brief.json

# Review markdown report for actionable insights
cat data/campaigns/campaign_id/ai_diagnostic_report.md
```

### 2. Continuous Integration Checks

```python
# In CI pipeline, check for critical issues
analyzer = RuleBasedAnalyzer(analysis_data=brief_data)
analyzer.run()

# Fail CI if critical issues detected
for conclusion in analyzer.conclusions:
    if "critical" in conclusion.title.lower():
        raise ValueError(f"Critical issue: {conclusion.summary}")
```

### 3. Automated Recommendations

```python
# Generate recommendations for all campaigns
import glob

for brief_path in glob.glob("data/campaigns/*/brief.json"):
    with open(brief_path) as f:
        brief_data = json.load(f)

    analyzer = RuleBasedAnalyzer(analysis_data=brief_data)
    analyzer.run()

    # Save recommendations
    recs = analyzer.generate_recommendations()
    output_path = Path(brief_path).parent / "recommendations.json"
    output_path.write_text(json.dumps(recs, indent=2))
```

## Comparison: RuleBasedAnalyzer vs ML Models

| Aspect | RuleBasedAnalyzer | ML Models |
|--------|------------------|-----------|
| **Training** | None required | Requires enriched data |
| **Speed** | Instant | Requires training time |
| **Insights** | Fixed heuristics | Learned patterns |
| **Use Case** | Quick diagnostics | Deep regime analysis |
| **Data Needs** | Just brief.json | 50+ enriched trades |
| **Interpretability** | Very high | Medium (feature importances) |

**Best Practice**: Use both!
- RuleBasedAnalyzer: Quick feedback after every backtest
- ML Models: Deep analysis for strategy improvement

## See Also

- [RuleBasedAnalyzer API](../src/trading_platform/reporting/diagnostics/rule_based.py)
- [Diagnostic Rules](../src/trading_platform/reporting/diagnostics/rules.py)
- [ProfitabilityModel Documentation](02_profitability_model.md)
- [PerformanceDiagnosticModel Documentation](04_performance_diagnostic_model.md)
- [Campaign Runner Guide](06_campaign_runner_guide.md)
