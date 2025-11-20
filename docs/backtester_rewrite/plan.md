# Backtester Rewrite Plan

This document tracks the objectives, scope, and progress for the backtester rewrite.

## Progress Summary
| Milestone | Status | Notes |
|-----------|--------|-------|
| M1 – Requirements & Architecture | 🟡 In Progress | Use checkboxes below to track completion |
| M2 – Execution Engine | ⚪ Not Started | |
| M3 – Risk & Portfolio | ⚪ Not Started | |
| M4 – Context/Reporting & Validation | ⚪ Not Started | |
| M5 – Full Validation & Cutover | ⚪ Not Started | |

## Guiding Goals
- **Deterministic timing semantics.** Clearly separate decision, execution, and stop timestamps so every component shares the same contract.
- **Modular layers.** Strategy, execution engine, portfolio manager, and risk/exit manager should communicate via well-defined interfaces (e.g., intents, fills, risk events).
- **Traceable context.** Every trade/brief snapshot must carry the exact decision metadata (time, price, feature payload) without recomputation or re-alignment hacks.
- **Testability-first.** Unit and integration tests should cover each module independently before we wire them together. Golden validations remain the final gate, but not the only safety net.

## Milestones

### M1 – Requirements & Architecture (Current)
**Status:** 🟡 In Progress
**Exit Criteria:** Behavioral requirements documented; interfaces defined with type hints; architecture & sequence diagrams approved; rollout decisions resolved.

#### M1.1 Behavioral Requirements
- [x] Document entry/exit timing semantics (same-bar vs. next-bar-open).
- [x] Enumerate timestamp types (`decision_time`, `execution_time`, `stop_check_time`) and propagation rules.
- [x] Specify context snapshot contract (structure, schema versioning, immutability).
- [x] Define explicit portfolio/position state machine.
- [x] Document gap handling and tie-break policies.
- [x] Identify cost application points and supported cost models.

#### M1.2 Interface Definitions
- [x] Draft `DecisionSnapshot` dataclass (fields + typing).
- [x] Draft `ExecutionIntent` model (intent type, execution model, risk metadata).
- [x] Draft `FillEvent` structure (timestamp, price, intent reference, costs).
- [x] Draft `RiskExitEvent` structure for REM outputs.
- [x] Define `ExecutionEngine` protocol (inputs, outputs, clock dependency).
- [x] Define `PortfolioManager` command API for intents/fills.

#### M1.3 Architecture & Review
- [x] Component diagram showing flow from DataHandler → Strategy → Execution Engine → Portfolio → REM → Reporting.
- [x] Sequence diagrams for: next-bar-open entry, intrabar stop detection, gating rejection.
- [x] Review diagrams/requirements with team; capture feedback.
- [x] Finalize rollout strategy before M2 begins.

**Rollout Strategy:** Build the new engine on this branch, validate via golden tests/performance benchmarks, then merge into `main` and retire the legacy backtester. No feature flags or staged canaries are required since the system is not yet in production.

**Exit Criteria:**
- [ ] All M1.1–M1.3 tasks complete.
- [ ] Interfaces have type-hinted signatures captured in repo.
- [ ] Architecture & sequence diagrams checked in.
- [ ] Rollout strategy documented (feature flag → cutover plan).

### M2 – Execution Engine Implementation
- [ ] Build the new event/intent loop with unit tests and contract tests.
- [ ] Integrate the authoritative system clock abstraction.
- [ ] Add performance instrumentation (bars/sec, per-module timings) directly in the loop.
- [ ] Create a benchmark suite comparing legacy vs. new execution.
- [ ] Provide fixtures to compare legacy vs. new loop outputs.

**Exit Criteria:**
- [ ] Baseline throughput recorded (bars/sec on reference backtest).
- [ ] Performance matches or exceeds legacy within 20%.
- [ ] All tests passing.
- [ ] Self-review against `principles.md` completed.
**Status:** ⚪ Planned

### M3 – Risk & Portfolio Integration
- [ ] Adapt REM to emit structured `RiskExitEvent`s and consume clock signals.
- [ ] Wire the portfolio FSM to handle intents/fills and apply costs centrally.
- [ ] Ensure entry window serialization works with new interfaces.
- [ ] Verify cost model remains centralized (no duplication).

