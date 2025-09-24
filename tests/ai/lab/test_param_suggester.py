from trading_platform.ai.lab.param_suggester import suggest_parameters


def test_suggest_parameters_best_result():
    brief: dict = {
        "parameter_search": {
            "results": [
                {"parameters": {"a": 1, "b": 2}, "objective_score": 0.5},
                {"parameters": {"a": 3, "b": 4}, "objective_score": 0.9},
                {"parameters": {"a": 5, "b": 6}, "objective_score": 0.7},
            ]
        }
    }
    result = suggest_parameters(brief)
    assert result == {"a": 3, "b": 4}


def test_suggest_parameters_no_results():
    brief: dict = {"parameter_search": {"results": []}}
    result = suggest_parameters(brief)
    assert result == {}


def test_suggest_parameters_missing_section():
    brief: dict = {}
    result = suggest_parameters(brief)
    assert result == {}
