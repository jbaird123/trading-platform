from trading_platform.core.run import hello_run
def test_hello_run(tmp_path):
    d = hello_run(tmp_path)
    assert (d / "meta.json").exists()
