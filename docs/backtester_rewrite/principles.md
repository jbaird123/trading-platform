# Backtester Rewrite Principles & Requirements

Use this document to capture architectural principles, coding rules, and behavioral requirements that must hold throughout the rewrite. Add new items as they surface so the entire effort stays aligned.

## Core Principles
- **Fail fast.** Prefer explicit errors over defensive catch-alls; unexpected data or states should abort immediately so problems are visible. (See `docs/coding_standards/exception_handling_policy.md`.)
- **Strict module boundaries.** Design each component (data prep, strategy, execution engine, portfolio, REM, reporting) to communicate only through defined interfaces. Future separation into standalone services should require minimal refactoring.
- **Simplicity over optionality.** Avoid sprawling optional parameters or mode flags. If a use case is necessary, model it via distinct interfaces/types rather than boolean switches.
- **Deterministic contracts.** Every interface must specify what timestamps, prices, and payloads it expects/produces so there is zero implicit shifting or re-alignment.
- **Unambiguous bar metadata.** Every time series handed to downstream modules must expose explicit `open_time` and `close_time` columns in addition to the label (always set to the bar’s open). No component should ever have to “guess” whether a value represents open or close, nor should we rely on shifting/ffill tricks to align feature caches—timestamps make alignment canonical.
- **Testability by construction.** Each module should be unit-testable in isolation with clear seams for mocks/fakes; large integration tests then stitch the pieces together.
- **Authoritative system clock.** All modules must derive “current time” from a single clock abstraction injected by the orchestrator. In live trading the clock maps to wall time; in simulation the backtester advances it per bar. No component should infer time by reading `datetime.utcnow()` or deriving it from labels on its own. This ensures deterministic sequencing and catches any attempt to operate on T‑1/T‑2 accidentally.
- **Performance without look-ahead.** Optimize for higher throughput (vectorization, caching, parallel sweep execution) while guaranteeing no look-ahead bias. Any precomputation or batching must respect the authoritative clock and expose only data available at that simulated time. Track performance (bars/sec, per-module timing) so regressions are visible.

## Performance Anti-Patterns to Avoid
The legacy backtester surfaced several bottlenecks we must not replicate:
1. **Serial re-materialization:** Rebuilding context snapshots from scratch each bar instead of capturing immutable snapshots once and reusing them.
2. **Alignment fixups:** Shifting/reindexing DataFrames to “guess” alignment. Explicit timestamps must make all joins trivial.
3. **Per-component recomputation:** Indicators/risk thresholds recalculated independently by each module. Compute once per bar/batch and share.
4. **No batching:** Processing one bar at a time with no opportunity for vectorization or batched/gated evaluations.
5. **Hidden state:** Modules pulling timestamps or session info from globals leads to inconsistent timelines and race conditions.

## Performance Optimization Levers
The new architecture enables specific accelerators, each with the constraint that they must respect the system clock and be backed by equivalence tests:
1. **Batch indicator computation.** Compute strategy/global features once per bar batch instead of per component.
2. **Immutable snapshot reuse.** Cache decision snapshots/feature bars for reuse across WFE windows, Monte Carlo runs, and Monte Carlo seeds.
3. **Parallel sweep execution.** Run Monte Carlo seeds or parameter grid cells in separate processes/workers using isolated data snapshots.
4. **Vectorized gating.** Evaluate gating policies on series/batches instead of per bar when rules allow it.
5. **Pluggable execution variants.** Provide stripped-down engines (e.g., “no REM”, “no reporting”) for rapid exploratory sweeps while keeping the default engine full featured.

## Behavioral Requirements (Living List)

> **Note:** Requirement IDs use the `BT-10.x` namespace so they can be copied directly into `docs/project_requirements.md` later without renumbering.

