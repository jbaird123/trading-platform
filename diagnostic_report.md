# AI Diagnostic Report

## Inefficient Take-Profit Exits Detected
$15.50 of potential profit was left on the table by take-profit exits, suggesting inefficient exit logic.

**Evidence:**
- avg_pnl_left_on_table_at_tp: 15.5
- threshold: 10.0
## Low Win Rate with High Trade Count
The strategy executed 650 trades with a low win rate (51.00%). This may indicate excessive trading or poor signal quality.

**Evidence:**
- n_trades: 650
- win_rate: 0.51
- thresholds:

```json
{
  "n_trades": 100,
  "win_rate": 0.55
}
```