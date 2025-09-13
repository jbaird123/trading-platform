@req:SE
Feature: Strategy Signal Generation
  As a user, I want to generate trading signals from market data using a strategy
  so that I can define entry and exit points for backtesting.

  Background:
    Given a market data series with columns "open", "high", "low", "close", "volume"

  Scenario: Generate a long signal on a bullish EMA crossover
    Given the strategy is an EMA Crossover with fast_period=3 and slow_period=5
    And the market data is prepared for the strategy
    And the "ema_fast" at the previous bar is 102.0
    And the "ema_slow" at the previous bar is 103.0
    And the "ema_fast" at the current bar is 105.0
    And the "ema_slow" at the current bar is 104.0
    When the strategy generates signals
    Then the signal for the current bar should be "long"

  Scenario: Generate a short signal on a bearish EMA crossover
    Given the strategy is an EMA Crossover with fast_period=3 and slow_period=5
    And the market data is prepared for the strategy
    And the "ema_fast" at the previous bar is 104.0
    And the "ema_slow" at the previous bar is 103.0
    And the "ema_fast" at the current bar is 102.0
    And the "ema_slow" at the current bar is 103.0
    When the strategy generates signals
    Then the signal for the current bar should be "short"

  Scenario: Maintain a flat signal when there is no crossover
    Given the strategy is an EMA Crossover with fast_period=3 and slow_period=5
    And the market data is prepared for the strategy
    And the "ema_fast" at the previous bar is 102.0
    And the "ema_slow" at the previous bar is 103.0
    And the "ema_fast" at the current bar is 103.0
    And the "ema_slow" at the current bar is 104.0
    When the strategy generates signals
    Then the signal for the current bar should be "flat"
