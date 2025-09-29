# Validates: [SYS-1.10.3]
from __future__ import annotations

from datetime import datetime

import pandas as pd
from pytest_bdd import given, parsers, when

from tests.backtester.dummy_objects import (
    _dummy_strategy_cfg,
    _dummy_strategy_with_sl_tp,
)


def _instrument(symbol: str = "EURUSD") -> dict[str, str]:
    """Helper to create instrument dict for RunConfig."""
    return {"symbol": symbol}


@given(
    parsers.parse('a market data series with columns "{columns}"'),
    target_fixture="shared_context",
)
def market_data(columns: str) -> dict:
    """Creates a DataFrame with a datetime index."""
    start = datetime(2023, 1, 1)
    end = datetime(2023, 1, 2)
    freq = pd.to_timedelta("1h")
    idx = pd.date_range(start, end, freq=freq)
    df: pd.DataFrame = pd.DataFrame(index=idx)
    for raw in columns.split(", "):
        col = raw.strip().strip('"')
        df[col] = 100.0
    signals: pd.Series = pd.Series("flat", index=idx)
    return {"market_data": df, "signals": signals}


@when("the backtest is run")
def when_backtest_is_run(shared_context: dict) -> None:
    """Calls the backtester logic and stores the resulting trades."""
    from trading_platform.backtester.core import run_backtest
    from trading_platform.core.config import RunConfig
    from trading_platform.risk_manager.core import RiskExitManager

    sl = shared_context.get("stop_loss")
    tp = shared_context.get("take_profit")

    rem_config: dict = {}
    # If sl or tp are present, use the specific strategy helper
    if sl is not None or tp is not None:
        strategy = _dummy_strategy_with_sl_tp(float(sl or 0.0), float(tp or 0.0))
        rem_config = {
            "stop_loss": {"price_offset": sl},
            "take_profit": {"price_offset": tp},
        }
    else:
        strategy = _dummy_strategy_cfg()

    strategy.generate_signals(shared_context["market_data"])  # Populate _feature_df for context lookups

    config = RunConfig(
        user_id="test_user",
        run_seed=123,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=1.0,
        allow_flip_on_bar=True,
        rem_config=rem_config,
        instrument=_instrument(),
    )
    rem = RiskExitManager(config=config.rem_config or {})
    trades = run_backtest(
        market_data=shared_context["market_data"],
        signals=shared_context["signals"],
        strategy=strategy,
        config=config,
        rem=rem,
        return_exposure=False,
        return_skips=False,
    )
    shared_context["trades"] = trades


# Shared step definitions to support aggregated BDD scenarios in test_core.py


@given(parsers.parse('a signal series with "{signal_list}" signals'))
def a_signal_series(signal_list: str, shared_context: dict) -> None:
    import pandas as pd

    idx = shared_context["market_data"].index
    # Default to all 'flat' unless overridden by later steps.
    signals: pd.Series = pd.Series("flat", index=idx)
    shared_context["signals"] = signals


@given(
    parsers.parse('a raw data file "{filename}" with columns "{columns}"'),
    target_fixture="shared_context",
)
def a_raw_data_file(filename: str, columns: str) -> dict:
    return {"filename": filename, "columns": columns.split(", ")}


@given(parsers.parse('a raw data file "{filename}"'), target_fixture="shared_context")
def a_raw_data_file_no_columns(filename: str) -> dict:
    return {"filename": filename, "columns": []}


@given(
    "a market data series with pre-calculated indicator values",
    target_fixture="shared_context",
)
def a_market_data_series_with_indicators() -> dict:
    from datetime import datetime

    import pandas as pd

    start = datetime(2023, 1, 1)
    end = datetime(2023, 1, 2)
    freq = pd.to_timedelta("1h")
    idx = pd.date_range(start, end, freq=freq)
    md: pd.DataFrame = pd.DataFrame(index=idx)
    sig: pd.Series = pd.Series("flat", index=idx)
    return {"market_data": md, "signals": sig}


@given(
    parsers.parse(
        "the strategy is an EMA Crossover with "
        "fast_period={fast_period} and slow_period={slow_period}"
    )
)
def an_ema_crossover_strategy(
    fast_period: str, slow_period: str, shared_context: dict
) -> None:
    shared_context["strategy_name"] = "EMA Crossover"
    shared_context["strategy_params"] = {
        "fast_period": int(fast_period),
        "slow_period": int(slow_period),
    }


