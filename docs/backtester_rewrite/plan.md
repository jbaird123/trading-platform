# Backtester Rewrite Plan

This document tracks the objectives, scope, and progress for the backtester rewrite.

## Progress Summary
| Milestone | Status | Notes |
|-----------|--------|-------|
| M1 – Requirements & Architecture | ✅ Complete | Use checkboxes below to track completion |
| M2 – Execution Engine | ✅ Complete | |
| M3 – Risk & Portfolio | ✅ Complete | |
| M4 – Context/Reporting & Validation | ✅ Complete | |
| M5 – Full Validation & Cutover | ⚪ Not Started | |

## Guiding Goals
- **Deterministic timing semantics.** Clearly separate decision, execution, and stop timestamps so every component shares the same contract.
- **Modular layers.** Strategy, execution engine, portfolio manager, and risk/exit manager should communicate via well-defined interfaces (e.g., intents, fills, risk events).
- **Traceable context.** Every trade/brief snapshot must carry the exact decision metadata (time, price, feature payload) without recomputation or re-alignment hacks.
- **Testability-first.** Unit and integration tests should cover each module independently before we wire them together. Golden validations remain the final gate, but not the only safety net.

## Milestones

### M1 – Requirements & Architecture (Complete)
**Status:** ✅ Complete
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
- [x] All M1.1–M1.3 tasks complete.
- [x] Interfaces have type-hinted signatures captured in repo.
- [x] Architecture & sequence diagrams checked in.
- [x] Rollout strategy documented (feature flag → cutover plan).

## M1 Completion Checklist
- [x] Archive M1 artifacts under `docs/backtester_rewrite/completed/m1/`.
- [x] Document any deviations from the original plan (if none, state “None”).
- [x] Capture lessons learned / TODOs for M2 in `docs/backtester_rewrite/notes.md`.

### M2 – Execution Engine Implementation

**Developer Mandates (apply to M2–M5):**
- No bypassing static analysis (`mypy`, `ruff`) or coverage checks.
- No deferrals or “TODO later” placeholders.
- Follow fail-fast exception handling (`docs/coding_standards/exception_handling_policy.md`).
- Adopt TDD: write failing tests first, then implement code.
- Maintain 100% code coverage for new/changed modules.

#### M2.1 Test Infrastructure
- [x] Write contract tests for the ExecutionEngine protocol (submit/advance behavior).
- [x] Write contract tests for the clock abstraction (deterministic progression and alignment to bar close/open).
- [x] Build unit-test fixtures/builders for DecisionSnapshots, ExecutionIntents, FillEvents, and RiskExitEvents.

#### M2.2 Implementation
- [x] Build the new event/intent loop (driven by the clock) to satisfy the contract tests.
- [x] Integrate the authoritative system clock abstraction.
- [x] Add performance instrumentation (bars/sec, per-module timings) directly in the loop.
- [x] Provide fixtures to compare legacy vs. new loop outputs.

**Exit Criteria:**
- [x] Baseline throughput recorded (bars/sec on reference backtest).
- [x] Performance matches or exceeds legacy within 20%.
- [x] All tests passing.
- [x] Self-review checklist:
  - [x] All tasks complete (no deferrals).
  - [x] Every function has targeted tests (non-trivial assertions).
  - [x] Edge cases and expected failures covered.
  - [x] Code adheres to `principles.md` and `project_requirements.md`.
  - [x] Code is clean/readable and documented; no `mypy`/`ruff` violations.
**Status:** ✅ Complete

### M3 – Risk & Portfolio Integration
- [x] Adapt REM to emit structured `RiskExitEvent`s and consume clock signals.
- [x] Wire the portfolio FSM to handle intents/fills and apply costs centrally.
- [x] Ensure entry window serialization works with new interfaces.
- [x] Verify cost model remains centralized (no duplication).

**Exit Criteria:**
- [x] REM integration does not degrade throughput by >10%.
- [x] Profiling identifies top three bottlenecks for future optimization.
- [x] Portfolio FSM documented with explicit states/transitions.
- [x] Tests covering intent → fill → trade lifecycle passing.
- [x] Self-review checklist:
  - [x] All tasks complete (no deferrals).
  - [x] Every function has targeted tests (non-trivial assertions).
- [x] Edge cases and expected failures covered.
- [x] Code adheres to `principles.md` and `project_requirements.md`.
- [x] Code is clean/readable and documented; no `mypy`/`ruff` violations.

