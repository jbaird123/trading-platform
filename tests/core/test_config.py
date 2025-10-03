def test_run_config_auto_populate_instrument_from_data_request() -> None:
    """Test instrument auto-populated from data_request."""
    # Validates: [REQ-CONFIG-001] Auto-populate instrument
    from trading_platform.core.config import RunConfig

    config = RunConfig.model_validate(
        {
            "run_id": "test",
            "data_request": {"symbol": "EUR_USD", "timeframe": "1H"},
        }
    )

    assert config.instrument is not None
    assert config.instrument["symbol"] == "EURUSD"
    assert config.instrument["timeframe"] == "1H"
