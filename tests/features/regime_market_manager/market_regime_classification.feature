Feature: Market Regime Classification
  As a user, I want to classify the market regime based on technical indicators
  so that I can filter trades and adapt my strategy to current market conditions.

  Background:
    Given a market data series with pre-calculated indicator values

  @req_RMM_4_1
  @req_RMM_4_2
  @req_RMM_4_3
  Scenario: Classify a strong trending regime
    Given the indicator "ADX(14)" has a value of 30.0
    And the indicator "EMA(200)_slope" has a value of 0.5
    When the market regime is classified
    Then the regime should be "trend_up"
    And the confidence should be "high"

  @req_RMM_4_1
  @req_RMM_4_2
  @req_RMM_4_3
  Scenario: Classify a ranging regime
    Given the indicator "ADX(14)" has a value of 15.0
    And the indicator "BB_width(20)" has a value of 0.02
    When the market regime is classified
    Then the regime should be "range"
    And the confidence should be "medium"
