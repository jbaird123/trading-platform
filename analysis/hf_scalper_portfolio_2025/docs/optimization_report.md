# HF Scalper Optimization Report

## Goal
Minimize Max Drawdown Duration to < 14 days.

## Best Result
*   **Configuration**: BB Std=3.0, RSI<5, StopLoss=10 pips.
*   **Max Drawdown Duration**: 71 Days (Reduced from 154).
*   **Total Profit**: +366 pips (Jan-Oct 2022).
*   **Trade Frequency**: 758 trades (~3.5/day).

## Conclusion
Optimization cut the drawdown in half (154 -> 71 days), but **failed** to meet the 14-day target. The strategy became "starved" for signals (only 3.5 trades/day) due to the strict filters required to survive the volatility.

## Recommendation
Evaluation proves that a **single** strategy cannot achieve < 14 day drawdowns in all regimes. The 71-day drawdown occurred during the strongest trends of 2022.
**Solution**: Deploy this Mean Reversion strategy ALONGSIDE a Trend Following Scalper.
