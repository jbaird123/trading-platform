# RMM Hysteresis Behavior Contract

This note defines the runtime contract for applying hysteresis inside the
Regime Market Manager (RMM). It guides the implementation in
`RMMEngine` and the accompanying tests that validate requirement
`[RMM-4.7]`.

## Purpose
- Prevent rapid label flipping when indicator inputs drift around a boundary.
- Give the Portfolio Manager and Execution Layer predictable, serializable
  regime state.
- Ensure any ML or analytics workflow receives both the raw regime signal and
  the hysteresis-adjusted label.

## Configuration Inputs
The hysteresis block in `RMMConfig` supplies the knobs that control stickiness.

- `min_bars`: `int >= 0`. Bars a label must persist before a change is allowed.
- `cooldown_bars`: `int >= 0`. Bars to wait after a switch before another
  change is permitted.

Both fields default to `0`, which makes hysteresis a no-op. Strategies can tune
them per configuration at runtime.

## State Tracked Per Timeframe
For each bar evaluated at the RMM timeframe, the engine must maintain:

- `active_label`: label currently exposed to downstream components.
- `active_confidence`: confidence associated with `active_label`.
- `bars_in_state`: number of completed bars since the label last changed.
- `cooldown_remaining`: bars left in the cooldown period (zero when inactive).
- `raw_label` / `raw_confidence`: direct output from the rule evaluation.

These values must be serializable so the Execution Layer can resume without
losing hysteresis continuity.

## Evaluation Flow
1. **Evaluate Rules**
   Compute indicator features and evaluate regime rule blocks in order,
   producing `raw_label` and `raw_confidence`. If no rule matches, use
   `unknown` with confidence `0.0`.

2. **Bootstrap State**
   If `active_label` is unset (start of run) and `raw_label` is not `unknown`,
   accept the raw label immediately and reset counters.

3. **Cooldown Enforcement**
   If `cooldown_remaining > 0` and `raw_label != active_label`, ignore the raw
   label, decrement `cooldown_remaining`, increment `bars_in_state`, and keep
   the current label.

4. **Minimum Hold Enforcement**
   If `raw_label != active_label` and `bars_in_state < min_bars`, ignore the
   raw label, increment `bars_in_state`, and leave cooldown unchanged.

5. **Label Transition**
   When neither cooldown nor min-bars prevent a switch:
   - Set `active_label = raw_label`.
   - Set `active_confidence = raw_confidence`.
   - Reset `bars_in_state = 0`.
   - Set `cooldown_remaining = cooldown_bars`.

6. **Label Persistence**
   When `raw_label == active_label`, update `active_confidence` to the latest
   value, increment `bars_in_state`, and, if applicable, decrement
   `cooldown_remaining` until it reaches zero.

The resulting DataFrame should expose both the raw and adjusted labels so
downstream consumers can analyze hysteresis effects.

## Testing Expectations
- Synthetic sequences that oscillate around a threshold must show fewer label
  transitions when hysteresis is applied.
- Cooldown logic must block immediate flips in either direction.
- `bars_in_state` and `cooldown_remaining` must persist across projection
  (`project_to_index`) to guarantee Execution Layer parity.
- Tests must cover cases where hysteresis is disabled to prove there is no
  unintended behavior change.
- Brief outputs and CSV exports now surface both the raw and hysteresis-adjusted
  regime fields (`raw_label`, `raw_confidence`, `bars_in_state`,
  `cooldown_remaining`, and `hysteresis.*`). The JSON brief schema has been
  updated accordingly (`src/trading_platform/reporting/schemas/brief.schema.json`).

Adhering to this contract keeps the runtime, documentation, and tests aligned
as hysteresis moves from plan to production.
