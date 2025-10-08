# AI Prompt: AI-Guided Iterative Strategy Discovery

## 1. Your Mission

Your primary mission is to autonomously discover and validate a profitable trading strategy through an **AI-guided iterative process**. You will use the platform's AI qualitative analysis system to provide intelligent feedback at each iteration, guiding your refinements toward a successful strategy.

This is an **unconstrained discovery process** - you have full freedom to explore any strategy type, make fundamental changes, or pivot completely based on what the data and AI analysis reveal. Your only hard constraints are the logging requirements and the final success criteria.

---

## 2. Core Mandates & Guardrails

These rules are absolute and must be followed at all times.

### 2.1 Unified Campaign Workspace
-   All work for a single strategy campaign **MUST** be contained within a single parent "campaign" directory under `workspace/research/`.
-   You are strictly forbidden from writing any files outside of this campaign workspace, with the single exception of promoting a final, validated strategy to the `config/strategy/` directory during the final promotion phase.
-   Create a descriptive campaign name (e.g., `trend_following_discovery`, `mean_reversion_exploration`).

### 2.2 Chronological, Timestamped Steps
-   Every iteration **MUST** be executed in its own unique, timestamped subdirectory within the campaign folder.
-   Directory names **MUST** follow the format: `YYYYMMDD_HHMMSS_XXX_YY_description`
    -   `YYYYMMDD_HHMMSS`: Timestamp
    -   `XXX`: Iteration number (000, 001, 002, etc.)
    -   `YY`: Phase code (00=baseline, 01-89=discovery, 90-98=validation, 99=promotion)
    -   `description`: Brief description (e.g., `baseline`, `add_atr_filter`, `wider_stops`)
-   Example: `20251005_143000_002_03_add_trend_filter/`

### 2.3 Meticulous Logging
-   **Each step's directory** **MUST** contain a `run_summary.md` file with:
    -   **Hypothesis**: What you're testing and why
    -   **Configuration Changes**: Specific changes from previous iteration
    -   **Results**: Key metrics (PnL, win rate, trades, drawdown)
    -   **AI Analysis Summary**: Key findings from the AI qualitative report
    -   **Learning**: What you learned from this iteration
    -   **Next Step**: What you'll try next and why
-   **Campaign root** **MUST** contain:
    -   `campaign_log.md`: Master log linking to each iteration
    -   `technical_debt.log`: Log of any bugs, unexpected behavior, or platform issues encountered

### 2.4 Bug Detection & Reporting
-   **CRITICAL**: This platform is new and may contain bugs. You **MUST** flag unexpected behavior for investigation:
    -   Zero trades when trades are expected
    -   Crashes or validation errors
    -   Results that don't match the configuration
    -   Inconsistencies between brief.json and trades.csv
    -   Any behavior that seems illogical or incorrect
-   When you encounter unexpected behavior:
    1. Document it in detail in the `run_summary.md`
    2. Add an entry to `technical_debt.log` with the issue and affected iteration
    3. Investigate whether it's a bug or expected behavior
    4. If uncertain, flag it for the user to review

### 2.5 Standard Timeframes
-   Use only the following standard timeframes: `1M`, `5M`, `15M`, `30M`
-   Avoid arbitrary timeframes unless there's a specific research reason

---

## 3. The AI-Guided Iterative Workflow

### Phase 0: Campaign Initialization

1. **Create Campaign Workspace**: `workspace/research/<campaign_name>/`
2. **Initialize Campaign Log**: Create `campaign_log.md` documenting:
   -   Campaign objective
   -   Starting strategy idea (if provided by user)
   -   Methodology overview
3. **Initialize Technical Debt Log**: Create empty `technical_debt.log`
4. **Review Available Indicators**: Read the contents of `src/trading_platform/strategy/indicators_registry.py` to get a complete list of all available indicators and their parameters that you can use in your strategies.

### Phase 1: AI-Guided Iterative Discovery

This is the core loop. Each iteration follows this exact process:

#### Step 1: Create Iteration Directory
-   Create timestamped directory for this iteration
-   Copy or create necessary files (strategy.yaml, rem.yaml, backtest.yaml)

#### Step 2: Document Hypothesis
-   Write `run_summary.md` with your hypothesis for this iteration
-   Explain what you're changing and why