### Canonical Timestamps
- **Decision Time (`decision_time`).** Always the bar’s `close_time` when the strategy made its decision.
- **Execution Time (`execution_time`).** Actual fill timestamp (bar close for immediate fills, next bar open for deferred fills). Stored on trades and contexts separately from decision time.
- **Stop Check Time (`stop_check_time`).** Timestamp used when REM evaluates exits—equal to the parent bar’s clock time (usually the bar open/close). Even if REM inspects 1-minute zoom data internally, it reports exits using the parent bar timestamp so comparisons to TradingView remain straightforward.
- **Available-at Time (`available_time`).** Timestamp associated with any cached global feature row; must match a bar close so that lookups are unambiguous.

### Timing & Execution Semantics
- **[BT-10.1]** Every component operates on explicit timestamps: `decision_time`, `execution_time`, `stop_check_time`. These values must be carried in all intents/events.
- **[BT-10.2]** No implicit index shifting or inferred alignment. Any transformation of a DataFrame must declare whether it is aligned to bar open or bar close.
- **[BT-10.3]** Next-bar-open execution semantics are canonical: decision at bar *N* close → fill intent scheduled for bar *N+1* open → REM still evaluates intrabar events starting on bar *N+1*.
- **[BT-10.4]** Stop/TP checks must specify whether they rely on intrabar zoom data or bar-level OHLC only; ambiguity resolutions must be deterministic.
- **[BT-10.4a]** Unless explicitly implemented, only the `next_bar_open` execution model is allowed. Requesting any unsupported execution model must fail fast (no silent fallback).
- **[BT-10.4b]** Strategy-driven exits respect the execution model (defer to next bar open when configured), but REM exits always execute immediately at the stop/TP hit price using intrabar data when available.
- **[BT-10.4c]** Decision timestamps are always derived from the bar’s `close_time`, but recorded entry/exit times must reflect the actual fill timestamp (bar close for same-bar fills, bar open for next-bar fills). Matching TradingView comparisons is the ultimate arbiter: if recorded timestamps prevent parity, adjust so that entries/exits align with how TradingView labels them (typically bar open for fills that occur at the next bar).

### Context & Metadata Contracts
- **[BT-10.5]** `context_at_entry` / `context_at_exit` payloads are part of the external API. If structural changes are introduced in the future, versioning should be added, but the initial implementation can treat the schema as single-version.
- **[BT-10.6]** Decision snapshots must capture strategy features, global features, regime metadata, risk levels, and `decision_time` (ISO-8601). No partial snapshots are allowed.
- **[BT-10.7]** Once captured, context snapshots are immutable. Late enrichment is prohibited; any additional data should be stored separately with explicit provenance.

#### Context Snapshot Contract
Every context snapshot must conform to the following structure (additive fields allowed, but core keys must exist):
- `decision_time`: ISO timestamp from the bar’s close.
- `decision_price`: Price used when the strategy decided (bar close).
- `strategy_features`: Map of strategy-specific indicators/features used for that decision.
- `global_features`: Map of global/market-wide features aligned to the same timestamp.
- `regime` (optional): Regime metadata (label, confidence, hysteresis info).
- `risk`: Snapshot of risk calculations at decision time (entry price, initial stop/take-profit levels, other REM fields).
- `gating`: Result of profitability gating or other policy decisions (including notes for why an entry was skipped).
- `extras`: Any additional metadata must be namespaced (e.g., `diagnostics`, `ai_context`) and documented.

`context_at_entry` stores the decision snapshot as-is. `context_at_exit` stores the exit-time metadata but must retain the original `decision_time`/`decision_price` so downstream tooling can reconcile entries/exits even if the exit happens on a later bar.

#### DecisionSnapshot Dataclass (Conceptual)
When defining the new execution interfaces, use a type with (at minimum) the following fields:
```python
@dataclass(frozen=True)
class DecisionSnapshot:
    timestamp: datetime  # decision_time (bar close)
    price: float         # decision_price (bar close)
    side: Literal["long", "short"]
    size: float
    bar_index: int | None  # optional reference to the source bar
    strategy_features: dict[str, float | None]
    global_features: dict[str, float | None]
    regime: dict[str, Any] | None
    risk: dict[str, Any]  # e.g., entry price, initial stop/tp
    gating: dict[str, Any] | None
    context: dict[str, Any] = field(default_factory=dict)  # namespace for extras
```
This object should be immutable and serializable so it can be persisted in briefs and reused across WFE windows or Monte Carlo runs.

