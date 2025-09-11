Feature: Data Schema Contract

  As a developer,
  I want to load raw market data and enforce a strict, normalized schema,
  so that all downstream components can rely on a consistent and valid data structure.

  Scenario: Loading and normalizing valid market data
    Given a raw data file "valid_market_data.csv" with columns "UTCTime", "Open", "High", "Low", "Close", "Volume"
    When the data is loaded and normalized
    Then the resulting DataFrame should have columns "timestamp", "open", "high", "low", "close", "volume"
    And the "timestamp" column should be a UTC datetime index
    And the DataFrame should contain 3 rows
    And no data quality flags should be raised

  Scenario: Detecting a missing timestamp in market data
    Given a raw data file "missing_timestamp_data.csv"
    When the data is loaded and normalized
    Then a "missing_timestamp" quality flag should be raised
    And the DataFrame should be empty
