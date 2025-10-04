# Code Review: `feature/pnl-reporting-clarity` (Tasks 8-11)

**Verdict: Approved**

All changes related to the implementation of unrealized PnL are implemented correctly, fully tested, and adhere to all project standards. No further action is required.

## Review Summary
- **Task Completion**: All specified tasks were implemented precisely as described.
- **Testing**: The new functionality is covered by comprehensive and well-designed tests that verify correctness for long, short, winning, and losing scenarios.
- **Architecture**: The changes are architecturally sound and correctly isolated within the portfolio management domain.
- **Code Quality**: The code is clean, well-commented, and highly readable.

## Suggested Commit Message

```
feat(portfolio): Implement realistic unrealized PnL

Implements the calculation for unrealized PnL for open positions.

- Adds `unrealized_pnl` field to the `Position` object.
- Calculates unrealized PnL in `PortfolioManager` on each bar update,
  correctly accounting for the full spread cost by using the bid/ask
  exit price.
- This ensures that the mark-to-market value of an open position
  reflects the immediate cost of crossing the spread, providing a more
  realistic equity curve during backtests.
- Adds comprehensive tests for long, short, winning, and losing
  scenarios.
```