#### ExecutionIntent Model (Conceptual)
An intent describes what the strategy wants the execution engine / portfolio manager to do based on a specific decision snapshot:
```python
@dataclass(frozen=True)
class ExecutionIntent:
    decision: DecisionSnapshot
    intent_type: Literal["enter_long", "enter_short", "exit", "hold"]
    execution_model: Literal["next_bar_open"]  # future-proof for other models
    risk_overrides: dict[str, Any] | None  # optional adjustments to stops/TPs
    notes: str | None  # e.g., gating reason for skips
```
- Sizing is determined by the Portfolio Manager; the intent does not carry position size.
- Intents are immutable records; once created they should not be edited—any change in strategy opinion produces a new intent.

#### FillEvent Model (Conceptual)
When an intent executes, the engine emits a fill describing what happened:
```python
@dataclass(frozen=True)
class FillEvent:
    intent: ExecutionIntent
    timestamp: datetime        # actual fill time (bar open for next_bar_open)
    price: float               # mid-price before costs
    size: float                # final size applied by PortfolioManager
    costs: dict[str, float]    # e.g., {"spread": 0.0002, "commission": 1.0}
    reason: Literal["entry", "strategy_exit", "stop_loss", "take_profit"]
```
- The fill references the originating intent so briefs and diagnostics can trace decisions to executions.
- Costs are computed immediately after the fill (via `CostModel`) and stored on the fill/trade record to keep gross/net reconciliations transparent.

#### RiskExitEvent Model (Conceptual)
REM returns structured events indicating when a stop-loss or take-profit triggers:
```python
@dataclass(frozen=True)
class RiskExitEvent:
    timestamp: datetime              # bar time when the stop triggered
    price: float                     # exit price (mid) determined by REM
    reason: Literal["stop_loss", "take_profit", "trailing_stop"]
    decision: DecisionSnapshot       # snapshot of the original entry decision
    details: dict[str, Any] | None   # e.g., which rule fired, ambiguity notes
```
- The execution engine converts a `RiskExitEvent` into a `FillEvent` immediately (ignoring deferred execution models), so REM stops always execute as soon as they are triggered.

### Execution Engine Protocol
The execution engine is the orchestrator between DecisionSnapshots/ExecutionIntents and actual FillEvents. At a minimum it must expose:
```python
class ExecutionEngine(Protocol):
    def submit_intent(self, intent: ExecutionIntent) -> None: ...
    def submit_risk_event(self, risk_event: RiskExitEvent) -> None: ...
    def advance_clock(self, current_bar: BarData) -> Iterable[FillEvent]: ...
```
- `submit_intent` queues an intent (entry/exit) along with its decision context.
- `submit_risk_event` receives REM-triggered exits, which should be executed immediately (returning a FillEvent the same bar).
- `advance_clock` is called once per bar (respecting the authoritative clock) and returns any FillEvents that occur (e.g., deferred next-bar-open fills). The caller hands each FillEvent to the PortfolioManager.

Implementation notes:
- Execution Engine must be stateless with respect to costs; it only produces mid-price fills. PortfolioManager applies spreads/commissions/slippage.
- Only `next_bar_open` is implemented initially; the protocol is designed to allow additional execution models later without modifying callers.

### PortfolioManager Command API
The Portfolio Manager needs explicit entry/exit commands in terms of intents and fills:
- `submit_intent(intent: ExecutionIntent) -> CommandResult`: validates gating, per-side limits, and transitions the relevant position(s) to `ENTRY_PENDING` or `EXIT_PENDING`. Returns a descriptor indicating whether the intent was accepted, rejected, or deferred.
- `apply_fill(fill: FillEvent) -> None`: consumes FillEvents (both entries and exits) to transition positions (`ENTRY_PENDING → OPEN`, `OPEN → EMPTY`, etc.) and record trades.
- `ingest_risk_event(risk_event: RiskExitEvent) -> None`: optional helper when REM-triggered events bypass the execution engine; should produce an immediate FillEvent internally.
- `serialize_state() / restore_state()`: persist/restore the FSM for live trading resiliency.

