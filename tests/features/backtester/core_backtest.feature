Feature: Core Backtester Logic
  As a user, I want to run a backtest on a series of signals
  so that I can simulate a strategy's performance and generate a list of trades.

  Background:
    Given a market data series with columns "open", "high", "low", "close", "volume"
    And a signal series with "long", "short", and "flat" signals

  @req_BT_6_1
  @req_BT_6_2
  @req_BT_6_8
  Scenario: Process a simple long entry and exit
    Given the signal at bar 1 is "long"
    And the close price at bar 1 is 100.0
    And the signal at bar 2 is "flat"
    And the close price at bar 2 is 105.0
    When the backtest is run
    Then there should be 1 trade generated
    And the trade should have an entry price of 100.0 and an exit price of 105.0