#### Step 3: Run Backtest
-   Execute: `poetry run tp run-backtest --config <iteration>/backtest.yaml`
-   Verify the backtest completes successfully
-   **Check for unexpected results**: Zero trades? Errors? Flag them!

#### Step 4: Generate AI Qualitative Report
-   **CRITICAL STEP**: Run AI analysis to get intelligent feedback
-   Execute: `poetry run tp ai-diagnose --brief <run_dir>/brief.json --qualitative-report`
-   This creates `ai_qualitative_report.md` in the run directory
-   **WARNING**: This sends data to a third-party LLM API and may incur costs

#### Step 5: Analyze AI Feedback
-   **Read the entire AI qualitative report carefully**
-   The AI report provides:
    -   Overall narrative and performance assessment
    -   Exit timing efficiency analysis
    -   Transaction cost impact
    -   Regime alignment issues
    -   Risk and structural soundness
    -   Critical issues ranked by severity
    -   **Actionable recommendations prioritized by impact**
-   Identify the **top 1-3 critical issues** to address

#### Step 6: Update Run Summary
-   Complete the `run_summary.md` with:
    -   Results summary
    -   Key findings from AI report
    -   Learning and insights
    -   Planned next step

#### Step 7: Update Campaign Log
-   Add this iteration to `campaign_log.md`
-   Include link to iteration directory and brief summary

#### Step 8: Decide Next Action
Based on AI feedback and results, choose one:

-   **Continue Discovery**: Create next iteration addressing AI's top recommendation
-   **Pivot Strategy**: If fundamentally broken, try a completely different approach
-   **Proceed to Validation**: If promising results, move to Phase 2
-   **Flag for Investigation**: If unexpected behavior, document and investigate potential bug

### Phase 2: Validation

When you have a promising candidate (meets or is close to success criteria):

1. **Create Validation Directory**: `YYYYMMDD_HHMMSS_XXX_90_validation/`
2. **Run Walk-Forward Evaluation**: Test robustness over time
3. **Analyze Validation Results**: Use AI qualitative analysis on validation run
4. **Document Verdict**: Robust or Brittle?
5. **Update Campaign Log**: Link validation results

### Phase 3: Promotion

If strategy passes validation:

1. **Create Final Scorecard**: Verify ALL success criteria (Section 5)
2. **Create Promotion Directory**: `YYYYMMDD_HHMMSS_XXX_99_PROMOTION/`
3. **Promote Final Strategy**: Save the final, validated `strategy.yaml` to `config/strategy/` using a descriptive name (e.g., `bb_breakout_trend_15m.yaml`). Consolidate all other final artifacts (brief.json, reports) into the promotion directory.
4. **Report to User**: Present findings and ask about formal promotion

---

## 4. Strategy Development Freedom

You have **full discretion** to discover any profitable strategy. The user may provide a starting point, but you are **NOT constrained** to that approach.

### What You Can Change
-   **Strategy Type**: Mean reversion → trend following, breakout, momentum, etc.
-   **Indicators**: Add, remove, or replace any technical indicators
-   **Entry Logic**: Completely redesign entry conditions
-   **Exit Logic**: Redesign exit conditions, use REM-only exits, signal-based exits, or hybrid
-   **Risk Management**: Adjust stops, take profits, position sizing
-   **Timeframes**: Switch to different timeframes if analysis suggests it
-   **Symbols**: Test on different currency pairs or instruments
-   **Filters**: Add regime filters, volatility filters, time-of-day filters, etc.

### When to Pivot

If the AI analysis reveals **fundamental problems** with the strategy approach:
-   Example: "Strategy claims mean reversion but operates as scalper"
-   Example: "Exit timing incompatible with holding for trends"
-   Example: "Win rate good but fundamental structural flaw prevents profitability"

**DO NOT** keep iterating on a fundamentally broken approach. **PIVOT** to a different strategy type.

### Example Pivot Scenarios

**Scenario 1**: You start with BB mean reversion, but AI reveals it exits too early to capture trends
-   **Action**: Pivot to trend-following strategy using BB breakouts instead of mean reversion

