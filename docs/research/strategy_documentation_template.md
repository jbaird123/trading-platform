# Strategy Documentation Template

**Copy this template when adding a new strategy to the catalog.**

---

## [Strategy Name] ([Parameters])

**Signal Type:** [Trend-Following / Mean-Reversion / Breakout / etc.]
**Research Period:** [Start Date] to [End Date]
**Campaigns:** [campaign_name] (Iterations [XXX-YYY])

### Performance Summary
- **Raw Baseline:** $[PnL] PnL, [X]% WR, [X]x DD/PnL [✅/⚠️/❌]
- **Optimized:** $[PnL] PnL, [X]% WR, [X]x DD/PnL [✅/⚠️/❌]
- **Walk-Forward:** [X]% profitable windows [✅/⚠️/❌] (target: 70%)

### Optimal Market Conditions

**✅ WORKS WELL IN:**
- **Time of Day:** [Hours] UTC
  - **Sessions:** [London/NY/Asian/Overlap]
  - **Why:** [Market-based justification]
- **Market Structure:** [Trending/Ranging/Volatile/Calm]
- **Volatility:** [High/Low/Moderate]
- **Trend Strength:** [Strong/Weak/Any]
- **Other Conditions:** [Specific regime characteristics]

**❌ PERFORMS POORLY IN:**
- **Time of Day:** [Hours] UTC
  - **Sessions:** [Which sessions]
  - **Why:** [Why it struggles]
- **Market Structure:** [Conditions where it fails]
- **Other Conditions:** [Anti-patterns]

### Validated Filters

**✅ SUCCESSFUL:**
1. **[Filter Name]** (Iteration [XXX])
   - Hypothesis: [What you thought would happen]
   - Result: [Actual outcome with metrics]
   - Impact: [+/-X% PnL improvement]
   - Rationale: [Why it worked]

**❌ REJECTED:**
1. **[Filter Name]** (Iteration [XXX])
   - Hypothesis: [What you thought would happen]
   - Result: [Actual outcome with metrics]
   - Lesson: [What you learned]

### Exit Optimization
- **Optimal:** [Stop-loss and take-profit settings]
- **Reasoning:** [Why these settings work]
- **Alternatives Tested:** [What else you tried]

### Known Limitations
- **[Limitation 1]:** [Description and impact]
- **[Limitation 2]:** [Description and impact]
- **Cannot Fix:** [Fundamental issues that can't be optimized away]

### Multi-Strategy Considerations
- **Complement With:** [Which other strategies work well together]
- **Avoid Pairing With:** [Which strategies would be redundant]
- **Portfolio Role:** [How this fits in a multi-strategy portfolio]

### Key Differentiators from [Other Strategy]

| Aspect | [Strategy 1] | [Strategy 2] |
|--------|--------------|--------------|
| **Signal Type** | [Type] | [Type] |
| **Best Hour** | [Hour] (+$[PnL]) | [Hour] (+$[PnL]) |
| **Worst Hour** | [Hour] (-$[PnL]) | [Hour] (-$[PnL]) |
| **Trade Count** | [N] | [N] |
| **Raw PnL** | $[X] | $[X] |
| **[Filter] Effect** | [%] | [%] |

### Critical Insights
- **Insight 1:** [Important finding]
- **Insight 2:** [Important finding]
- **Portfolio Implication:** [How this affects strategy selection]

---

## Update Checklist

When documenting a new strategy or updating an existing one:

- [ ] Fill in all sections of the template
- [ ] Add to main catalog's "Strategy Profiles" section
- [ ] Update "Indicator Effectiveness Matrix" if new indicators used
- [ ] Add failed hypotheses to "Failed Hypothesis Log"
- [ ] Update "Portfolio Strategy Recommendations"
- [ ] Update "Version History" at bottom of main catalog
- [ ] Cross-reference with complementary strategies
- [ ] Note any new market regime discoveries