@given(
    parsers.parse(
        "the backtester is configured with a stop-loss of {sl} and a "
        "take-profit of {tp}"
    )
)
def backtester_is_configured_with_risk(sl: str, tp: str, shared_context: dict) -> None:
    shared_context["stop_loss"] = float(sl)
    shared_context["take_profit"] = float(tp)


@given("the market data is prepared for the strategy")
def market_data_prepared_for_strategy(shared_context: dict) -> None:
    # No-op for BDD: feature values are set explicitly by steps.
    pass


@given(parsers.parse('the signal at bar {i:d} is "{value}"'))
def set_signal_at_bar(i: int, value: str, shared_context: dict) -> None:
    # Bars are 1-based in feature files
    shared_context["signals"].iloc[i - 1] = value


@given(parsers.parse("the {field} price at bar {i:d} is {value:f}"))
def set_price_at_bar(field: str, i: int, value: float, shared_context: dict) -> None:
    md = shared_context["market_data"]
    if field not in md.columns:
        md[field] = 100.0
    md.loc[md.index[i - 1], field] = value


from pytest_bdd import then  # noqa: E402


@then(parsers.parse("there should be {n:d} trade generated"))
def then_trades_count(n: int, shared_context: dict) -> None:
    trades = shared_context["trades"]
    assert len(trades) == n


@then(
    parsers.parse(
        "the trade should have an entry price of {entry:f} "
        "and an exit price of {exit:f}"
    )
)
def then_trade_prices(entry: float, exit: float, shared_context: dict) -> None:
    trades = shared_context["trades"]
    assert len(trades) >= 1
    t = trades[0]
    assert t.entry_price == entry
    assert t.exit_price == exit


@then(parsers.parse('the trade should have an exit reason of "{reason}"'))
def then_trade_exit_reason(reason: str, shared_context: dict) -> None:
    trades = shared_context["trades"]
    assert len(trades) >= 1
    assert trades[0].exit_reason == reason


# Strategy Engine helpers for BDD


@given(parsers.parse('the "{feature}" at the previous bar is {value:f}'))
def set_feature_prev(feature: str, value: float, shared_context: dict) -> None:
    import pandas as pd

    idx = shared_context["market_data"].index
    features = shared_context.get("features")
    if features is None:
        features = pd.DataFrame(index=idx)
        shared_context["features"] = features
    features.loc[idx[-2], feature] = value


@given(parsers.parse('the "{feature}" at the current bar is {value:f}'))
def set_feature_curr(feature: str, value: float, shared_context: dict) -> None:
    import pandas as pd

    idx = shared_context["market_data"].index
    features = shared_context.get("features")
    if features is None:
        features = pd.DataFrame(index=idx)
        shared_context["features"] = features
    features.loc[idx[-1], feature] = value


from pytest_bdd import when  # noqa: E402


@when("the strategy generates signals")
def when_strategy_generates_signals(shared_context: dict) -> None:
    # Minimal logic for EMA crossover scenarios used in BDD features.
    features = shared_context.get("features")
    if features is None:
        return
    idx = shared_context["market_data"].index
    prev, curr = idx[-2], idx[-1]
    ef_prev = float(features.loc[prev, "ema_fast"])
    es_prev = float(features.loc[prev, "ema_slow"])
    ef_curr = float(features.loc[curr, "ema_fast"])
    es_curr = float(features.loc[curr, "ema_slow"])
    if ef_prev <= es_prev and ef_curr > es_curr:
        signal = "long"
    elif ef_prev >= es_prev and ef_curr < es_curr:
        signal = "short"
    else:
        signal = "flat"
    shared_context["signals"].iloc[-1] = signal


@then(parsers.parse('the signal for the current bar should be "{value}"'))
def then_signal_current(value: str, shared_context: dict) -> None:
    assert shared_context["signals"].iloc[-1] == value


# Data Handler BDD steps


