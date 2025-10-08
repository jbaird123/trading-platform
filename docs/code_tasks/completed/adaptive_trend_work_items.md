# Adaptive Trend Discovery – Code Enhancement Proposals

This document outlines engineering work needed to move beyond we’ve achieved
with configuration-only tuning. The goal is to give architects enough detail to
judge scope, dependencies, and expected benefits before green-lighting any
coding effort.

## Context & Current Plateau

- The EMA crossover baseline (Ref 04) reaches ~39% profitable WFE windows with
  ATR-based regime filters, but further config tweaks (Ref 05–10) show
  diminishing returns and/or unacceptable trade-count reduction.
- Trade-level analysis indicates losses concentrate in midday and late-session
  hours despite adequate ATR, implying the signal and exit logic are not
  adaptive enough; regime filters alone can’t bridge the gap.

## Proposed Engineering Tracks

### 1. Signal Confirmation Enhancements

**Objective:** Improve entry quality by requiring trend/momentum confirmation
that cannot be expressed with current YAML predicates.

**Work Items:**
1. **Indicator Registry Extension:**
   - Add EMA slope, higher-timeframe EMA, RSI, and rate-of-change indicators to
     `src/trading_platform/strategy/indicators_registry.py`.
   - Update `docs/schemas/strategy.schema.json` and loader logic so new features
     validate and expose config knobs (`slope_window`, `roc_period`, etc.).
2. **Strategy Predicate Expansion:**
   - Support predicates like `slope_is_above` or `roc_is_above` within
     `yaml_strategy.py`, enabling slope/ROC gating without hardcoded logic.
   - Ensure schema and unit tests cover these new predicates.
3. **Higher Timeframe Trend Feature (optional):**
   - Add utility to compute a higher-timeframe EMA/ADX and expose it as a
     contextual feature (requires multi-resolution caching in DataHandler or a
     pre-aggregation step). Benefit: reliably spot macro trends.

**Rationale:** Currently the YAML only allows simple `is_above` checks on raw
indicators. Without slope or momentum context, the strategy enters many trades
where the crossover is flat or oscillating—config-level ATR filters can’t fully
catch these cases. Code changes would let us filter to “true trend” crossovers.

### 2. Exit & Risk Model Adaptation

**Objective:** Reduce drawdown and degradation by making exits sensitive to
volatile mid-session reversals.

**Work Items:**
1. **Dynamic REM Modules:**
   - Implement a REM that combines trailing stop with break-even and partial
     profit-taking logic (e.g., move stop to break-even after +0.75R, exit half
     position, trail half by ATR multiple).
   - Add configuration schema, serialization, and tests for the new module.
2. **Volatility-Aware Trailing:**
   - Extend REM to use ATR percentile or ADX to tighten stops when volatility or
     momentum falls—requires new inputs from `trade.context_at_entry`.
3. **REM Testing & Brief Integration:**
   - Update `finalize_run` to capture metrics specific to the new exit behavior
     (e.g., partial-exit PnL contribution) and ensure `brief.json` stays
     consistent.

**Rationale:** Most losses in mid-day/late-session trades occur after entry when
momentum stalls. Exit logic tailored to the trend quality can cut off these
losses without banning the hour outright. Current REM options are “one size
fits all.”

### 3. Regime Feature Expansion

**Objective:** Provide richer market-state signals (trend labels, volatility
percentiles, macro blackout) for RMM logic beyond straight ATR thresholds.

**Work Items:**
1. **RMM Feature Library:**
   - Implement features such as ATR percentile, realized volatility, volume
     Z-score, and higher-timeframe ADX in `RMMEngine.compute_features`.
   - Update JSON schema (`docs/schemas/rmm.schema.json`) and validation to allow
     these new features.
2. **New Regime Predicates:**
   - Support predicates like `percentile_is_above`, `trend_label_is`, or
     `volatility_is_between` within RMM conditions to express richer logic.
3. **Macro Event Calendar (optional):**
   - Integrate a pluggable event calendar (e.g., NFP, CPI) with blackout
     predicates for known high-risk windows.

**Rationale:** ATR alone doesn’t differentiate between choppy vs structured
volatility. Percentiles or trend labels would let us skip trades only when
volatility is “too low relative to history,” while still taking advantage of
trend windows. Macro events are consistently flagged by analysts as high-risk
for EMA strategies; having a first-class predicate would remove manual
blacklisting.

### 4. Diagnostics & Data Plumbing

**Objective:** Support the above initiatives with better data exposure and QA.

**Work Items:**
1. **Contextual Feature Logging:**
   - Update `trades.csv` / `brief.json` exports to include any new features
     (slope, higher timeframe trend, ATR percentiles) for post-run analysis.
2. **Testing Infrastructure:**
   - Add integration tests ensuring new indicators/REM modules don’t break
     existing reports, plus regression tests for trade-count invariants.
3. **Performance Profiling:**
   - Since added indicators may increase runtime, profile runs with/without the
     new features and adjust caching (e.g., DataHandler multi-timeframe caching)
     to keep run times acceptable.

**Rationale:** Without consistent logging, future analyses repeat manual work,
slowing iteration. Tests ensure `.schema` updates, new predicates, and REM
features don’t regress the current stable baseline.

## Implementation Notes & Dependencies

- Adding indicators/predicates requires coordination across schema, registry,
  loader, and YAML parser logic—unit tests are mandatory.
- New REM behaviors must be reflected in `brief.json` sections (`rem_policy`,
  `exit_efficiency`, etc.) to keep downstream analytics accurate.
- Macro/calendar integration would depend on data availability; if not feasible,
  skip or stub until the data source is defined.

## Expected Impact

- **Signal enhancements** should raise the WFE hit rate by eliminating noisy
  crossovers without sacrificing trade count.
- **Exit adaptations** aim to reduce drawdown/degradation without shrinking
  the sample, addressing the midday/late-session losses highlighted in the
  trade analysis.
- **RMM feature expansion** enables smarter filtering beyond ATR, especially
  for high-volatility windows where ATR alone can be misleading.

Taken together, these efforts give us the tooling to extract more value from the
EMA crossover rather than repeatedly tightening the same ATR-based filter.