Performance & profiling notes (10k-bar micro-benchmark on 2021 M1 Pro):
- Portfolio-only loop averages 0.054 s (≈185k bars/sec). With the RiskExitAdapter wired (NoOp REM), the same loop averages 0.058 s (≈172k bars/sec), a 7.2% overhead—within the ≤10% regression budget. See `docs/backtester_rewrite/benchmarks.md` for the raw numbers and commands.
- cProfile shows the dominant hot spots to revisit when optimizing: `EventLoop.on_bar`, `BarClock.advance`, `NextBarExecutionEngine.advance_clock`, `RiskExitAdapter.evaluate`, and `EventLoop._extract_bar_series`. These functions consume the majority of cumulative time in the synthetic benchmark.
**Status:** ✅ Complete

### M4 – Context/Reporting & Validation Harness
- [x] Reconnect brief generation, analytics, and validation exporters to the new data flow.
- [x] Validate context snapshot schema with briefs and comparison exports.
- [x] Run smoke tests + targeted golden comparisons under feature flag.
- [x] Validate caching strategy for WFE/Monte Carlo reuse.

**Exit Criteria:**
- [x] Brief/reporting overhead measured and documented.
- [x] Golden comparison exporters produce explainable results (hash variances documented).
- [x] WFE/Monte Carlo caching strategy exercised.
- [x] Telemetry/logging validated for downstream consumers.
- [x] Self-review checklist:
  - [x] All tasks complete (no deferrals).
  - [x] Every function has targeted tests (non-trivial assertions).
  - [x] Edge cases and expected failures covered.
  - [x] Code adheres to `principles.md` and `project_requirements.md`.
  - [x] Code is clean/readable and documented; no `mypy`/`ruff` violations.
**Status:** ✅ Complete

Reporting notes:
- `ReportingPipeline` now wraps `generate_brief` with telemetry + validation exports, and `RunArtifactCache` allows Monte Carlo/WFE replays without recomputing briefs. Hash-based `ValidationHarness` provides deterministic comparison output for golden CSVs.
- Context builders were extracted into `backtester.context`, ensuring the new DecisionSnapshot flow shares the same timestamp/feature alignment as the legacy loop.
- Brief generation benchmark: 250 trades complete in 0.76s on the reference M1 Pro (see `benchmarks.md`). Telemetry entries logging `brief_seconds` + trade counts are emitted for every report to aid downstream monitoring.

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
- [ ] Self-review checklist:
  - [ ] All tasks complete (no deferrals).
  - [ ] Every function has targeted tests (non-trivial assertions).
  - [ ] Edge cases and expected failures covered.
  - [ ] Code adheres to `principles.md` and `project_requirements.md`.
  - [ ] Code is clean/readable and documented; no `mypy`/`ruff` violations.
**Status:** ⚪ Planned

## Current Focus
- [x] Draft requirements doc that enumerates all behavioral rules (entry timing, next-bar semantics, REM expectations, cache usage).
- [x] Identify pain points in the legacy code that the new design must avoid (e.g., implicit index shifting, duplicated context snapshots).
- [x] Decide on initial data structures (e.g., `DecisionSnapshot`, `ExecutionIntent`, `FillEvent`) so we can stub interfaces early.
- [x] Define performance targets, including:
  - **Primary:** ≤ 2 minutes for a 2-year / 5-minute backtest on reference hardware (2021 MacBook Pro, M1 Pro, 32 GB RAM).
  - **Stretch:** ≤ 1 minute for the same workload.
  - **Minimum acceptable:** ≤ 3 minutes (50% slower than target) with a remediation plan.
  - **Measurement:** Average of three runs after warm-up (excluding first-time compilation).
- [x] Instrument the prototype loop with timing hooks so benchmarks are ready once code exists.
- [x] Emit performance telemetry (bars/sec, per-module timings) into structured logs so that historical runs can be inspected whenever a regression or negative user experience is reported.
- [x] Define global feature “profiles” (e.g., full_campaign, profitability_ml, diagnostics, minimal) and document how each scenario selects the appropriate bundle.
- [x] Ensure strategies/ML modules declare their feature dependencies so the chosen profile can validate that all required features are present.
- [x] Reaffirm testing standards from `project_requirements.md`: adopt TDD, maintain 100% coverage, and require non-trivial tests that cover edge/failure cases.

## Notes / Open Questions

### Q1 – Rollout Strategy
- **Question:** How do we promote the new engine once validated?
- **Decision Deadline:** Before M2 begins.
- **Working Plan:** Build/validate on feature branch → once golden tests & benchmarks pass, merge into `main` and retire legacy code (no feature flag/canary needed).
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
