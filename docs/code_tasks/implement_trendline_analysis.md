# Trendline Analysis and Charting Implementation Plan

This document outlines the steps to implement a trendline analysis feature, including backend logic for signal generation and frontend functionality for chart visualization.

**Branch Name:** `feature/trendline-analysis`

Before starting, create and switch to the specified branch:
`git checkout -b feature/trendline-analysis`

---

### Phase 1: Core Trendline Identification Logic

1.  [ ] **Write Test for Trendline Data Structure:**
    -   Create a new test file: `tests/strategy/features/test_trendline_logic.py`.
    -   In this file, write a test `test_trendline_dataclass` to ensure a `Trendline` data structure can be instantiated and holds the expected attributes (`start_time`, `start_price`, `end_time`, `end_price`, `slope`, `type`).

2.  [ ] **Implement Trendline Data Structure:**
    -   Create a new file: `src/trading_platform/strategy/features/trendline_logic.py`.
    -   In this file, define a `Trendline` dataclass with the following attributes: `start_time: datetime`, `start_price: float`, `end_time: datetime`, `end_price: float`, `slope: float`, `type: str` (e.g., 'uptrend' or 'downtrend').

3.  [ ] **Write Test for Trendline Identification Function:**
    -   In `tests/strategy/features/test_trendline_logic.py`, add a new test `test_identify_trendlines`.
    -   This test will create mock pandas Series for `swing_highs` and `swing_lows` containing several pivot points.
    -   Call a new (not-yet-created) function `identify_trendlines` with these series.
    -   Assert that the function returns a list of `Trendline` objects.
    -   Assert that the correct number of uptrend and downtrend lines were found and that their start/end points match the mock data.

4.  [ ] **Implement Trendline Identification Function:**
    -   In `src/trading_platform/strategy/features/trendline_logic.py`, create the function `identify_trendlines(swing_highs: pd.Series, swing_lows: pd.Series) -> list[Trendline]`.
    -   Implement the logic to iterate through the swing points, identify valid pairs that form trendlines (e.g., two higher lows for an uptrend), calculate their slope, and return them as a list of `Trendline` objects.

### Phase 2: Backtester Integration and Data Export

5.  [ ] **Write Test for Trendline Data Export:**
    -   In a relevant test file like `tests/backtester/test_backtester.py`, add a test to verify that trendline data is exported.
    -   The test should run a backtest with a strategy that generates swing points.
    -   Use `unittest.mock.patch` to mock `identify_trendlines` to return a known list of `Trendline` objects.
    -   Assert that a `trendlines.json` file is created in the run output directory.
    -   Assert that the content of `trendlines.json` matches the mocked trendline data.

6.  [ ] **Implement Trendline Export in Backtester:**
    -   Modify the backtester execution flow (e.g., in `src/trading_platform/backtester/backtester.py`).
    -   After the feature generation step, if `swing_highs` and `swing_lows` are present in the feature DataFrame, call the `identify_trendlines` function.
    -   Serialize the returned list of `Trendline` objects to JSON and save it to `trendlines.json` within the run's output directory.

### Phase 3: Charting Integration

7.  [ ] **Write Test for Chart Data Embedding:**
    -   In `tests/reporting/test_exports.py`, add a test `test_save_chart_embeds_trendlines`.
    -   Create a temporary run directory containing a mock `brief.json` and a mock `trendlines.json`.
    -   Call `save_chart_from_brief` using this directory.
    -   Read the generated `chart.html` and assert that the content of `trendlines.json` is present and correctly embedded within a `<script id="trendlines" ...>` tag.

8.  [ ] **Modify Chart Export to Embed Trendline Data:**
    -   Open `src/trading_platform/reporting/chart_export.py`.
    -   In the `save_chart_from_brief` function, add logic to check for the existence of `trendlines.json` in the run path.
    -   If it exists, read its content and embed it into the `HTML_TMPL` using a new placeholder `__TRENDLINES_JSON__` and a `<script id="trendlines" type="application/json">` tag.

9.  [ ] **Modify Chart JavaScript to Draw Trendlines:**
    -   In the `HTML_TMPL` within `src/trading_platform/reporting/chart_export.py`, add a new JavaScript block.
    -   This script will:
        -   Parse the JSON data from the `#trendlines` script tag.
        -   Loop through each trendline object.
        -   For each object, use the `chart.addLineSeries()` method to draw a line on the main chart, setting the `data` to an array containing the start and end points: `[{ time: startTime, value: startPrice }, { time: endTime, value: endPrice }]`.
        -   Style uptrend and downtrend lines with different colors (e.g., green for up, red for down).

### Phase 4: Trendline-Based Signal Generation

10. [ ] **Write Test for Trendline Signal Feature:**
    -   Create a new test file: `tests/strategy/features/test_trendline_signals.py`.
    -   Write a test for a new feature type, `TRENDLINE_BREAK`.
    -   The test will provide a mock price series and a list of pre-defined `Trendline` objects.
    -   Assert that the feature correctly generates a signal series (e.g., `1` for a cross above a downtrend line, `-1` for a cross below an uptrend line, `0` otherwise).

11. [ ] **Implement Trendline Signal Feature:**
    -   Create the business logic for the `TRENDLINE_BREAK` feature.
    -   This logic will take the price data and a list of trendlines as input.
    -   For each candle, it will calculate the trendline's value at that point in time and compare it to the candle's price to detect a cross.
    -   This may require adding a new function to a file like `src/trading_platform/strategy/features/signal_functions.py`.

12. [ ] **Update Indicator Registry and Schema:**
    -   In `src/trading_platform/strategy/indicators_registry.py`, add `TRENDLINE_BREAK` as a new available feature.
    -   In `docs/schemas/strategy.schema.json`, update the feature type enum to include `TRENDLINE_BREAK`, allowing it to be used in strategy YAML files.
