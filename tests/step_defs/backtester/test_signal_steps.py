# ruff: noqa: E501
from pytest_bdd import given, parsers


@given(parsers.parse('a signal series with "{signal_list}" signals'))
def a_signal_series(signal_list: str, shared_context: dict) -> None:
    import pandas as pd

    signals = pd.Series(
        signal_list.split(", "), index=shared_context["market_data"].index
    )
    shared_context["signals"] = signals
