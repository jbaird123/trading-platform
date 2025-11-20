# Backtester Rewrite Architecture Notes

## Component Diagram
```mermaid
graph LR
    DH[DataHandler (session-aware bars)] --> STR[Strategy Engine & features]
    STR --> SNAP[DecisionSnapshot]
    SNAP --> INTENTS[ExecutionIntent Queue]
    INTENTS --> EE[Execution Engine]
    EE -->|FillEvents| PM[Portfolio Manager (FSM + CostModel)]
    SNAP --> REM[Risk Exit Manager]
    REM -->|RiskExitEvents| EE
    PM --> RPT[Reporting/Briefs]
    PM --> VAL[Validation/Diagnostics]
```

**Component responsibilities**
- **DataHandler:** supplies bars with explicit `open_time`/`close_time`, handles resampling and feature cache alignment.
- **Strategy Engine:** computes strategy/global features, evaluates entry/exit rules, emits `DecisionSnapshot`s (with risk/gating metadata) plus `ExecutionIntent`s.
- **Execution Engine:** accepts intents/risk events, advances with the authoritative clock, and produces `FillEvent`s according to the execution model (initially `next_bar_open` only).
- **Risk Exit Manager:** evaluates stop/take-profit/trailing rules per bar (with intrabar zoom when required) and emits `RiskExitEvent`s that bypass deferred execution.
- **Portfolio Manager:** maintains per-position FSMs, enforces gating/limits, applies all trading costs, records trades, and feeds reporting/validation layers.
- **Reporting/Validation:** consume the trades, contexts, and telemetry for briefs, diagnostics, and golden comparisons.

## Sequence Diagrams

### Next-Bar-Open Entry Flow
```mermaid
sequenceDiagram
    participant STR as Strategy Engine
    participant EE as Execution Engine
    participant PM as Portfolio Manager

    STR->>STR: compute features & decision snapshot
    STR->>STR: apply gating (RMM)
    STR->>EE: submit ExecutionIntent (enter_long/short, next_bar_open)
    EE->>PM: notify intent accepted (PM moves to ENTRY_PENDING)
    loop per bar
        EE->>PM: advance_clock(current_bar)
        alt next bar open reached
            EE->>EE: produce FillEvent (timestamp = bar open)
            EE->>PM: deliver FillEvent
            PM->>PM: apply fill (ENTRY_PENDING → OPEN), apply costs
        else no fill
            EE->>PM: no fills this bar
        end
    end
```

### Intrabar Stop Detection Flow
```mermaid
sequenceDiagram
    participant REM as Risk Exit Manager
    participant EE as Execution Engine
    participant PM as Portfolio Manager
    participant DH as DataHandler

    loop per bar
        REM->>DH: request current bar & intrabar data
        REM->>REM: evaluate stop/tp (zoom if ambiguous)
        alt stop triggers
            REM->>EE: emit RiskExitEvent(stop_loss)
            EE->>PM: convert to FillEvent immediately
            PM->>PM: close position (OPEN → EMPTY), apply costs, record trade
        else no stop
            REM->>REM: no action
        end
    end
```

### Gating Rejection Flow
```mermaid
sequenceDiagram
    participant STR as Strategy Engine
    participant RMM as Gating/Risk Module
    participant PM as Portfolio Manager

    STR->>RMM: evaluate decision snapshot
    RMM-->>STR: gating result (e.g., blocked, allowed_sides)
    STR->>PM: submit ExecutionIntent with gating metadata
    alt gating allowed
        PM->>PM: move to ENTRY_PENDING (window opens)
    else gating blocked
        PM->>PM: record rejection (status=blocked, reason)
        PM-->>STR: intent rejected (optional feedback)
    end
    note over PM,RMM: Entry window remains active until it expires or gating clears, per FSM.
```
