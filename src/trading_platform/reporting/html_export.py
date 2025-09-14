from __future__ import annotations

from pathlib import Path
from typing import Any

from trading_platform.portfolio.trade import Trade


def generate_html_report(meta: dict[str, Any], trades: list[Trade]) -> str:
    """Return a minimal HTML report with summary and entry/exit table.

    Skeleton only: no price chart yet. Keeps dependencies to zero.
    """
    title = f"Trading Report - {meta.get('strategy_name', 'Unknown')}"
    run_id = meta.get("run_id", "")
    parts: list[str] = []
    parts.append("<!doctype html>")
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append(f"<title>{title}</title>")
    parts.append(
        "<style>body{font-family:system-ui,sans-serif;margin:20px}"
        ".muted{color:#666} table{border-collapse:collapse} "
        "td,th{border:1px solid #ddd;padding:4px 6px}</style>"
    )
    parts.append("</head><body>")
    parts.append(f"<h1>{title}</h1>")
    if run_id:
        parts.append(f"<div class='muted'>Run ID: {run_id}</div>")

    parts.append("<h2>Summary</h2>")
    parts.append(f"<p>Trades: {len(trades)}</p>")

    parts.append("<h2>Entries/Exits</h2>")
    parts.append(
        "<table><thead><tr>"
        "<th>Symbol</th><th>Side</th><th>Entry Time</th><th>Entry</th>"
        "<th>Exit Time</th><th>Exit</th><th>PnL</th>"
        "</tr></thead><tbody>"
    )
    for t in trades:
        parts.append(
            "<tr>"
            f"<td>{t.symbol}</td>"
            f"<td>{t.side}</td>"
            f"<td>{t.entry_time.isoformat()}</td>"
            f"<td>{t.entry_price}</td>"
            f"<td>{t.exit_time.isoformat()}</td>"
            f"<td>{t.exit_price}</td>"
            f"<td>{t.pnl}</td>"
            "</tr>"
        )
    parts.append("</tbody></table>")
    parts.append("</body></html>")
    return "\n".join(parts)


def save_html_report(
    run_path: Path, *, meta: dict[str, Any], trades: list[Trade]
) -> Path:
    """Write `report.html` under the given run_path and return the path."""
    out = run_path / "report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    html = generate_html_report(meta, trades)
    out.write_text(html)
    return out