**Exit Criteria:**
- [ ] REM integration does not degrade throughput by >10%.
- [ ] Profiling identifies top three bottlenecks for future optimization.
- [ ] Portfolio FSM documented with explicit states/transitions.
- [ ] Tests covering intent → fill → trade lifecycle passing.
**Status:** ⚪ Planned

### M4 – Context/Reporting & Validation Harness
- [ ] Reconnect brief generation, analytics, and validation exporters to the new data flow.
- [ ] Validate context snapshot schema with briefs and comparison exports.
- [ ] Run smoke tests + targeted golden comparisons under feature flag.
- [ ] Validate caching strategy for WFE/Monte Carlo reuse.

**Exit Criteria:**
- [ ] Brief/reporting overhead measured and documented.
- [ ] Golden comparison exporters produce explainable results (hash variances documented).
- [ ] WFE/Monte Carlo caching strategy exercised.
- [ ] Telemetry/logging validated for downstream consumers.
**Status:** ⚪ Planned

### M5 – Full Validation & Cutover
- [ ] Execute entire validation suite with the new engine.
- [ ] Run parallel comparisons vs. legacy outputs; reconcile differences.
- [ ] Roll through parallel → canary → default-on → legacy removal per rollout plan.
- [ ] Add performance regression tests to CI.

**Exit Criteria:**
- [ ] Full validation suite hits performance target (≤ 2 minutes for 2-year/5-min run, ≤ 3 minutes worst-case).
- [ ] Legacy backtester gated behind feature flag or removed per plan.
- [ ] Documentation updated (README/handbooks) to reflect new engine.
- [ ] Post-cutover monitoring plan in place.
**Status:** ⚪ Planned

## Current Focus
- Draft requirements doc that enumerates all behavioral rules (entry timing, next-bar semantics, REM expectations, cache usage).
- Identify pain points in the legacy code that the new design must avoid (e.g., implicit index shifting, duplicated context snapshots).
- Decide on initial data structures (e.g., `DecisionSnapshot`, `ExecutionIntent`, `FillEvent`) so we can stub interfaces early.
- [ ] Define performance targets, including:
  - **Primary:** ≤ 2 minutes for a 2-year / 5-minute backtest on reference hardware (2021 MacBook Pro, M1 Pro, 32 GB RAM).
  - **Stretch:** ≤ 1 minute for the same workload.
  - **Minimum acceptable:** ≤ 3 minutes (50% slower than target) with a remediation plan.
  - **Measurement:** Average of three runs after warm-up (excluding first-time compilation).
- [ ] Instrument the prototype loop with timing hooks so benchmarks are ready once code exists.
- [ ] Emit performance telemetry (bars/sec, per-module timings) into structured logs so that historical runs can be inspected whenever a regression or negative user experience is reported.
- [ ] Define global feature “profiles” (e.g., full_campaign, profitability_ml, diagnostics, minimal) and document how each scenario selects the appropriate bundle.
- [ ] Ensure strategies/ML modules declare their feature dependencies so the chosen profile can validate that all required features are present.

## Notes / Open Questions

### Q1 – Rollout Strategy
- **Question:** Feature flag vs. full cutover?
- **Decision Deadline:** Before M2 begins.
- **Working Plan:** Feature flag → parallel comparison → default-on with escape hatch → remove legacy.
- **Owner:** Joe + architecture leads.

### Q2 – Strategy Config Compatibility
- **Question:** Maintain backward compatibility or allow breaking changes?
- **Decision Deadline:** Before M2 begins.
- **Working Plan:** Keep existing entry/exit rule syntax; allow documented changes for timing metadata with validation tooling to compare old/new outputs.
- **Owner:** Strategy/platform owners.

### Q3 – Telemetry & Debugging
- **Question:** What observability is mandatory?
- **Decision Deadline:** Before M2 implementation.
- **Must-Haves:** Structured logs for decision→intent→fill, performance metrics, debug dumps of decision snapshots, hooks for legacy vs. new comparisons.
- **Owner:** DevOps + lead developer.

## Takeaways
- Document everything: the existing system's behavior is complicated; capturing it now prevents re-learning later.
- Keep requirements, design artifacts, and decisions in-repo for easy reference across sessions.
- Plan incremental rollout steps (parallel run, canary, full cutover) early to avoid surprises.
- Performance is a first-class requirement: architectural choices must enable vectorization, caching, and parallel sweeps without introducing look-ahead bias. Every milestone should include performance instrumentation and benchmarks so regressions are caught immediately.

_(Update this plan as we make decisions, complete milestones, or discover new work.)_