**Scenario 2**: Strategy generates signals but REM exits don't trigger (zero trades)
-   **Action**: Investigate if it's a bug, document in technical_debt.log, try hybrid signal+REM exits

**Scenario 3**: Transaction costs eat up all profits (high-frequency strategy)
-   **Action**: Pivot to lower-frequency strategy or add filters to reduce trade count

---

## 5. Success Criteria (ABSOLUTE REQUIREMENTS)

A strategy is only successful if it meets **ALL** of these criteria:

### 5.1 Profitability
-   `total_pnl` > 0 (must be profitable)

### 5.2 Risk Management
-   `max_drawdown` < 20% of total PnL
-   **CRITICAL**: Maximum drawdown period **MUST** be < 2 weeks
-   Test over **minimum 3 years** of data (for validation phase)

### 5.3 Risk/Reward
-   Sharpe Ratio > 1.0
-   Reward/Risk Ratio (Avg Win / Avg Loss) > 1.0

### 5.4 Robustness
-   Must pass walk-forward evaluation
-   Performance should be consistent across different time periods

### 5.5 Statistical Significance
-   Sufficient number of trades to be statistically meaningful (typically 30+ trades)
-   Win rate should not be due to random chance

---

## 6. Key Differences from Manual Discovery

### Use AI Feedback as Your Guide
-   The AI qualitative report is your **primary source of insights**
-   Don't guess at what's wrong - read what the AI identifies
-   Prioritize issues by the AI's severity ranking
-   Follow the AI's actionable recommendations

### Iterate Rapidly
-   Each iteration should address the **top 1-3 issues** from AI feedback
-   Don't try to fix everything at once
-   Make targeted, measurable changes
-   Document what each change is meant to accomplish

### Be Willing to Pivot
-   If AI feedback suggests fundamental problems, don't iterate endlessly
-   Recognize when a strategy approach is flawed
-   Have the courage to start fresh with a different strategy type

### Flag the Unexpected
-   This is a new platform - bugs are likely
-   Any weird behavior should be documented and investigated
-   Don't assume strange results are "just how it works"

---

## 7. Iteration Template

Use this template for each `run_summary.md`:

```markdown
# Iteration X: [Brief Description]

## Hypothesis
[What you're testing and why]

## Configuration Changes from Previous Iteration
- Change 1: [specific change]
- Change 2: [specific change]
- Rationale: [why these changes]

## Configuration Details
- Strategy: [strategy type and key parameters]
- Entry: [entry conditions]
- Exit: [exit conditions]
- REM: [risk management settings]
- Period: [date range]
- Symbol: [trading pair]
- Timeframe: [chart timeframe]

## Results
- Total PnL: $X (Y% return)
- Win Rate: Z%
- Total Trades: N
- Max Drawdown: $DD (DD%)
- Sharpe Ratio: S
- Avg Win / Avg Loss: R

## AI Analysis Summary

### Critical Issues Identified
1. [Issue 1 - severity]
2. [Issue 2 - severity]
3. [Issue 3 - severity]

### Key AI Findings
- [Finding 1]
- [Finding 2]
- [Finding 3]

### AI's Top Recommendations
1. [Priority 1 recommendation]
2. [Priority 2 recommendation]
3. [Priority 3 recommendation]

## Unexpected Behavior / Potential Bugs
[Document anything unusual - or write "None observed"]

## Learning
[What you learned from this iteration]

## Decision
[Continue discovery / Pivot strategy / Proceed to validation / Investigate bug]

## Next Step
**Iteration X+1**: [What you'll try next and why]
```

---

## 8. Campaign Log Template

Use this template for `campaign_log.md`:

```markdown
# [Campaign Name] - AI-Guided Discovery

## Campaign Objective
[Brief description of what you're trying to discover]

## Starting Point
[Initial strategy idea, if any]

## Methodology
AI-guided iterative discovery using qualitative analysis feedback at each step.

## Success Criteria
- Profitable (PnL > 0)
- Max DD < 20% of PnL
- **Max DD period < 2 weeks**
- Sharpe > 1.0
- Avg Win/Loss > 1.0
- Robust across walk-forward validation

## Iterations

### [Iteration 0: Baseline](YYYYMMDD_HHMMSS_000_00_baseline/)
**Status**: Complete
**Result**: [Brief result]
**Key Finding**: [Main insight from AI]
**Next**: [What you'll try next]

### [Iteration 1: Description](YYYYMMDD_HHMMSS_001_01_description/)
**Status**: Complete
**Result**: [Brief result]
**Key Finding**: [Main insight from AI]
**Next**: [What you'll try next]

[... continue for each iteration ...]

## Pivot Points
[Document any major strategic pivots]

## Final Outcome
[To be filled when campaign concludes]
```

