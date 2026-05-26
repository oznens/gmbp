"""Static dashboard generator: paper_trade_log.json + OKX canli verisi -> docs/index.html.

GitHub Actions cron her run'da bu scripti calistirir, docs/index.html
guncellenirse commit eder. GitHub Pages 'docs/' klasorunden serve ediyor.

Kullanim:
    .venv/bin/python dashboard_build.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

OUT_PATH = Path("docs/index.html")
LOG_PATH = Path("paper_trade_log.json")


def fmt(v, prec=2, default="—"):
    try:
        return f"{float(v):.{prec}f}"
    except Exception:
        return default


def fetch_okx_state() -> Dict:
    """Returns dict with balance, positions, last_error. Sessizce skip eder credentials yoksa.
    DASHBOARD_MODE=simulated ise OKX'e bag­lanmaz."""
    out: Dict = {"balance": None, "positions": [], "error": None}
    if os.environ.get("DASHBOARD_MODE", "").lower() == "simulated":
        out["error"] = "simulated_mode"
        return out
    key = os.environ.get("OKX_API_KEY", "")
    sec = os.environ.get("OKX_API_SECRET", "")
    pp = os.environ.get("OKX_PASSPHRASE", "")
    demo = (os.environ.get("OKX_DEMO", "true").lower() == "true")
    if not (key and sec and pp):
        out["error"] = "credentials_missing"
        return out
    try:
        sys.path.insert(0, ".")
        from utils.okx_client import OKXClient
        c = OKXClient(api_key=key, api_secret=sec, passphrase=pp, demo=demo)
        out["balance"] = c.get_balance()
        positions = c.get_positions()
        # Mark price + uPNL zaten get_positions'ta var
        for p in positions:
            out["positions"].append({
                "instId": p["instId"], "side": p["side"], "size": p["size"],
                "avg_px": p["avg_px"], "u_pnl": p["u_pnl"], "lev": p["lev"],
            })
    except Exception as e:
        out["error"] = str(e)[:200]
    return out


