from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from trading_platform.portfolio.trade import Trade


def _to_ts(x: Any) -> datetime:
    if isinstance(x, datetime):
        return x
    try:
        return datetime.fromisoformat(str(x))
    except Exception:  # pragma: no cover
        return datetime.min


def _spark_svg(
    series: list[tuple[Any, float]],
    overlays: dict[str, list[tuple[Any, float]]] | None,
    entry_exit_ts: list[tuple[datetime, datetime]],
) -> str:
    if not series:
        return ""
    pts = [(_to_ts(t), float(v)) for t, v in series]
    xs = [p[0].timestamp() for p in pts]
    ys = [p[1] for p in pts]
    w, h, pad = 360, 120, 6
    x0, x1 = min(xs), max(xs) or 1.0
    y0, y1 = min(ys), max(ys) or 1.0
    xr = (x1 - x0) or 1.0
    yr = (y1 - y0) or 1.0

    def sx(x: float) -> float:
        return pad + (x - x0) * (w - 2 * pad) / xr

    def sy(y: float) -> float:
        return pad + (h - 2 * pad) * (1.0 - (y - y0) / yr)

    def poly(points: list[tuple[float, float]], cls: str) -> str:
        pts_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        return (
            f"<polyline class='{cls}' points='{pts_str}' "
            "fill='none' stroke-width='1.5' />"
        )

    price_xy = [(sx(t), sy(v)) for t, v in zip(xs, ys)]
    svg_parts = [
        "<svg xmlns='http://www.w3.org/2000/svg' " f"viewBox='0 0 {w} {h}'>",
        "<style>.pr{stroke:#333}.ov{stroke:#0a7}.mk{fill:#c33}"
        ".mk2{fill:#3a3}</style>",
        poly(price_xy, "pr"),
    ]
    if overlays:
        for name, arr in overlays.items():
            o_pts = [(_to_ts(t), float(v)) for t, v in arr]
            o_x = [p[0].timestamp() for p in o_pts]
            o_y = [p[1] for p in o_pts]
            o_xy = [(sx(t), sy(v)) for t, v in zip(o_x, o_y)]
            svg_parts.append(poly(o_xy, "ov"))
    # Markers for entries/exits
    xs_map = {
        datetime.fromtimestamp(t): x for t, x in zip(xs, [p[0] for p in price_xy])
    }
    for et, xt in entry_exit_ts:
        ex = xs_map.get(et)
        xx = xs_map.get(xt)
        if ex is not None:
            svg_parts.append(
                f"<circle class='mk' cx='{ex:.2f}' cy='{sy(ys[0]):.2f}' r='2' />"
            )
        if xx is not None:
            svg_parts.append(
                f"<circle class='mk2' cx='{xx:.2f}' cy='{sy(ys[-1]):.2f}' r='2' />"
            )
    svg_parts.append("</svg>")
    return "".join(svg_parts)


def generate_html_report(
    meta: dict[str, Any],
    trades: list[Trade],
    *,
    price_series: list[tuple[Any, float]] | None = None,
    overlays_data: dict[str, list[tuple[Any, float]]] | None = None,
) -> str:
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

    overlays = []
    m_over = meta.get("overlays")
    if isinstance(m_over, list):
        overlays = [str(x) for x in m_over]

    parts.append("<h2>Overlays</h2>")
    if overlays:
        parts.append("<ul>")
        for name in overlays:
            parts.append(f"<li>{name}</li>")
        parts.append("</ul>")
    else:
        parts.append("<p class='muted'>No overlays declared.</p>")

    # Sparkline (optional)
    if price_series:
        ee = [(t.entry_time, t.exit_time) for t in trades]
        svg = _spark_svg(price_series, overlays_data or {}, ee)
        if svg:
            parts.append("<h2>Price</h2>")
            parts.append(svg)

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
    run_path: Path,
    *,
    meta: dict[str, Any],
    trades: list[Trade],
    price_series: list[tuple[Any, float]] | None = None,
    overlays_data: dict[str, list[tuple[Any, float]]] | None = None,
) -> Path:
    """Write `report.html` under the given run_path and return the path."""
    out = run_path / "report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    html = generate_html_report(
        meta, trades, price_series=price_series, overlays_data=overlays_data
    )
    out.write_text(html)
    return out
