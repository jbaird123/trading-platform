# Validates: [DH-2.2]
from __future__ import annotations

from trading_platform.data.oanda_connector import OandaStreamingConnector


def test_oanda_streaming_connector_lifecycle():
    """Tests the connect, get_next_tick, and disconnect methods."""
    # Arrange
    connector = OandaStreamingConnector(
        account_id="test-account",
        access_token="test-token",
        instrument="EURUSD",
    )

    # Assert initial state
    assert connector.get_next_tick() is None

    # Act: Connect
    connector.connect()

    # Assert: Can get a tick
    tick = connector.get_next_tick()
    assert tick is not None
    assert tick["type"] == "PRICE"
    assert tick["instrument"] == "EURUSD"
    assert "bids" in tick and "asks" in tick

    # Act: Disconnect
    connector.disconnect()

    # Assert: Can no longer get a tick
    assert connector.get_next_tick() is None