Command results should be structured (e.g., `{ "status": "accepted", "reason": None }`) so diagnostics can explain why intents were skipped (gating, position caps, etc.). The API keeps strategy logic and execution separated while supporting multi-position operation.

### State & Portfolio Management
- **[BT-10.8]** Entry window state must be serializable/deserializable so live trading can restart mid-window without loss.
- **[BT-10.9]** Portfolio and position transitions must follow an explicit finite-state machine (idle → pending → open → closing), avoiding ad hoc booleans.
- **[BT-10.10]** The single-position constraint must either be guaranteed by design or the new system must intentionally support multi-position workflows. There is no “implicit” assumption.

#### Position State Machine
Every position (long or short) follows the same lifecycle:
1. `EMPTY` – no active position.
2. `ENTRY_PENDING` – entry intent approved but execution deferred (e.g., next bar open). Stores the `DecisionSnapshot`.
3. `OPEN` – position is live; REM and strategy exits act on this state. Multiple positions per side are allowed if limits permit.
4. `EXIT_PENDING` – strategy exit triggered but execution deferred. REM exits bypass this and close immediately.

Transitions:
- `EMPTY → ENTRY_PENDING`: entry signal + gating approval.
- `ENTRY_PENDING → OPEN`: execution engine fills (next bar open).
- `OPEN → EXIT_PENDING`: strategy exit deferred per execution model.
- `EXIT_PENDING → EMPTY`: execution model fills the exit.
- `OPEN → EMPTY`: REM exit (stop/TP) triggers immediately.
- `OPEN → OPEN`: updates to stops/risk metrics without changing state.
- `ENTRY_PENDING → EMPTY`: entry window expires or a cancelling event (e.g., opposite-side signal) voids the pending intent.

Portfolio Manager tracks a collection of these state machines (one per open intent/position) and enforces per-side limits by counting how many positions are in `ENTRY_PENDING` or `OPEN` states.

### Data & Feature Handling
- **[BT-10.11]** DataHandler’s `open_time`/`close_time` columns remain the source of truth for bar timing; all downstream consumers must reference them instead of recomputing.
- **[BT-10.12]** Global-feature caches must declare their alignment (e.g., “values valid at bar close”). Joining logic may not silently shift indexes to guess alignment.
- **[BT-10.13]** Any DataFrame handed to a strategy or gateway must specify whether its label is the bar open, close, or other reference. Strategies must never discover this via heuristics.

### Risk & Exit Management
- **[BT-10.14]** REM returns structured exit events `{price, reason, timestamp, method, metadata}` rather than raw floats; execution engine decides how to apply them.
- **[BT-10.15]** Gap handling and tie-break policies (e.g., `stop_then_tp`) must be explicitly configured and enforced consistently.
- **[BT-10.16]** Ambiguity resolution via 1-minute zoom must be deterministic, logged, and testable with golden fixtures. If zoom data is unavailable, REM must raise rather than guess.

#### Gap Handling & Tie-Break Policy
- **Gap Fills:** When the next bar opens beyond a stop or take-profit level, the fill price is the bar’s open (worst-case realistic fill). Decision metadata remains tied to the preceding bar close, but `exit_time`/`entry_time` reflect the bar open.
- **Ambiguity Analyzer:** If a bar’s range contains both stop and take-profit levels—or if a trailing stop moves into the bar’s range intrabar—the REM must zoom down to finer data (e.g., 1-minute bars) and process them sequentially until one condition is clearly met first. Only if the zoomed bar still hits competing levels within the same minute do we fall back to the configured tie-break order (default `stop_then_tp`). This mirrors the current “ambiguity analyzer” behavior and must be preserved.
- **REM vs. Strategy Exits:** REM exits ignore execution model and fire immediately when the stop/TP condition occurs (subject to ambiguity resolution). Strategy exits honor the execution model and may defer to the next bar open.

