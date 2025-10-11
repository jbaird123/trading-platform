# Golden Validation Execution Plan

**Purpose**: Step-by-step execution plan for implementing TradingView golden validation

**Status**: In Progress

**Created**: 2025-10-11

---

## Phase 1: Enhanced Indicator Validation

### Part A: Prepare for Export

- [ ] 1. Review current indicator test to understand structure
- [ ] 2. Create list of exact indicators and parameters to export
- [ ] 3. Create PineScript indicator script for TradingView export
- [ ] 4. Document TradingView export settings (timeframe, date range, etc.)

### Part B: Export from TradingView

- [ ] 5. Open TradingView EUR/USD 1H chart
- [ ] 6. Set date range: 2023-01-01 to 2024-12-31
- [ ] 7. Load PineScript indicator script
- [ ] 8. Export chart data with all indicators to CSV
- [ ] 9. Save CSV as `data/dvc/golden/indicators/eurusd_1h_full.csv`
- [ ] 10. Create `data/dvc/golden/indicators/metadata.json`

### Part C: Update Indicator Tests

- [ ] 11. Create/update `tests/validation/test_indicator_validation.py`
- [ ] 12. Add all new indicators to test cases
- [ ] 13. Set appropriate tolerances for each indicator
- [ ] 14. Run tests with new golden data
- [ ] 15. Fix any tolerance issues
- [ ] 16. Verify all indicator tests pass

### Part D: Document & Track with DVC

- [ ] 17. Track indicator dataset with DVC
- [ ] 18. Push to DVC remote (S3)
- [ ] 19. Commit DVC pointer files to git
- [ ] 20. Update indicator validation documentation

---

## Phase 2: Strategy 1 - EMA Crossover

### Part A: Verify Configuration

- [ ] 21. Review `configs/golden_strategies/ema_crossover/strategy.pine`
- [ ] 22. Review `configs/golden_strategies/ema_crossover/strategy.yaml`
- [ ] 23. Verify parameters match between PineScript and YAML
- [ ] 24. Review `configs/golden_strategies/ema_crossover/README.md`

### Part B: Export from TradingView

- [ ] 25. Open TradingView EUR/USD 1H chart (2023-2024)
- [ ] 26. Load EMA Crossover PineScript
- [ ] 27. Configure Strategy Tester settings per README
- [ ] 28. Run backtest in TradingView
- [ ] 29. Export List of Trades to CSV
- [ ] 30. Export Chart Data (OHLCV) to CSV
- [ ] 31. Export Equity Curve to CSV (if available)
- [ ] 32. Take screenshot of Strategy Tester results
- [ ] 33. Save all files to `data/dvc/golden/strategies/ema_crossover/`
- [ ] 34. Create `data/dvc/golden/strategies/ema_crossover/metadata.json`

### Part C: Implement Test Integration

- [ ] 35. Review `tests/validation/test_strategy_validation.py`
- [ ] 36. Implement `load_platform_trades()` function
- [ ] 37. Connect to backtester API
- [ ] 38. Run test: `test_ema_crossover_trade_count_matches_tradingview`
- [ ] 39. Debug any trade count mismatches
- [ ] 40. Run test: `test_ema_crossover_trade_times_match_tradingview`
- [ ] 41. Debug any timing issues
- [ ] 42. Run test: `test_ema_crossover_trade_pnl_matches_tradingview`
- [ ] 43. Adjust tolerances if needed
- [ ] 44. Run test: `test_ema_crossover_equity_curve_correlation`
- [ ] 45. Verify equity curves match

### Part D: Document & Track

- [ ] 46. Track EMA crossover dataset with DVC
- [ ] 47. Push to DVC remote
- [ ] 48. Commit DVC pointer files
- [ ] 49. Document any tolerance adjustments made
- [ ] 50. Update EMA crossover README with results

---

## Phase 3: Strategy 2 - BB Mean Reversion

### Part A: Create Configuration

- [ ] 51. Create `configs/golden_strategies/bb_mean_reversion/strategy.yaml`
- [ ] 52. Create `configs/golden_strategies/bb_mean_reversion/rem.yaml`
- [ ] 53. Create `configs/golden_strategies/bb_mean_reversion/run_config.yaml`
- [ ] 54. Create `configs/golden_strategies/bb_mean_reversion/strategy.pine`
- [ ] 55. Create `configs/golden_strategies/bb_mean_reversion/README.md`
- [ ] 56. Verify parameters match between PineScript and YAML

### Part B: Export from TradingView

- [ ] 57. Open TradingView chart (instrument/timeframe per config)
- [ ] 58. Load BB Mean Reversion PineScript
- [ ] 59. Configure Strategy Tester settings
- [ ] 60. Run backtest in TradingView
- [ ] 61. Export List of Trades to CSV
- [ ] 62. Export Chart Data (OHLCV) to CSV
- [ ] 63. Take screenshot of results
- [ ] 64. Save all files to `data/dvc/golden/strategies/bb_mean_reversion/`
- [ ] 65. Create metadata.json

### Part C: Create & Run Tests

- [ ] 66. Add BB mean reversion test cases to test_strategy_validation.py
- [ ] 67. Run test: trade count matches
- [ ] 68. Run test: trade times match
- [ ] 69. Run test: PnL matches
- [ ] 70. Run test: equity curve correlation
- [ ] 71. Adjust tolerances if needed
- [ ] 72. Verify all tests pass

### Part D: Document & Track

