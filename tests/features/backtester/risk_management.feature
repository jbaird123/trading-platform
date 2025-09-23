Feature: Backtester Risk Management

  As a trader,
  I want the backtester to handle stop-loss and take-profit orders,
  So that I can simulate risk management rules and evaluate their impact on performance.

  Background:
    Given a market data series with columns "open", "high", "low", "close", "volume"
    And a signal series with "long, short, flat" signals
    And the backtester is configured with a stop-loss of 10.0 and a take-profit of 20.0

  @req_BT_7_9
  Scenario: A long trade is closed by a stop-loss
    Given the signal at bar 2 is "long"
    And the close price at bar 2 is 100.0  # Entry price
    And the low price at bar 3 is 89.0     # Stop-loss is 100.0 - 10.0 = 90.0. This should trigger it.
    And the high price at bar 3 is 95.0
    And the close price at bar 3 is 92.0
    When the backtest is run
    Then there should be 1 trade generated
    And the trade should have an entry price of 100.0 and an exit price of 90.0
    And the trade should have an exit reason of "stop-loss"

  @req_BT_7_9
  Scenario: A long trade is closed by a take-profit
    Given the signal at bar 2 is "long"
    And the close price at bar 2 is 100.0  # Entry price
    And the low price at bar 3 is 105.0
    And the high price at bar 3 is 121.0   # Take-profit is 100.0 + 20.0 = 120.0. This should trigger it.
    And the close price at bar 3 is 119.0
    When the backtest is run
    Then there should be 1 trade generated
    And the trade should have an entry price of 100.0 and an exit price of 120.0
    And the trade should have an exit reason of "take-profit"
