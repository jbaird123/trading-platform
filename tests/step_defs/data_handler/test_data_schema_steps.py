from pytest_bdd import given, parsers


@given(parsers.parse('a raw data file "{filename}" with columns "{columns}"'))
def a_raw_data_file(filename: str, columns: str, shared_context: dict) -> None:
    shared_context["filename"] = filename
    shared_context["columns"] = columns.split(", ")


@given(parsers.parse("a market data series with pre-calculated indicator values"))
def a_market_data_series_with_indicators(shared_context: dict) -> None:
    pass