### Cost & Execution Model
- **[BT-10.17]** PortfolioManager (or a dedicated cost service) is the only place where spreads, commissions, and slippage are applied. No other module may adjust fills for costs.
- **[BT-10.18]** Execution engines pass intents/fills but never duplicate cost logic; they simply forward cost configuration to the portfolio layer.

#### Cost Application Rules
- All trading costs (spread, commission, slippage) are computed through `CostModel` inside PortfolioManager. Strategies, REM, and execution engines operate on mid prices and do **not** adjust fills themselves.
- Supported commission modes mirror today’s cost model: per-unit, per-trade flat, and basis-points-on-notional. Any new mode must be added to `CostModel` so both backtests and live trading stay in sync.
- Spread is applied via adjusted fill prices (`get_entry_price`, `get_exit_price`), slippage/commission through `compute_entry_cost`/`compute_exit_cost`, and totals are recorded on each `Trade`.
- Cost metadata (breakdown of spread/commission/slippage) must be preserved so downstream reporting (briefs, analytics) can reconcile net vs. gross PnL.

### Validation & Testing
- **[BT-10.19]** Golden validations remain authoritative. Any intentional deviations must be documented with rationale and migration tooling.
- **[BT-10.20]** Each module requires unit tests covering valid/invalid inputs before it participates in integration suites.
- **[BT-10.21]** Public interfaces must have contract tests or fixtures that assert required fields and failure modes.
- **[BT-10.25]** Any optimization relying on caching/batching/precomputation must include tests proving there is no look-ahead bias (results must match serial per-bar computation exactly).
- **[BT-10.26]** Performance instrumentation (bars/sec, per-module timing) is part of the execution loop. Regression tests must fail if throughput drops >20% without documented justification.
- **[BT-10.27]** Follow TDD principles: write failing tests before implementing new behavior, and keep the fast test suite green as you iterate.
- **[BT-10.28]** Maintain 100% code coverage (line and branch) for backtester modules. Any exclusions must be explicitly justified and documented.
- **[BT-10.29]** Tests must be non-trivial: make specific assertions proving correctness, not merely that functions run without error.
- **[BT-10.30]** Tests must include edge cases and expected failures (e.g., None inputs, empty datasets, boundary conditions, invalid execution models).
- **[BT-10.31]** Every test must document its intent (docstring or comment) describing what behavior is being verified and why it matters.

### Extensibility & Future-Proofing
- **[BT-10.22]** Design workflows so multi-position support can be added without a wholesale rewrite (e.g., treat “position” as a collection).
- **[BT-10.23]** Execution model plug-ins (current bar close, next bar open, limit orders) should be swappable via interfaces, not conditionals.
- **[BT-10.24]** Components must be deployable as separate services in the future; avoid tight coupling to in-process assumptions.

_(Continue appending to this list as new requirements emerge. Reference IDs can align with the broader project requirements doc for traceability.)_
#### Gap Handling & Tie-Break Policy
- **Gap Fills:** When the next bar opens beyond a stop or take-profit level, the fill price is the bar’s open (worst-case realistic fill). Decision metadata remains tied to the preceding bar close, but `exit_time`/`entry_time` reflect the bar open.
- **Ambiguity Analyzer:** If a bar’s range contains both stop and take-profit levels—or if a trailing stop moves into the bar’s range intrabar—the REM must zoom down to finer data (e.g., 1-minute bars) and process them sequentially until one condition is clearly met first. Only if the zoomed bar still hits competing levels within the same minute do we fall back to the configured tie-break order (default `stop_then_tp`). This mirrors the current “ambiguity analyzer” behavior and must be preserved.
- **REM vs. Strategy Exits:** REM exits ignore execution model and fire immediately when the stop/TP condition occurs (subject to ambiguity resolution). Strategy exits honor the execution model and may defer to the next bar open.
