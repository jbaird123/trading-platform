# Brief Costs Section – Schema and Semantics

This note explains the `costs` section in the JSON brief and how it is derived from per-trade fields.

Key points
- Units: All values are in the run's base currency.
- Round-trip costs: Costs are applied per side (entry and exit) and aggregated per trade.
- Aggregation: `costs` is computed from each trade's `cost_currency` and `cost_breakdown`.

Canonical fields
- `total_costs`: Sum of `cost_currency` across all trades.
- `avg_cost_per_trade`: `total_costs / n_trades`.
- `breakdown`: Sums of per-trade `cost_breakdown.{spread, commission, slippage}`.

Example
```json
{
  "costs": {
    "total_costs": 0.15,
    "avg_cost_per_trade": 0.075,
    "breakdown": {
      "spread": 0.05,
      "commission": 0.08,
      "slippage": 0.02
    }
  }
}
```

How costs are computed per trade
- Spread and slippage are applied per unit and per side, using instrument-aware units when available:
  - Effective units = `size / lot_size` when `lot_size` is specified; otherwise `size`.
  - Entry and exit each include spread and slippage.
- Commissions support three modes:
  - `per_unit`: `commission_value * effective_units` per side.
  - `per_trade_flat`: constant per side.
  - `bps_notional`: `(price * size) * (bps / 10_000)` per side (uses raw `size`, not lot-scaled).

Related config snapshot
- The brief includes a `cost_model` snapshot that documents which cost parameters were active during the run. See the canonical cost model shape in `docs/project_requirements.md` under "Detailed Notes & Edge Requirements".