def aggregate(log: List[Dict]) -> Dict:
    closed = [e for e in log if e.get("status") == "closed"]
    placed = [e for e in log if e.get("status") == "placed"]
    errors = [e for e in log if e.get("status") == "error"]
    closed.sort(key=lambda e: e.get("close_ts", 0))
    wins = sum(1 for e in closed if e.get("outcome") == "WIN")
    net_r = sum(float(e.get("r_multiple") or 0) for e in closed)
    net_usdt = sum(float(e.get("realized_pnl") or 0) for e in closed)
    wr = (wins / len(closed) * 100) if closed else 0.0
    # Equity curve
    cum_r, cum_usdt = [], []
    s_r, s_p = 0.0, 0.0
    for e in closed:
        s_r += float(e.get("r_multiple") or 0)
        s_p += float(e.get("realized_pnl") or 0)
        cum_r.append(s_r); cum_usdt.append(s_p)
    # Drawdown
    peak, max_dd = 0.0, 0.0
    for x in cum_r:
        peak = max(peak, x)
        max_dd = min(max_dd, x - peak)
    # Per-model
    by_model: Dict[str, Dict] = {}
    for e in closed:
        m = e.get("model", "?")
        r = float(e.get("r_multiple") or 0)
        d = by_model.setdefault(m, {"n": 0, "wins": 0, "net": 0.0, "net_usdt": 0.0})
        d["n"] += 1
        if e.get("outcome") == "WIN":
            d["wins"] += 1
        d["net"] += r
        d["net_usdt"] += float(e.get("realized_pnl") or 0)
    for m, d in by_model.items():
        d["wr"] = (d["wins"] / d["n"] * 100) if d["n"] else 0.0
    return {
        "closed": closed, "placed": placed, "errors": errors,
        "n_closed": len(closed), "n_open": len(placed), "n_err": len(errors),
        "wr": wr, "net_r": net_r, "net_usdt": net_usdt, "max_dd": max_dd,
        "cum_r": cum_r, "cum_usdt": cum_usdt,
        "by_model": by_model,
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ICT Paper Trade Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:#0f1115; --card:#181b22; --line:#22262f; --text:#e8eaed; --muted:#8c93a3;
    --green:#22c55e; --red:#ef4444; --blue:#3b82f6; --orange:#f59e0b;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--text);
       font:14px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
  header{{padding:18px 24px;border-bottom:1px solid var(--line);
         display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}}
  h1{{margin:0;font-size:18px;font-weight:600}}
  .updated{{color:var(--muted);font-size:12px}}
  main{{padding:20px 24px;max-width:1400px;margin:0 auto}}
  .grid{{display:grid;gap:16px}}
  .kpi-grid{{grid-template-columns:repeat(auto-fit,minmax(170px,1fr));margin-bottom:20px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
  .kpi .label{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px}}
  .kpi .value{{font-size:22px;font-weight:700;margin-top:6px}}
  .kpi .sub{{color:var(--muted);font-size:11px;margin-top:2px}}
  .green{{color:var(--green)}} .red{{color:var(--red)}} .blue{{color:var(--blue)}}
  .orange{{color:var(--orange)}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{text-align:left;color:var(--muted);font-weight:500;font-size:11px;
      text-transform:uppercase;letter-spacing:.5px;padding:8px 10px;border-bottom:1px solid var(--line)}}
  td{{padding:9px 10px;border-bottom:1px solid #1d2028}}
  tr:last-child td{{border-bottom:0}}
  .tag{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600}}
  .tag-long{{background:rgba(34,197,94,.15);color:var(--green)}}
  .tag-short{{background:rgba(239,68,68,.15);color:var(--red)}}
  .tag-win{{background:rgba(34,197,94,.15);color:var(--green)}}
  .tag-loss{{background:rgba(239,68,68,.15);color:var(--red)}}
  .charts{{grid-template-columns:1fr;gap:16px;margin:20px 0}}
  .two-col{{grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:16px}}
  .section-title{{font-size:12px;color:var(--muted);text-transform:uppercase;
                  letter-spacing:.5px;margin:0 0 10px}}
  .error{{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);
         color:var(--red);padding:10px 14px;border-radius:8px;margin-bottom:16px;font-size:13px}}
  .muted{{color:var(--muted)}}
  canvas{{max-height:280px}}
  .empty{{padding:24px;text-align:center;color:var(--muted)}}
  @media(max-width:600px){{
    main{{padding:14px}}
    .kpi .value{{font-size:18px}}
    th,td{{padding:6px 6px;font-size:12px}}
  }}
</style>
</head>
<body>
<header>
  <h1>📊 ICT Paper Trade Dashboard <span style="font-size:13px;color:#7aa;font-weight:400">· MEXC simulation</span></h1>
  <span class="updated">Son guncelleme: <b>{updated}</b> UTC</span>
</header>
<main>

{error_banner}

<!-- KPI -->
<div class="grid kpi-grid">
  <div class="card kpi">
    <div class="label">Bakiye</div>
    <div class="value">{balance} <span class="muted" style="font-size:13px">USDT</span></div>
    <div class="sub">{balance_source}</div>
  </div>
  <div class="card kpi">
    <div class="label">Net R</div>
    <div class="value {net_r_class}">{net_r_str}</div>
    <div class="sub">Toplam {n_closed} kapali trade</div>
  </div>
  <div class="card kpi">
    <div class="label">Net USDT (gerceklesen)</div>
    <div class="value {net_usdt_class}">{net_usdt_str}</div>
    <div class="sub">Sadece kapanan trade'ler</div>
  </div>
  <div class="card kpi">
    <div class="label">Win-rate</div>
    <div class="value">{wr_str}<span class="muted" style="font-size:13px"> %</span></div>
    <div class="sub">{n_wins} W / {n_losses} L</div>
  </div>
  <div class="card kpi">
    <div class="label">Max Drawdown</div>
    <div class="value red">{max_dd_str}<span class="muted" style="font-size:13px"> R</span></div>
    <div class="sub">En kotu cekilme</div>
  </div>
  <div class="card kpi">
    <div class="label">Acik Pozisyon</div>
    <div class="value blue">{n_open_live}</div>
    <div class="sub">{n_open_log} log'ta · OKX'te canli</div>
  </div>
</div>

<!-- Charts -->
<div class="grid charts">
  <div class="card">
    <div class="section-title">Equity Curve (Cumulative R)</div>
    <canvas id="equity"></canvas>
  </div>
  <div class="grid two-col">
    <div class="card">
      <div class="section-title">Drawdown (R)</div>
      <canvas id="dd"></canvas>
    </div>
    <div class="card">
      <div class="section-title">Per-Model Breakdown</div>
      {model_table}
    </div>
  </div>
</div>

<!-- Open positions -->
<div class="card" style="margin-top:20px">
  <div class="section-title">🟢 Acik Pozisyonlar (OKX canli)</div>
  {open_table}
</div>

<!-- Closed trades -->
<div class="card" style="margin-top:16px">
  <div class="section-title">📜 Son Kapanan Trade'ler</div>
  {closed_table}
</div>

</main>

<script>
const EQUITY_LABELS = {equity_labels_json};
const EQUITY_R = {equity_r_json};
const DD_DATA = {dd_json};

function makeChart(id, opts) {{
  const ctx = document.getElementById(id);
  if (!ctx) return;
  new Chart(ctx, opts);
}}

const baseOpts = {{
  responsive: true, maintainAspectRatio: false,
  plugins: {{ legend: {{ display:false }}, tooltip: {{ mode:'index', intersect:false }} }},
  scales: {{
    x: {{ ticks: {{ color: '#8c93a3', maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }},
          grid: {{ color: '#1d2028' }} }},
    y: {{ ticks: {{ color: '#8c93a3' }}, grid: {{ color: '#1d2028' }} }},
  }},
  interaction: {{ intersect: false, mode: 'index' }},
}};

if (EQUITY_LABELS.length) {{
  makeChart('equity', {{
    type: 'line',
    data: {{ labels: EQUITY_LABELS,
             datasets: [{{ label: 'Cumulative R', data: EQUITY_R,
                           borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,.1)',
                           fill: true, tension: 0.2, pointRadius: 2 }}] }},
    options: baseOpts,
  }});
  makeChart('dd', {{
    type: 'line',
    data: {{ labels: EQUITY_LABELS,
             datasets: [{{ label: 'Drawdown', data: DD_DATA,
                           borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,.15)',
                           fill: true, tension: 0.1, pointRadius: 0 }}] }},
    options: baseOpts,
  }});
}}
</script>
</body>
</html>
"""


def render_open_positions(live_positions: List[Dict], log_placed: List[Dict]) -> str:
    """Live OKX pozisyonlari ile log'daki SL/TP'leri eslestir."""
    by_inst = {p["instId"]: p for p in live_positions}
    rows = []
    for lp in log_placed:
        inst_id = lp.get("instId")
        live = by_inst.get(inst_id)
        if not live:
            continue  # log diyor 'placed' ama OKX'te kapali -- reconcile bekleniyor
        side = lp["direction"]
        side_tag = "tag-long" if side == "LONG" else "tag-short"
        upnl = live["u_pnl"]
        upnl_cls = "green" if upnl >= 0 else "red"
        rows.append(f"""<tr>
            <td><b>{lp["symbol"]}</b></td>
            <td><span class="tag {side_tag}">{side}</span></td>
            <td>{lp.get("model","-")}</td>
            <td>{fmt(live["avg_px"],4)}</td>
            <td>{fmt(lp.get("stop"),4)}</td>
            <td>{fmt(lp.get("tp"),4)}</td>
            <td>{fmt(live["size"],4)}</td>
            <td class="{upnl_cls}">{upnl:+.2f}</td>
        </tr>""")
    if not rows:
        return '<div class="empty">Acik pozisyon yok.</div>'
    return f"""<table>
        <thead><tr><th>Sembol</th><th>Yon</th><th>Model</th><th>Avg Entry</th>
                  <th>SL</th><th>TP</th><th>Size</th><th>uPNL (USDT)</th></tr></thead>
        <tbody>{"".join(rows)}</tbody></table>"""


def render_closed_trades(closed: List[Dict], limit: int = 50) -> str:
    if not closed:
        return '<div class="empty">Henuz kapanmis trade yok. Cron birkac kez tetiklendikten sonra burada gorunecek.</div>'
    rows = []
    for e in reversed(closed[-limit:]):
        side = e.get("direction", "?")
        side_tag = "tag-long" if side == "LONG" else "tag-short"
        outcome = e.get("outcome", "?")
        out_tag = "tag-win" if outcome == "WIN" else "tag-loss"
        r = float(e.get("r_multiple") or 0)
        r_cls = "green" if r > 0 else "red"
        ct = e.get("close_ts")
        ct_str = "-"
        if ct:
            try:
                ct_str = datetime.fromtimestamp(int(ct)/1000, tz=timezone.utc).strftime("%m-%d %H:%M")
            except Exception:
                pass
        rows.append(f"""<tr>
            <td>{ct_str}</td>
            <td><b>{e.get("symbol","-")}</b></td>
            <td><span class="tag {side_tag}">{side}</span></td>
            <td>{e.get("model","-")}</td>
            <td><span class="tag {out_tag}">{outcome}</span></td>
            <td class="{r_cls}">{r:+.2f}</td>
            <td class="{r_cls}">{float(e.get("realized_pnl") or 0):+.2f}</td>
            <td>{fmt(e.get("entry"),4)}</td>
            <td>{fmt(e.get("close_price"),4)}</td>
        </tr>""")
    return f"""<table>
        <thead><tr><th>Kapanis</th><th>Sembol</th><th>Yon</th><th>Model</th>
                  <th>Sonuc</th><th>R</th><th>PnL</th><th>Entry</th><th>Exit</th></tr></thead>
        <tbody>{"".join(rows)}</tbody></table>"""


def render_model_table(by_model: Dict) -> str:
    if not by_model:
        return '<div class="empty">Veri yok</div>'
    rows = []
    for m, d in sorted(by_model.items(), key=lambda kv: -kv[1]["net"]):
        net_cls = "green" if d["net"] > 0 else "red"
        rows.append(f"""<tr>
            <td><b>{m}</b></td>
            <td>{d["n"]}</td>
            <td>{d["wr"]:.1f}%</td>
            <td class="{net_cls}">{d["net"]:+.2f}R</td>
            <td class="{net_cls}">{d["net_usdt"]:+.2f}</td>
        </tr>""")
    return f"""<table>
        <thead><tr><th>Model</th><th>n</th><th>WR</th><th>Net R</th><th>Net USDT</th></tr></thead>
        <tbody>{"".join(rows)}</tbody></table>"""


def main():
    if not LOG_PATH.exists():
        log: List[Dict] = []
    else:
        log = json.loads(LOG_PATH.read_text())
    agg = aggregate(log)
    okx = fetch_okx_state()
    simulated_mode = (os.environ.get("DASHBOARD_MODE", "").lower() == "simulated")

    n_wins = sum(1 for e in agg["closed"] if e.get("outcome") == "WIN")
    n_losses = agg["n_closed"] - n_wins

    error_banner = ""
    if okx["error"] and okx["error"] not in ("credentials_missing", "simulated_mode"):
        error_banner = f'<div class="error">⚠️ OKX baglanti hatasi: <code>{okx["error"]}</code></div>'

    if simulated_mode:
        starting = 5000.0
        bal = starting + agg["net_usdt"]
        bal_str = fmt(bal, 2)
        bal_source = f"simule (MEXC) · baslangic {starting:.0f}"
    else:
        bal = okx["balance"]
        bal_str = fmt(bal, 2) if bal is not None else "—"
        bal_source = "canli" if bal is not None else (
            "credentials yok" if okx["error"] == "credentials_missing" else "baglanti hatasi"
        )

    # Equity curve labels (close timestamps)
    labels = []
    for e in agg["closed"]:
        ct = e.get("close_ts")
        if ct:
            try:
                labels.append(datetime.fromtimestamp(int(ct)/1000, tz=timezone.utc).strftime("%m-%d %H:%M"))
                continue
            except Exception:
                pass
        labels.append("?")
    # Drawdown
    dd = []
    peak = 0
    for x in agg["cum_r"]:
        peak = max(peak, x)
        dd.append(round(x - peak, 4))

    html = HTML_TEMPLATE.format(
        updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        error_banner=error_banner,
        balance=bal_str, balance_source=bal_source,
        net_r_str=f"{agg['net_r']:+.2f}",
        net_r_class=("green" if agg["net_r"] > 0 else "red"),
        net_usdt_str=f"{agg['net_usdt']:+.2f}",
        net_usdt_class=("green" if agg["net_usdt"] > 0 else "red"),
        wr_str=f"{agg['wr']:.1f}",
        n_wins=n_wins, n_losses=n_losses,
        max_dd_str=f"{agg['max_dd']:+.2f}",
        n_open_live=len(okx["positions"]),
        n_open_log=agg["n_open"],
        n_closed=agg["n_closed"],
        equity_labels_json=json.dumps(labels),
        equity_r_json=json.dumps([round(x, 4) for x in agg["cum_r"]]),
        dd_json=json.dumps(dd),
        model_table=render_model_table(agg["by_model"]),
        open_table=render_open_positions(okx["positions"], agg["placed"]),
        closed_table=render_closed_trades(agg["closed"]),
    )

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard yazildi: {OUT_PATH} ({len(html)} bytes)")
    print(f"  closed={agg['n_closed']} placed={agg['n_open']} balance={bal_str} netR={agg['net_r']:+.2f}")


if __name__ == "__main__":
    main()
