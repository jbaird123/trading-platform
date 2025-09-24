from typing import Any, Dict


def suggest_parameters(brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Suggests optimal parameters from the brief's parameter_search section.
    Returns the parameter set with the best objective_score, or empty dict if not found.
    """
    param_search = brief.get("parameter_search")
    if not param_search or "results" not in param_search:
        return {}
    results = param_search["results"]
    if not isinstance(results, list) or not results:
        return {}
    # Find the result with the best objective_score
    best = max(results, key=lambda r: r.get("objective_score", float("-inf")))
    return best.get("parameters", {}) if "parameters" in best else {}
