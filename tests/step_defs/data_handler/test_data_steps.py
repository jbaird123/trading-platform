from pytest_bdd import given


@given('a raw data file "{filename}" with columns {columns}')
def a_raw_data_file(filename: str, columns: str, shared_context: dict) -> None:
    shared_context["filename"] = filename
    shared_context["columns"] = columns.split(", ")
