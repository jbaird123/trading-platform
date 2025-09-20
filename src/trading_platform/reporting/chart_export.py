from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HTML_TMPL = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>__TITLE__</title>
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <style>
    html,body{height:100%;margin:0}
    #c-main{height:60vh}
    #panels > div{height:180px;margin:8px 0}
    #tt{position:fixed;pointer-events:none;background:#000a;color:#fff;
      padding:4px 6px;border-radius:4px;font:12px system-ui,sans-serif;
      transform:translate(8px,8px);}
    #c-main{position:relative}
    #rmm-shades{position:absolute;inset:0;pointer-events:none;z-index:5}
    .rmm-shade{position:absolute;top:0;bottom:0}
    header{padding:8px 12px;font:14px/1.4 system-ui,sans-serif;
      border-bottom:1px solid #eee}
    header h1{margin:0;font-size:16px}
    header .sub{color:#666}
    #legend{font:12px/1.4 system-ui,sans-serif;padding:6px 12px;
      display:flex;flex-wrap:wrap;gap:12px;border-bottom:1px solid #eee}
    .lg-item{display:flex;align-items:center;gap:6px;color:#333}
    .sw{width:10px;height:10px;border-radius:2px;display:inline-block}
    #controls{font:12px/1.4 system-ui,sans-serif;padding:6px 12px;
      display:flex;align-items:center;gap:16px;border-bottom:1px solid #eee}
    #controls label{display:flex;align-items:center;gap:6px}
    #controls input[type=range]{width:140px}
  </style>
  <script src=
"https://unpkg.com/lightweight-charts@4.2.0/dist/
lightweight-charts.standalone.production.js"
  ></script>
</head>
<body>
  <header>
    <h1>__TITLE__</h1>
    <div class="sub" id="subtitle"></div>
  </header>
  <div id="legend"></div>
  <div id="controls">
    <label>Line width
      <input id="lw" type="range" min="1" max="9" step="1" value="5" />
      <span id="lw-val">5</span>
    </label>
  </div>
  <div id="c-main"><div id="rmm-shades"></div></div>
  <div id="panels"></div>
  <div id="tt" style="display:none"></div>
  <script id="equity" type="application/json">__EQUITY_JSON__</script>
  <script id="candles" type="application/json">__CANDLES_JSON__</script>
  <script id="trades" type="application/json">__TRADES_JSON__</script>
  <script id="features" type="application/json">__FEATURES_JSON__</script>
  <script id="rmm" type="application/json">__RMM_JSON__</script>
  <script>
    (function(){
      const el = document.getElementById('c-main');
      const rawEq = JSON.parse(
        document.getElementById('equity').textContent || '[]'
      );
      const eq = rawEq.map(([iso, v]) => ({
        time: Math.floor(Date.parse(iso)/1000), value: v
      }));
      const rawCd = JSON.parse(
        document.getElementById('candles').textContent || '[]'
      );
      const candles = rawCd.map(([iso,o,h,l,c]) => ({
        time: Math.floor(Date.parse(iso)/1000), open:o, high:h, low:l, close:c
      }));
      const trades = JSON.parse(
        document.getElementById('trades').textContent || '[]'
      );
      const chart = LightweightCharts.createChart(el, {
        layout:{textColor:'#222', background:{type:'solid', color:'#fff'}},
        rightPriceScale:{visible:true},
        // Allow deep compression; library will manage tick density
        timeScale:{ timeVisible:true, secondsVisible:false, minBarSpacing: 0.5 }
      });
      // Built-in zoom/pan: wheel zoom + drag pan
      chart.applyOptions({
        handleScale: {
          mouseWheel: true,
          pinch: true,
          axisPressedMouseMove: { time: true, price: true },
        },
        handleScroll: { mouseWheel: true, pressedMouseMove: true },
      });
      // Ensure crosshair behaves as expected
      chart.applyOptions({ crosshair: { mode: 0 } });
      let mainSeries = null;
      let candleSeries = null;
      const overlaySeries = [];
      const tradeLines = [];
      let currentLineWidth = 5;
      if (candles.length > 0) {
        candleSeries = chart.addCandlestickSeries({
          priceFormat: { type: 'price', precision: 4, minMove: 0.0001 }
        });
        candleSeries.setData(candles);
        mainSeries = candleSeries;
        const addEndpointTick = (timeSec, price, color) => {
          const base = (candles.length >= 2)
            ? Math.abs(candles[1].time - candles[0].time)
            : 60;
          const dt = Math.max(1, Math.floor(base / 10));
          const ls = chart.addLineSeries({
            color,
            lineWidth: currentLineWidth + 1,
            lastValueVisible: false,
            priceLineVisible: false,
          });
          ls.setData([
            { time: timeSec - dt, value: Number(price) },
            { time: timeSec + dt, value: Number(price) },
          ]);
          tradeLines.push(ls);
        };

        const rebuildTradeLines = () => {
          // Clear existing line series by creating new ones (library lacks remove)
          // Note: We keep references only for width updates after initial build.
          while (tradeLines.length) tradeLines.pop();
          trades.forEach(t => {
            const tEntry = Math.floor(Date.parse(t.entry_time)/1000);
            const tExit = Math.floor(Date.parse(t.exit_time)/1000);
            const win = Number(t.pnl || 0) > 0;
            const lineColor = win ? 'rgba(44,160,44,0.9)'
                                  : 'rgba(214,39,40,0.9)';
            const ls = chart.addLineSeries({
              color: lineColor,
              lineWidth: currentLineWidth,
              lastValueVisible: false,
              priceLineVisible: false,
            });
            ls.setData([
              { time: tEntry, value: Number(t.entry_price) },
              { time: tExit, value: Number(t.exit_price) },
            ]);
            tradeLines.push(ls);
            // Precise endpoint ticks centered on entry/exit
            addEndpointTick(tEntry, t.entry_price, lineColor);
            addEndpointTick(tExit, t.exit_price, lineColor);
          });
        };
        rebuildTradeLines();
        // No inexact price markers: rely on connector lines + endpoint ticks only.
      } else {
        const area = chart.addAreaSeries({
          lineColor:'#1f78b4', topColor:'rgba(31,120,180,0.25)',
          bottomColor:'rgba(31,120,180,0.05)'
        });
        area.setData(eq);
        mainSeries = area;
      }
      chart.timeScale().fitContent();
      // Infer interval from first two candles (in seconds)
      let intervalSec = null;
      if (candles.length >= 2) {
        intervalSec = (candles[1].time - candles[0].time);
      }
      // Subtitle: show inferred interval
      try {
        const sub = document.getElementById('subtitle');
        if (intervalSec != null) {
          const toLabel = (s) => {
            const abs = Math.abs(s);
            if (abs < 60) return `${abs}s`;
            if (abs < 3600) return `${Math.round(abs/60)}m`;
            if (abs < 86400) return `${Math.round(abs/3600)}h`;
            return `${Math.round(abs/86400)}d`;
          };
          sub.textContent = `Interval: ${toLabel(intervalSec)}`;
        }
      } catch (e) { /* noop */ }
      // Render overlays/panels from features.json
      try {
        const feat = JSON.parse(
          document.getElementById('features').textContent || '{}'
        );
        const seriesMap = feat.series || {};
        const meta = feat.meta || [];
        const overlayTypes = {
          SMA:1, EMA:1, WMA:1, BB:1, KC:1, VWAP:1, PSAR:1, HHV:1, LLV:1, DC:1
        };
        const palette = [
          '#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
          '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf'
        ];
        const pickColor = (key) => {
          let h = 0; const s = String(key);
          for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i))|0;
          const idx = Math.abs(h) % palette.length; return palette[idx];
        };
        const panelsEl = document.getElementById('panels');
        meta.forEach((m, idx) => {
          const t = String(m.type||'');
          const cols = m.columns || [];
          if (overlayTypes[t]) {
            cols.forEach((col) => {
              const s = chart.addLineSeries({
                lineWidth: 1, color: pickColor(col)
              });
              const data = (seriesMap[col]||[]).map(([iso, v]) => ({
                time: Math.floor(Date.parse(iso)/1000), value: v
              }));
              s.setData(data);
              overlaySeries.push({
                name: col,
                series: s,
                color: pickColor(col),
              });
            });
          } else {
            const div = document.createElement('div');
            div.id = `c-pan-${idx}`;
            div.style.height = '180px';
            panelsEl.appendChild(div);
            const ch = LightweightCharts.createChart(div, {
              layout:{
                textColor:'#222',
                background:{type:'solid', color:'#fff'}
              },
              rightPriceScale:{visible:true},
              timeScale:{secondsVisible:true}
            });
            cols.forEach((col) => {
              const ls = ch.addLineSeries({lineWidth:1});
              const data = (seriesMap[col]||[]).map(([iso, v]) => ({
                time: Math.floor(Date.parse(iso)/1000), value: v
              }));
              ls.setData(data);
            });
            ch.timeScale().fitContent();
          }
        });
      } catch (e) { /* ignore */ }
      // RMM shading bands
      (function(){
        const spans = JSON.parse(
          document.getElementById('rmm').textContent || '[]'
        );
        const shadesEl = document.getElementById('rmm-shades');
        // Ensure shades overlay sits on top of canvases
        if (shadesEl && el && shadesEl.parentElement !== el) {
          el.appendChild(shadesEl);
        } else if (shadesEl && el) {
          el.appendChild(shadesEl); // move to be last child
        }
        const colorFor = (m) => (
          m === 'long_only' ? 'rgba(46,204,113,0.15)'
          : m === 'short_only' ? 'rgba(231,76,60,0.15)'
          : m === 'both' ? 'rgba(52,152,219,0.12)'
          : 'rgba(127,127,127,0.10)'
        );
        const draw = () => {
          if (!shadesEl) return;
          shadesEl.innerHTML = '';
          spans.forEach(sp => {
            const t1 = Math.floor(Date.parse(sp.start)/1000);
            const t2 = Math.floor(Date.parse(sp.end)/1000);
            const x1 = chart.timeScale().timeToCoordinate(t1);
            const x2 = chart.timeScale().timeToCoordinate(t2);
            if (x1 == null || x2 == null) return;
            const left = Math.min(x1, x2);
            const width = Math.max(1, Math.abs(x2 - x1));
            const d = document.createElement('div');
            d.className = 'rmm-shade';
            d.style.left = `${left}px`;
            d.style.width = `${width}px`;
            d.style.background = colorFor(sp.mode);
            shadesEl.appendChild(d);
          });
        };
        const rerender = () => requestAnimationFrame(draw);
        const ts2 = chart.timeScale();
        ts2.subscribeVisibleTimeRangeChange(rerender);
        ts2.subscribeVisibleLogicalRangeChange(rerender);
        chart.subscribeSizeChange(rerender);
        requestAnimationFrame(draw);
      })();
      const legend = document.getElementById('legend');
      // Build static legend skeleton
      (function(){
        const items = [];
        items.push(
          `<span class="lg-item"><span class="sw" style="background:#444"></span>`+
          `<span id="lg-ohlc">OHLC</span></span>`
        );
        overlaySeries.forEach(it => {
          const safeName = it.name.replace(/[^a-zA-Z0-9_\-]/g,'_');
          const id = `lg-${safeName}`;
          items.push(
            `<span class="lg-item"><span class="sw"`+
            ` style="background:${it.color}"></span>`+
            `<span id="${id}">${it.name}: --</span></span>`
          );
        });
        legend.innerHTML = items.join('');
      })();
      const tt = document.getElementById('tt');
      const fmtHover = (ts) => {
        const d = new Date(ts * 1000);
        const pad = (n) => String(n).padStart(2, '0');
        const mm = pad(d.getMonth() + 1);
        const dd = pad(d.getDate());
        const yy = d.getFullYear();
        const hh = pad(d.getHours());
        const mi = pad(d.getMinutes());
        const ss = pad(d.getSeconds());
        // Format based on inferred interval
        const isDaily = intervalSec != null && intervalSec >= 86400;
        const isHourly = (
          intervalSec != null && intervalSec >= 3600 && intervalSec < 86400
        );
        const isMinute = intervalSec != null && intervalSec >= 60 && intervalSec < 3600;
        if (isDaily) {
          // Daily: date only, no timezone
          return `${mm}/${dd}/${yy}`;
        }
        // For sub-daily intervals include timezone
        let tz = '';
        try {
          const parts = new Intl.DateTimeFormat('en-US', { timeZoneName: 'short' })
            .formatToParts(d);
          const p = parts.find(x => x.type === 'timeZoneName');
          if (p && p.value) tz = ` ${p.value}`;
        } catch(e) {}
        if (isHourly) {
          // Hourly: minutes shown as 00
          return `${mm}/${dd}/${yy} ${hh}:00${tz}`;
        }
        if (isMinute) {
          // Minute bars: no seconds
          return `${mm}/${dd}/${yy} ${hh}:${mi}${tz}`;
        }
        // Default to full time with seconds
        return `${mm}/${dd}/${yy} ${hh}:${mi}:${ss}${tz}`;
      };
      chart.subscribeCrosshairMove(param => {
        if (!param || !param.time || !mainSeries) {
          tt.style.display = 'none';
          return;
        }
        const sp = param.seriesPrices.get(mainSeries);
        const y = (typeof sp === 'number') ? sp : (sp?.close ?? 0);
        const t = fmtHover(param.time);
        tt.textContent = `${t}  ${y}`;
        tt.style.left = `${param.point.x}px`;
        tt.style.top = `${param.point.y}px`;
        tt.style.display = 'block';
        // Update legend (OHLC + overlays)
        if (sp && typeof sp === 'object') {
          const o = (sp.open ?? null);
          const h = (sp.high ?? null);
          const l = (sp.low ?? null);
          const c = (sp.close ?? null);
          const ohlc = [o,h,l,c].every(v => v != null)
            ? `O ${o.toFixed(4)}  H ${h.toFixed(4)}`+
              `  L ${l.toFixed(4)}  C ${c.toFixed(4)}`
            : `C ${y.toFixed ? y.toFixed(4) : y}`;
          const ohlcEl = document.getElementById('lg-ohlc');
          if (ohlcEl) ohlcEl.textContent = ohlc;
        }
        overlaySeries.forEach(it => {
          const val = param.seriesPrices.get(it.series);
          if (val == null) return;
          const v = (typeof val === 'number') ? val : (val?.value ?? null);
          if (v == null) return;
          const safeName = it.name.replace(/[^a-zA-Z0-9_\-]/g,'_');
          const id = `lg-${safeName}`;
          const itemEl = document.getElementById(id);
          if (itemEl) itemEl.textContent = `${it.name}: ${Number(v).toFixed(4)}`;
        });
      });

      // Note: Using library's native wheel zoom to ensure reliability.

      // Controls: line width and dot size
      const lw = document.getElementById('lw');
      const lwVal = document.getElementById('lw-val');
      lw.addEventListener('input', () => {
        currentLineWidth = Number(lw.value) || 1;
        lwVal.textContent = String(currentLineWidth);
        tradeLines.forEach(s => s.applyOptions({ lineWidth: currentLineWidth }));
      });
    })();
  </script>
</body>
</html>
"""


def _read_prices_csv(run_path: Path) -> list[list[Any]]:
    p = run_path / "prices.csv"
    if not p.exists():
        return []
    rows: list[list[Any]] = []
    for line in p.read_text().splitlines()[1:]:
        # Expect: time,open,high,low,close
        parts = [x.strip() for x in line.split(",")]
        if len(parts) < 5:
            continue
        iso, o, h, lo, c = parts[:5]
        try:
            rows.append([iso, float(o), float(h), float(lo), float(c)])
        except Exception:
            continue
    return rows


def save_chart_from_brief(run_path: Path) -> Path:
    """Render a lightweight-charts HTML from run's brief.json.

    Uses equity curve from brief to provide a fast, dependency-free chart.
    """
    brief_path = run_path / "brief.json"
    data: dict[str, Any] = json.loads(brief_path.read_text())
    eq = data.get("equity_stats", {}).get("equity_curve", [])
    trades = data.get("trades", [])
    candles = _read_prices_csv(run_path)
    # Features.json is optional; embed empty when missing
    fpath = run_path / "features.json"
    features_json = fpath.read_text() if fpath.exists() else "{}"
    title = "Run Charts"
    try:
        meta = data.get("meta", {}) if isinstance(data, dict) else {}
        sname = meta.get("strategy_name")
        rid = meta.get("run_id")
        title = f"{sname} – {rid}" if sname and rid else (sname or rid or title)
    except Exception:
        pass
    html = (
        HTML_TMPL.replace("__TITLE__", title)
        .replace("__EQUITY_JSON__", json.dumps(eq))
        .replace("__CANDLES_JSON__", json.dumps(candles))
        .replace("__TRADES_JSON__", json.dumps(trades))
        .replace("__FEATURES_JSON__", features_json)
        .replace(
            "__RMM_JSON__",
            (run_path / "rmm_spans.json").read_text()
            if (run_path / "rmm_spans.json").exists()
            else "[]",
        )
    )
    out = run_path / "chart.html"
    out.write_text(html)
    return out


def save_features_for_chart(
    run_path: Path, feature_df: Any, feature_specs: list[dict]
) -> Path:
    """Persist features used by the strategy for chart rendering.

    Writes `features.json` containing meta (name,type,columns) and
    time-aligned series data per column.
    """
    import pandas as pd  # local to avoid heavy import at module load

    df = feature_df if isinstance(feature_df, pd.DataFrame) else None
    if df is None or df.empty:
        out = run_path / "features.json"
        out.write_text("{}")
        return out

    def _cols(name: str, typ: str) -> list[str]:
        t = typ.upper()
        if t == "BB":
            return [f"{name}_upper", f"{name}_lower", f"{name}_middle"]
        if t == "KC":
            return [f"{name}_upper", f"{name}_lower", f"{name}_middle"]
        if t == "MACD":
            return [f"{name}_macd", f"{name}_signal", f"{name}_diff"]
        if t == "STOCH":
            return [name, f"{name}_signal"]
        if t == "PSAR":
            return [name, f"{name}_up", f"{name}_down"]
        if t == "DC":
            return [f"{name}_upper", f"{name}_lower"]
        return [name]

    meta: list[dict[str, Any]] = []
    series: dict[str, list[list[Any]]] = {}
    idx = df.index
    times = [str(getattr(ts, "isoformat", lambda: str(ts))()) for ts in idx]
    for spec in feature_specs or []:
        name = str(spec.get("name", "")).strip()
        typ = str(spec.get("type", "")).strip()
        if not name or not typ:
            continue
        cols = [c for c in _cols(name, typ) if c in df.columns]
        if not cols:
            continue
        meta.append({"name": name, "type": typ, "columns": cols})
        for col in cols:
            vals = df[col].tolist()
            arr: list[list[Any]] = []
            for t, v in zip(times, vals):
                try:
                    fv = float(v)
                except Exception:
                    continue
                arr.append([t, fv])
            series[col] = arr
    payload = {"meta": meta, "series": series}
    out = run_path / "features.json"
    out.write_text(json.dumps(payload))
    return out