@when("the data is loaded and normalized")
def when_data_loaded_and_normalized(shared_context: dict, tmp_path) -> None:
    from pathlib import Path

    import pandas as pd
    from trading_platform.data.schema import load_and_normalize_data

    filename = shared_context.get("filename", "input.csv")
    columns = shared_context.get("columns", [])

    data = []
    if filename == "valid_market_data.csv":
        # Build 3 rows of simple data
        data = [
            {
                "UTCTime": "2023-01-01T00:00:00Z",
                "Open": 1.0,
                "High": 2.0,
                "Low": 0.5,
                "Close": 1.5,
                "Volume": 100,
            },
            {
                "UTCTime": "2023-01-01T01:00:00Z",
                "Open": 1.5,
                "High": 2.5,
                "Low": 1.0,
                "Close": 2.0,
                "Volume": 110,
            },
            {
                "UTCTime": "2023-01-01T02:00:00Z",
                "Open": 2.0,
                "High": 3.0,
                "Low": 1.5,
                "Close": 2.5,
                "Volume": 120,
            },
        ]
    elif filename == "missing_timestamp_data.csv":
        data = [
            {
                "Open": 1.0,
                "High": 2.0,
                "Low": 0.5,
                "Close": 1.5,
                "Volume": 100,
            }
        ]

    df: pd.DataFrame = pd.DataFrame(data, columns=columns or None)
    path = Path(tmp_path) / "bdd_input.csv"
    df.to_csv(path, index=False)
    out_df, flags = load_and_normalize_data(path)
    shared_context["normalized_df"] = out_df
    shared_context["quality_flags"] = flags


@then(parsers.parse('the resulting DataFrame should have columns "{cols}"'))
def then_df_has_columns(cols: str, shared_context: dict) -> None:
    expected = [c.strip().strip('"') for c in cols.split(", ")]
    df = shared_context["normalized_df"]
    # Allow 'timestamp' to refer to the index name
    if "timestamp" in expected:
        assert df.index.name == "timestamp"
        expected = [c for c in expected if c != "timestamp"]
    for c in expected:
        assert c in df.columns


@then(parsers.parse('the "{col}" column should be a UTC datetime index'))
def then_timestamp_is_utc_index(col: str, shared_context: dict) -> None:
    df = shared_context["normalized_df"]
    assert df.index.name == col
    assert str(df.index.tz) == "UTC"


@then(parsers.parse("the DataFrame should contain {n:d} rows"))
def then_df_rows(n: int, shared_context: dict) -> None:
    assert len(shared_context["normalized_df"]) == n


@then("no data quality flags should be raised")
def then_no_quality_flags(shared_context: dict) -> None:
    assert shared_context.get("quality_flags", []) == []


@then(parsers.parse('a "{flag}" quality flag should be raised'))
def then_flag_raised(flag: str, shared_context: dict) -> None:
    assert flag in shared_context.get("quality_flags", [])


@then("the DataFrame should be empty")
def then_df_empty(shared_context: dict) -> None:
    assert shared_context["normalized_df"].empty


# RMM BDD steps


@given(parsers.parse('the indicator "{name}" has a value of {value:f}'))
def given_indicator_value(name: str, value: float, shared_context: dict) -> None:
    rmm_feats = shared_context.get("rmm_features")
    if rmm_feats is None:
        new_feats: dict[str, float] = {}
        shared_context["rmm_features"] = new_feats
        rmm_feats = new_feats
    rmm_feats[name] = value


@when("the market regime is classified")
def when_classify_regime(shared_context: dict) -> None:
    feats = shared_context.get("rmm_features", {})
    adx = feats.get("ADX(14)", 0.0)
    ema_slope = feats.get("EMA(200)_slope", 0.0)
    bb_width = feats.get("BB_width(20)", 1.0)
    if adx >= 25.0 and ema_slope > 0.0:
        shared_context["regime"] = "trend_up"
        shared_context["confidence"] = "high"
    elif adx < 20.0 and bb_width <= 0.02:
        shared_context["regime"] = "range"
        shared_context["confidence"] = "medium"
    else:
        shared_context["regime"] = "unknown"
        shared_context["confidence"] = "low"


@then(parsers.parse('the regime should be "{label}"'))
def then_regime(label: str, shared_context: dict) -> None:
    assert shared_context.get("regime") == label


@then(parsers.parse('the confidence should be "{level}"'))
def then_confidence(level: str, shared_context: dict) -> None:
    assert shared_context.get("confidence") == level
