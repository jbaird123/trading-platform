Feature: Exponential Moving Average (EMA) Crossover Signal Generation

  As a developer,
  I want to generate trading signals based on the crossover of two EMAs,
  so that I can implement a basic trend-following strategy.

  Background:
    Given a DataFrame of market data with columns "open", "high", "low", "close"
    And the strategy is configured with a fast EMA of period 10 and a slow EMA of period 20

  Scenario: Generating a long signal on a bullish crossover
    Given the fast EMA on the previous bar was below the slow EMA
    And the fast EMA on the current bar is above the slow EMA
    When the strategy generates signals
    Then a "long" signal should be produced for the current bar

  Scenario: Generating a short signal on a bearish crossover
    Given the fast EMA on the previous bar was above the slow EMA
    And the fast EMA on the a current bar is below the slow EMA
    When the strategy generates signals
    Then a "short" signal should be produced for the current bar
