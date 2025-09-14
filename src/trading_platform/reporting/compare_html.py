from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .compare import compare_briefs


def render_comparison_html(comp: dict[str, Any]) -> str:
    runs = comp.get("runs", [])
    a = runs[0] if len(runs) > 0 else {}
    b = runs[1] if len(runs) > 1 else {}
    metrics: dict[str, dict[str, float]] = comp.get("metrics", {})  # type: ignore[assignment]

    def esc(x: Any) -> str:
        return (
            ("" if x is None else str(x))
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    rows: list[str] = []
    for name in sorted(metrics.keys()):
        m = metrics[name]
        row_html = (
            "<tr>"
            f"<td>{esc(name)}</td>"
            f"<td>{m.get('a', 0.0):.6g}</td>"
            f"<td>{m.get('b', 0.0):.6g}</td>"
            f"<td>{m.get('delta', 0.0):.6g}</td>"
            "</tr>"
        )
        rows.append(row_html)

    html = (
        "<!doctype html>\n"
        "<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>Comparison Report</title>\n<style>\n"
        "body { font-family: system-ui, -apple-system, Segoe UI, Roboto, "
        "sans-serif; padding: 16px; }\n"
        "table { border-collapse: collapse; width: 100%; max-width: 960px; }\n"
        "th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: right; }\n"
        "th:first-child, td:first-child { text-align: left; }\n"
        "thead { background: #f5f5f5; }\n"
        "</style>\n</head>\n<body>\n"
        "<h1>Comparison Report</h1>\n"
        f"<p><strong>Run A:</strong> {esc(a.get('strategy_name'))} "
        f"[{esc(a.get('run_id'))}]</p>\n"
        f"<p><strong>Run B:</strong> {esc(b.get('strategy_name'))} "
        f"[{esc(b.get('run_id'))}]</p>\n"
        "<table>\n"
        "  <thead><tr><th>Metric</th><th>A</th><th>B</th>"
        "<th>Delta (B - A)</th></tr></thead>\n"
        "  <tbody>\n    " + "".join(rows) + "\n  </tbody>\n</table>\n</body>\n</html>\n"
    )
    return html


def save_comparison_html(path: Path, comp: dict[str, Any]) -> Path:
    html = render_comparison_html(comp)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path


def save_comparison_report(a_path: Path, b_path: Path, out_path: Path) -> Path:
    """Load two brief.json files, compare, and save an HTML report.

    Returns the output path.
    """
    a = json.loads(Path(a_path).read_text())
    b = json.loads(Path(b_path).read_text())
    comp = compare_briefs([a, b])
    return save_comparison_html(out_path, comp)