- [ ] 73. Track BB dataset with DVC
- [ ] 74. Push to DVC remote
- [ ] 75. Commit DVC pointer files
- [ ] 76. Document tolerance decisions
- [ ] 77. Update BB Mean Reversion README

---

## Phase 4: Strategy 3 - Multi-Indicator (RSI + ADX + EMA)

### Part A: Create Configuration

- [ ] 78. Create `configs/golden_strategies/multi_indicator_strategy/strategy.yaml`
- [ ] 79. Create `configs/golden_strategies/multi_indicator_strategy/rem.yaml`
- [ ] 80. Create `configs/golden_strategies/multi_indicator_strategy/run_config.yaml`
- [ ] 81. Create `configs/golden_strategies/multi_indicator_strategy/strategy.pine`
- [ ] 82. Create `configs/golden_strategies/multi_indicator_strategy/README.md`
- [ ] 83. Verify parameters match between PineScript and YAML

### Part B: Export from TradingView

- [ ] 84. Open TradingView EUR/USD 1H chart (2023-2024)
- [ ] 85. Load Multi-Indicator PineScript
- [ ] 86. Configure Strategy Tester settings
- [ ] 87. Run backtest in TradingView
- [ ] 88. Export List of Trades to CSV
- [ ] 89. Export Chart Data (OHLCV) to CSV
- [ ] 90. Take screenshot of results
- [ ] 91. Save all files to `data/dvc/golden/strategies/multi_indicator_strategy/`
- [ ] 92. Create metadata.json

### Part C: Create & Run Tests

- [ ] 93. Add multi-indicator test cases to test_strategy_validation.py
- [ ] 94. Run test: trade count matches
- [ ] 95. Run test: trade times match
- [ ] 96. Run test: PnL matches
- [ ] 97. Run test: equity curve correlation
- [ ] 98. Adjust tolerances if needed
- [ ] 99. Verify all tests pass

### Part D: Document & Track

- [ ] 100. Track multi-indicator dataset with DVC
- [ ] 101. Push to DVC remote
- [ ] 102. Commit DVC pointer files
- [ ] 103. Document tolerance decisions
- [ ] 104. Update Multi-Indicator README

---

## Phase 5: Final Documentation & Validation

### Part A: Comprehensive Testing

- [ ] 105. Run all indicator validation tests: `pytest tests/validation/test_indicator_validation.py -v`
- [ ] 106. Run all strategy validation tests: `pytest tests/validation/test_strategy_validation.py -v`
- [ ] 107. Run full validation suite: `pytest -m validation -v`
- [ ] 108. Verify all tests pass
- [ ] 109. Check test coverage for validation modules

### Part B: Documentation

- [ ] 110. Update `data/dvc/golden/README.md` with final inventory
- [ ] 111. Update `docs/testing/tradingview_validation.md` with lessons learned
- [ ] 112. Create summary of tolerance decisions
- [ ] 113. Document any platform differences discovered
- [ ] 114. Update main task document with completion status

### Part C: CI/CD Integration (Optional)

- [ ] 115. Create GitHub Actions workflow for validation tests
- [ ] 116. Configure DVC pull in CI
- [ ] 117. Test CI pipeline
- [ ] 118. Document CI setup for team

### Part D: Team Handoff

- [ ] 119. Write summary document of validation results
- [ ] 120. Create presentation/demo of validation framework
- [ ] 121. Document how to add new strategies
- [ ] 122. Train team on validation process

---

## Quick Reference: Current Status

### Completed ✅
- Infrastructure setup
- EMA Crossover configs ready
- Test framework created
- Documentation templates ready

### In Progress 🔄
- (None - starting Phase 1)

### Blocked 🚫
- (None currently)

---

## Notes & Decisions

### Indicator Parameters Chosen
- (To be filled in during Phase 1)

### Tolerance Decisions
- (To be documented as we discover needed adjustments)

### Platform Differences Discovered
- (To be documented during testing)

---

## Time Estimates

- **Phase 1** (Indicator Validation): 3-4 hours
  - Export: 30-45 min
  - Testing: 2-3 hours

- **Phase 2** (EMA Crossover): 2-3 hours
  - Export: 30 min
  - Integration: 1.5-2 hours
  - Testing: 30-60 min

- **Phase 3** (BB Mean Reversion): 3-4 hours
  - Config creation: 1 hour
  - Export: 30 min
  - Testing: 1.5-2 hours

- **Phase 4** (Multi-Indicator): 3-4 hours
  - Config creation: 1 hour
  - Export: 30 min
  - Testing: 1.5-2 hours

- **Phase 5** (Documentation): 2-3 hours

**Total Estimated Time**: 13-18 hours

---

## Success Criteria

### Phase 1 Complete When:
- ✅ All priority indicators validated against TradingView
- ✅ Tests pass with documented tolerances
- ✅ Data tracked in DVC

### Phase 2 Complete When:
- ✅ EMA Crossover trades match TradingView exactly
- ✅ All 4 test cases pass
- ✅ Equity curves correlate > 0.999

### Phase 3 Complete When:
- ✅ BB Mean Reversion fully validated
- ✅ Tests demonstrate framework reusability
- ✅ Second strategy proves pattern works

### Phase 4 Complete When:
- ✅ Multi-indicator strategy validated
- ✅ Complex indicator combinations proven
- ✅ Three strategies provide comprehensive coverage

### Phase 5 Complete When:
- ✅ All tests passing
- ✅ Documentation complete
- ✅ Framework ready for team use
- ✅ Process documented for adding more strategies
