# Trades Cost Breakdown – Semantics and Roll-up

This note explains how `trades[].cost_breakdown` is produced and how it rolls up into the brief-level `costs` section.

Key points
- Per side application: Costs apply on entry and exit; `cost_breakdown` reflects the round-trip totals for a trade.
- Units: Values are in the run’s base currency.
- Optional on Trade: When a trade lacks `cost_breakdown`, it is treated as zeros for aggregation.
- Brief placeholders: In the JSON brief, trades missing a breakdown are serialized with `{spread: 0, commission: 0, slippage: 0}` to keep the schema uniform.

Fields
- `spread`: Sum of entry and exit spread costs.
- `commission`: Sum of entry and exit commissions.
- `slippage`: Sum of entry and exit slippage costs.

Aggregation behavior
- `brief.costs.total_costs` sums `trade.cost_currency` across all trades.
- `brief.costs.breakdown` sums `trade.cost_breakdown` fields where present; missing breakdowns contribute zeros.

Example
```json
{
  "trades": [
    { "cost_breakdown": {"spread": 0.02, "commission": 0.03, "slippage": 0.01} },
    { "cost_breakdown": {"spread": 0.00, "commission": 0.00, "slippage": 0.00} }
  ],
  "costs": {
    "total_costs": 0.10,
    "avg_cost_per_trade": 0.05,
    "breakdown": {"spread": 0.02, "commission": 0.03, "slippage": 0.01}
  }
}
```

Related references
- Canonical cost model shape: see `docs/project_requirements.md` (Detailed Notes & Edge Requirements).
- Brief costs aggregation: see `docs/examples/brief_costs_section.md`.
