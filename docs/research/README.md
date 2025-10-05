# Research Documentation

This directory contains knowledge accumulated from backtesting research campaigns.

## Files

### [strategy_performance_catalog.md](strategy_performance_catalog.md)
**Main Reference** - Comprehensive catalog of all tested strategies, indicators, and their performance characteristics across different market regimes.

**Use this for:**
- Understanding which strategies work in which market conditions
- Avoiding repeated failed experiments
- Building multi-strategy portfolios with complementary edges
- Selecting appropriate indicators for specific market regimes

### [strategy_documentation_template.md](strategy_documentation_template.md)
**Template** - Standard format for documenting new strategies in the catalog.

**Use this when:**
- Adding a new strategy to the catalog
- Updating existing strategy findings after new iterations
- Ensuring consistent documentation across all strategies

## Quick Start

### I want to know which strategy to use right now
1. Identify current market regime (time of day, volatility, trend)
2. Open `strategy_performance_catalog.md`
3. Check "Optimal Market Conditions" for each strategy
4. Select strategy that matches current conditions

### I'm starting a new research iteration
1. Check `strategy_performance_catalog.md` → "Failed Hypothesis Log"
2. Don't repeat rejected hypotheses for the current strategy
3. Review "Indicator Effectiveness Matrix" for guidance
4. Plan tests based on catalog insights

### I just completed an iteration
1. Copy `strategy_documentation_template.md` if adding new strategy
2. Update relevant sections in `strategy_performance_catalog.md`:
   - Strategy profile (add findings)
   - Indicator matrix (add learnings)
   - Failed hypothesis log (add rejections)
   - Portfolio recommendations (revise)
3. Update version history

### I want to build a multi-strategy portfolio
1. Review all strategy profiles in catalog
2. Look for **complementary** time-of-day patterns
3. Avoid strategies that profit in the SAME conditions
4. Check "Multi-Strategy Considerations" sections
5. See "Portfolio Strategy Recommendations"

## Key Insights

### Critical Lesson: Strategy-Specific Regimes
**Never assume filters transfer between strategies!**

Example: The blackout policy that improved EMA crossover by +1626% destroyed SuperTrend by -80%. Each strategy needs its own optimization based on its unique characteristics.

### Multi-Strategy Portfolio Benefits
- **Diversification:** Different strategies handle different regimes
- **Consistency:** Smoother equity curve across all market conditions
- **Robustness:** Higher walk-forward validation scores
- **Risk Reduction:** Lower correlation between strategy returns

## Maintenance

Update the catalog:
- ✅ **After every iteration** (add findings, update metrics)
- ✅ **When pivoting strategies** (create new profiles)
- ✅ **When discovering new regimes** (update conditions)
- ✅ **When testing fails** (add to failed hypothesis log)

The catalog is only valuable if kept current!