---

## 9. Technical Debt Log Template

Use this template for `technical_debt.log`:

```
# Technical Debt & Potential Bugs Log

## Format
[YYYYMMDD_HHMMSS] Iteration_XXX: Brief description of issue

## Issues

[20251005_143000] Iteration_001: Zero trades generated despite valid entry signals - potential REM exit bug
[20251005_150000] Iteration_004: Trailing stop never triggers even with rem.yaml configured - investigate exit precedence
```

---

## 10. Best Practices

### Start Simple
-   Begin with a simple, well-understood strategy
-   Add complexity only when AI feedback suggests it

### Make One Change at a Time
-   Isolate variables so you know what caused changes in performance
-   Exception: When pivoting to entirely new strategy

### Trust the AI Analysis
-   The AI has access to post-exit analysis and deep metrics you might miss
-   If AI says "100% premature exits", believe it
-   If AI says "fundamental structural flaw", consider pivoting

### Document Everything
-   Future you (or another AI) needs to understand your reasoning
-   Document failed attempts - they're valuable learning

### Watch for Patterns
-   If same issue appears across iterations, it might be fundamental
-   If AI keeps recommending same fix, you might be avoiding the real problem

### Know When to Stop
-   If 10+ iterations show no improvement, pivot or conclude
-   Don't iterate endlessly on a broken strategy

---

## 11. Example Campaign Flow

This is an example to illustrate the process:

**Iteration 0**: Test BB mean reversion baseline
- **Result**: $172, 67.5% WR, but AI says "100% premature exits, leaving 59x profit on table"
- **Next**: Try to fix exit timing

**Iteration 1**: Remove signal exits to force longer holds
- **Result**: 0 trades - positions never close
- **Flag**: Potential bug or limitation - REM exits alone don't work
- **Document**: Add to technical_debt.log
- **Next**: Try different approach

**Iteration 2**: Wider BB bands to delay signal exits
- **Result**: $147, same problem - "111x underperformance, still exiting too early"
- **AI Finding**: "Strategy Identity Crisis - claims mean reversion but operates as scalper"
- **Next**: Consider pivot

**Iteration 3**: Add take profit to capture some trends
- **Result**: $129, worse - TP rarely triggers, signals still dominate
- **AI Bottom Line**: "Could turn 1.29% into 15-65% with trend-following exits"
- **Decision**: Pivot to trend-following strategy

**Iteration 4**: NEW STRATEGY - Trend following with BB breakouts
- **Result**: $450, 55% WR, captures trends better
- **AI Finding**: "Good foundation but needs regime filtering"
- **Next**: Add trend strength filter

[... continue iterating on trend-following approach ...]

---

## 12. Final Checklist Before Promotion

Before promoting a strategy, verify:

- [ ] Total PnL > 0 over 3+ years
- [ ] Max drawdown < 20% of total PnL
- [ ] **Max drawdown period < 2 weeks**
- [ ] Sharpe Ratio > 1.0
- [ ] Avg Win / Avg Loss > 1.0
- [ ] Passed walk-forward validation
- [ ] AI qualitative analysis shows no critical structural flaws
- [ ] Sufficient trade count (30+ trades minimum)
- [ ] No unresolved bugs or unexpected behavior
- [ ] All iterations documented with run_summary.md
- [ ] Campaign log complete and up-to-date
- [ ] Technical debt log reviewed and issues resolved or understood

---

## 13. Remember

-   **You are unconstrained** - find ANY strategy that works
-   **The AI is your guide** - use its feedback religiously
-   **Document everything** - logging is not optional
-   **Flag bugs immediately** - this platform is new
-   **Pivot when needed** - don't iterate on broken foundations
-   **Only one hard rule**: Max drawdown period < 2 weeks over 3 years

Good luck discovering a profitable strategy!
