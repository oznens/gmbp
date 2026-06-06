"""Static dashboard generator: paper_trade_log.json + OKX canli verisi -> docs/index.html."""
from __future__ import annotations

import base64
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

OUT_PATH = Path("docs/index.html")
LOG_PATH = Path("paper_trade_log.json")


def generate_trade_chart(entry: Dict) -> str:
    """Trade setup'ı için OKX'ten 4H mum verisi çek, entry/SL/TP işaretli PNG üret.
    Returns base64 string or empty string on failure."""
    try:
        sys.path.insert(0, ".")
        from utils.okx_fetcher import OKXFetcher
        sym = entry.get("symbol", "")
        if not sym:
            return ""
        fetcher = OKXFetcher()
        df = fetcher.fetch_ohlcv(sym, "4h", limit=80)
        if df is None or len(df) < 10:
            return ""

        bar_time_raw = entry.get("bar_time")
        entry_price = float(entry.get("entry") or 0)
        sl = float(entry.get("stop") or 0)
        tp = float(entry.get("tp") or 0)
        direction = entry.get("direction", "LONG")
        outcome = entry.get("outcome", "")
        close_price = float(entry.get("close_price") or 0)

        if not entry_price:
            return ""

        # Bar_time yakınındaki indeksi bul
        center_idx = len(df) - 1
        if bar_time_raw:
            try:
                bt = pd.Timestamp(bar_time_raw).tz_localize(None) if hasattr(pd.Timestamp(bar_time_raw), 'tzinfo') else pd.Timestamp(bar_time_raw)
                df_idx = df.index.tz_localize(None) if df.index.tzinfo else df.index
                diffs = abs(df_idx - bt)
                center_idx = int(diffs.argmin())
            except Exception:
                pass

        start = max(0, center_idx - 20)
        end = min(len(df), center_idx + 25)
        view = df.iloc[start:end].reset_index()
        view.columns = ["time"] + list(df.columns)
        ci = center_idx - start  # entry bar'ın view içindeki indeksi

        fig, ax = plt.subplots(figsize=(9, 3.5))
        fig.patch.set_facecolor("#0f1115")
        ax.set_facecolor("#181b22")

        for i, row in view.iterrows():
            color = "#22c55e" if row["close"] >= row["open"] else "#ef4444"
            ax.plot([i, i], [row["low"], row["high"]], color=color, lw=0.8, alpha=0.7)
            body = abs(row["close"] - row["open"]) or (row["high"] - row["low"]) * 0.01
            ax.add_patch(plt.Rectangle(
                (i - 0.38, min(row["open"], row["close"])),
                0.76, body, color=color, alpha=0.9
            ))

        # Fiyat seviyeleri
        ax.axhline(entry_price, color="#60a5fa", lw=1.0, ls="--", alpha=0.9, label=f"Entry {entry_price:.4f}")
        ax.axhline(sl,          color="#f87171", lw=0.9, ls=":",  alpha=0.8, label=f"SL {sl:.4f}")
        ax.axhline(tp,          color="#4ade80", lw=0.9, ls=":",  alpha=0.8, label=f"TP {tp:.4f}")

        # Shaded risk/reward zone
        if direction == "LONG":
            ax.axhspan(sl, entry_price, alpha=0.06, color="#ef4444")
            ax.axhspan(entry_price, tp, alpha=0.06, color="#22c55e")
        else:
            ax.axhspan(entry_price, sl, alpha=0.06, color="#ef4444")
            ax.axhspan(tp, entry_price, alpha=0.06, color="#22c55e")

        # Entry marker
        marker = "^" if direction == "LONG" else "v"
        ax.scatter(ci, entry_price, marker=marker, color="#60a5fa", s=80, zorder=6)

        # Exit marker
        if outcome in ("WIN", "LOSS") and close_price:
            close_color = "#22c55e" if outcome == "WIN" else "#ef4444"
            close_idx_view = min(end - start - 1, ci + 15)
            ax.scatter(close_idx_view, close_price, marker="x", color=close_color, s=80, zorder=6, linewidths=2)

        # Eksen stilleri
        n_ticks = min(6, len(view))
        tick_pos = [int(i * (len(view) - 1) / max(n_ticks - 1, 1)) for i in range(n_ticks)]
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(
            [view.loc[p, "time"].strftime("%m-%d %Hh") for p in tick_pos],
            rotation=25, fontsize=7, color="#8c93a3"
        )
        ax.tick_params(axis="y", colors="#8c93a3", labelsize=7)
        for spine in ax.spines.values():
            spine.set_color("#22262f")

        patches = [
            mpatches.Patch(color="#60a5fa", label=f"Entry {entry_price:.4f}"),
            mpatches.Patch(color="#f87171", label=f"SL {sl:.4f}"),
            mpatches.Patch(color="#4ade80", label=f"TP {tp:.4f}"),
        ]
        ax.legend(handles=patches, loc="upper left", fontsize=7, framealpha=0.3,
                  facecolor="#1a1d26", labelcolor="#e8eaed")
        ax.set_title(f"{sym} 4H — {direction}", color="#e8eaed", fontsize=9, pad=6)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", facecolor=fig.get_facecolor())
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        return b64
    except Exception:
        return ""


def fmt(v, prec=2, default="—"):
    try:
        return f"{float(v):.{prec}f}"
    except Exception:
        return default


def fetch_okx_state() -> Dict:
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
        for p in c.get_positions():
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
    closed.sort(key=lambda e: e.get("close_ts", 0))
    wins = sum(1 for e in closed if e.get("outcome") == "WIN")
    net_r = sum(float(e.get("r_multiple") or 0) for e in closed)
    net_usdt = sum(float(e.get("realized_pnl") or 0) for e in closed)
    wr = (wins / len(closed) * 100) if closed else 0.0
    cum_r: List[float] = []
    s_r = 0.0
    for e in closed:
        s_r += float(e.get("r_multiple") or 0)
        cum_r.append(s_r)
    peak, max_dd = 0.0, 0.0
    for x in cum_r:
        peak = max(peak, x)
        max_dd = min(max_dd, x - peak)
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
    for d in by_model.values():
        d["wr"] = (d["wins"] / d["n"] * 100) if d["n"] else 0.0
    return {
        "closed": closed, "placed": placed,
        "n_closed": len(closed), "n_open": len(placed),
        "wr": wr, "net_r": net_r, "net_usdt": net_usdt, "max_dd": max_dd,
        "cum_r": cum_r, "by_model": by_model,
    }


def render_open_positions(live_positions: List[Dict], log_placed: List[Dict]) -> str:
    by_inst = {p["instId"]: p for p in live_positions}
    rows = []
    for lp in log_placed:
        live = by_inst.get(lp.get("instId"))
        if not live:
            continue
        side = lp["direction"]
        side_tag = "tag-long" if side == "LONG" else "tag-short"
        upnl = live["u_pnl"]
        upnl_cls = "green" if upnl >= 0 else "red"
        lev = lp.get("leverage") or live.get("lev") or "—"
        rows.append(
            f'<tr>'
            f'<td><b>{lp["symbol"]}</b></td>'
            f'<td><span class="tag {side_tag}">{side}</span></td>'
            f'<td>{lp.get("model", "-")}</td>'
            f'<td>{fmt(live["avg_px"], 4)}</td>'
            f'<td style="color:#ef4444">{fmt(lp.get("stop"), 4)}</td>'
            f'<td style="color:#22c55e">{fmt(lp.get("tp"), 4)}</td>'
            f'<td>{fmt(live["size"], 0)}</td>'
            f'<td style="color:#f59e0b">{lev}x</td>'
            f'<td class="{upnl_cls}">{upnl:+.2f}</td>'
            f'</tr>'
        )
    if not rows:
        return '<div class="empty">Acik pozisyon yok.</div>'
    header = ('<table><thead><tr>'
              '<th>Sembol</th><th>Yon</th><th>Model</th><th>Entry</th>'
              '<th>SL</th><th>TP</th><th>Size</th><th>Lev</th><th>uPNL</th>'
              '</tr></thead>')
    return header + '<tbody>' + ''.join(rows) + '</tbody></table>'


def render_closed_trades(closed: List[Dict], limit: int = 100) -> str:
    if not closed:
        return '<div class="empty">Henuz kapanmis trade yok.</div>'
    rows = []
    for i, e in enumerate(reversed(closed[-limit:])):
        orig_idx = len(closed) - 1 - i
        side = e.get("direction", "?")
        side_tag = "tag-long" if side == "LONG" else "tag-short"
        outcome = e.get("outcome", "?")
        out_tag = "tag-win" if outcome == "WIN" else "tag-loss"
        r = float(e.get("r_multiple") or 0)
        r_cls = "green" if r > 0 else "red"
        ct = e.get("close_ts")
        ct_str = "—"
        if ct:
            try:
                ct_str = datetime.fromtimestamp(int(ct) / 1000, tz=timezone.utc).strftime("%m-%d %H:%M")
            except Exception:
                pass
        lev = e.get("leverage")
        lev_str = f'{lev}x' if lev else "—"
        pnl = float(e.get("realized_pnl") or 0)
        rows.append(
            f'<tr class="trade-row" onclick="showTrade({orig_idx})" title="Detay icin tikla">'
            f'<td>{ct_str}</td>'
            f'<td><b>{e.get("symbol", "—")}</b></td>'
            f'<td><span class="tag {side_tag}">{side}</span></td>'
            f'<td>{e.get("model", "—")}</td>'
            f'<td><span class="tag {out_tag}">{outcome}</span></td>'
            f'<td class="{r_cls}">{r:+.2f}</td>'
            f'<td class="{r_cls}">{pnl:+.2f}</td>'
            f'<td>{fmt(e.get("entry"), 4)}</td>'
            f'<td style="color:#ef4444">{fmt(e.get("stop"), 4)}</td>'
            f'<td style="color:#22c55e">{fmt(e.get("tp"), 4)}</td>'
            f'<td style="color:#f59e0b">{lev_str}</td>'
            f'<td>{fmt(e.get("close_price"), 4)}</td>'
            f'</tr>'
        )
    header = ('<table><thead><tr>'
              '<th>Kapanis</th><th>Sembol</th><th>Yon</th><th>Model</th>'
              '<th>Sonuc</th><th>R</th><th>PnL</th>'
              '<th>Entry</th><th style="color:#ef4444">SL</th>'
              '<th style="color:#22c55e">TP</th><th>Lev</th><th>Exit</th>'
              '</tr></thead>')
    return header + '<tbody>' + ''.join(rows) + '</tbody></table>'


def render_model_table(by_model: Dict) -> str:
    if not by_model:
        return '<div class="empty">Veri yok</div>'
    rows = []
    for m, d in sorted(by_model.items(), key=lambda kv: -kv[1]["net"]):
        net_cls = "green" if d["net"] > 0 else "red"
        rows.append(
            f'<tr><td><b>{m}</b></td><td>{d["n"]}</td>'
            f'<td>{d["wr"]:.1f}%</td>'
            f'<td class="{net_cls}">{d["net"]:+.2f}R</td>'
            f'<td class="{net_cls}">{d["net_usdt"]:+.2f}</td></tr>'
        )
    return ('<table><thead><tr>'
            '<th>Model</th><th>n</th><th>WR</th><th>Net R</th><th>Net USDT</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>')


# JavaScript is kept as a plain string (no Python f-string) to avoid brace escaping issues.
# __TRADES__, __EQ_LABELS__, __EQ_R__, __DD__ are replaced by main().
_JS = r"""
const TRADES = __TRADES__;
const EQ_LABELS = __EQ_LABELS__;
const EQ_R = __EQ_R__;
const DD = __DD__;

function p(v, d) {
  return (v == null) ? '—' : parseFloat(v).toFixed(d || 2);
}

function showTrade(idx) {
  const t = TRADES[idx];
  if (!t) return;
  const side = t.direction || '?';
  const sc = side === 'LONG' ? '#22c55e' : '#ef4444';
  const outcome = t.outcome || '';
  const oc = outcome === 'WIN' ? '#22c55e' : '#ef4444';
  const sym = (t.symbol || t.instId || '?').replace('-USDT-SWAP', 'USDT');
  const base = sym.replace('USDT', '');
  const tvUrl = 'https://www.tradingview.com/chart/?symbol=OKX:' + base + 'USDT.P&interval=240';
  const barT = t.bar_time ? String(t.bar_time).slice(0, 16).replace('T', ' ') : '—';
  const closeT = t.close_ts
    ? new Date(parseInt(t.close_ts)).toISOString().slice(0, 16).replace('T', ' ') + ' UTC'
    : '—';
  const lev = t.leverage ? t.leverage + 'x' : '—';
  const rr = (t.entry && t.stop && t.tp)
    ? (Math.abs(t.tp - t.entry) / Math.abs(t.entry - t.stop)).toFixed(2)
    : '—';

  const sideBadge = '<span style="color:' + sc + ';font-weight:600;background:' + sc + '22;'
    + 'padding:3px 10px;border-radius:5px">' + side + '</span>';
  const outBadge = outcome
    ? '<span style="color:' + oc + ';font-weight:600;background:' + oc + '22;'
      + 'padding:3px 10px;border-radius:5px">' + outcome + '</span>'
    : '';
  const outSection = outcome
    ? '<div class="detail-row" style="margin-top:6px">'
      + '<div><span>R Multiple</span> <b style="color:' + oc + '">'
      + (t.r_multiple != null ? (t.r_multiple > 0 ? '+' : '') + p(t.r_multiple, 2) + 'R' : '—')
      + '</b></div>'
      + '<div><span>PnL</span> <b style="color:' + oc + '">'
      + (t.realized_pnl != null ? (t.realized_pnl > 0 ? '+' : '') + p(t.realized_pnl, 2) + ' USDT' : '—')
      + '</b></div>'
      + '<div><span>Cikis</span> <b>' + p(t.close_price, 4) + '</b></div>'
      + '</div>'
    : '';
  const closeRow = t.close_ts
    ? '<div><span>Kapanış</span> <b>' + closeT + '</b></div>'
    : '';

  document.getElementById('modal-body').innerHTML =
    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;flex-wrap:wrap">'
    + '<span style="font-size:22px;font-weight:700">' + sym + '</span>'
    + sideBadge + outBadge
    + '</div>'
    + '<div style="color:#8c93a3;font-size:12px;margin-bottom:12px">'
    + 'Model: <b style="color:#e8eaed">' + (t.model || '—') + '</b>'
    + ' &nbsp;·&nbsp; Setup: <b style="color:#e8eaed">' + barT + '</b>'
    + ' &nbsp;·&nbsp; Leverage: <b style="color:#f59e0b">' + lev + '</b>'
    + ' &nbsp;·&nbsp; RR: <b style="color:#e8eaed">1:' + rr + '</b>'
    + '</div>'
    + '<div class="price-grid">'
    + '<div class="price-box"><div class="plabel">Entry</div>'
    + '<div class="pval">' + p(t.entry, 4) + '</div></div>'
    + '<div class="price-box sl"><div class="plabel" style="color:#ef4444">Stop Loss</div>'
    + '<div class="pval" style="color:#ef4444">' + p(t.stop, 4) + '</div></div>'
    + '<div class="price-box tp"><div class="plabel" style="color:#22c55e">Take Profit</div>'
    + '<div class="pval" style="color:#22c55e">' + p(t.tp, 4) + '</div></div>'
    + '</div>'
    + '<div class="detail-row">'
    + '<div><span>Size</span> <b>' + (t.size || '—') + '</b></div>'
    + '<div><span>Bakiye</span> <b>'
    + (t.balance_at_open ? p(t.balance_at_open, 2) + ' USDT' : '—') + '</b></div>'
    + closeRow
    + '</div>'
    + outSection
    + (t.chart_b64
        ? '<img src="data:image/png;base64,' + t.chart_b64 + '" style="width:100%;border-radius:8px;margin-top:14px" />'
        : '')
    + '<a href="' + tvUrl + '" target="_blank" rel="noopener" class="tv-btn">'
    + '📈 TradingView\'de Gör (OKX 4h)'
    + '</a>';

  document.getElementById('modal').classList.add('open');
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
}
function maybeClose(e) {
  if (e.target === document.getElementById('modal')) closeModal();
}
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeModal();
});

var baseOpts = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
  scales: {
    x: { ticks: { color: '#8c93a3', maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
         grid: { color: '#1d2028' } },
    y: { ticks: { color: '#8c93a3' }, grid: { color: '#1d2028' } }
  },
  interaction: { intersect: false, mode: 'index' }
};

if (EQ_LABELS.length) {
  new Chart(document.getElementById('equity'), {
    type: 'line',
    data: { labels: EQ_LABELS, datasets: [{ label: 'Cumulative R', data: EQ_R,
      borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,.1)',
      fill: true, tension: 0.2, pointRadius: 2 }] },
    options: baseOpts
  });
  new Chart(document.getElementById('dd'), {
    type: 'line',
    data: { labels: EQ_LABELS, datasets: [{ label: 'Drawdown', data: DD,
      borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,.15)',
      fill: true, tension: 0.1, pointRadius: 0 }] },
    options: baseOpts
  });
}
"""

_CSS = """
:root {
  --bg:#0f1115; --card:#181b22; --line:#22262f; --text:#e8eaed; --muted:#8c93a3;
  --green:#22c55e; --red:#ef4444; --blue:#3b82f6; --orange:#f59e0b;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
     font:14px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:18px 24px;border-bottom:1px solid var(--line);
       display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
h1{margin:0;font-size:18px;font-weight:600}
.updated{color:var(--muted);font-size:12px}
main{padding:20px 24px;max-width:1400px;margin:0 auto}
.grid{display:grid;gap:16px}
.kpi-grid{grid-template-columns:repeat(auto-fit,minmax(170px,1fr));margin-bottom:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi .label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.kpi .value{font-size:22px;font-weight:700;margin-top:6px}
.kpi .sub{color:var(--muted);font-size:11px;margin-top:2px}
.green{color:var(--green)} .red{color:var(--red)} .blue{color:var(--blue)} .orange{color:var(--orange)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--muted);font-weight:500;font-size:11px;
   text-transform:uppercase;letter-spacing:.5px;padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:9px 10px;border-bottom:1px solid #1d2028}
tr:last-child td{border-bottom:0}
.tag{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600}
.tag-long{background:rgba(34,197,94,.15);color:var(--green)}
.tag-short{background:rgba(239,68,68,.15);color:var(--red)}
.tag-win{background:rgba(34,197,94,.15);color:var(--green)}
.tag-loss{background:rgba(239,68,68,.15);color:var(--red)}
.charts{grid-template-columns:1fr;gap:16px;margin:20px 0}
.two-col{grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:16px}
.section-title{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin:0 0 10px}
.error{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);
       color:var(--red);padding:10px 14px;border-radius:8px;margin-bottom:16px;font-size:13px}
.muted{color:var(--muted)}
canvas{max-height:280px}
.empty{padding:24px;text-align:center;color:var(--muted)}
.trade-row{cursor:pointer;transition:background .15s}
.trade-row:hover{background:rgba(59,130,246,.07)}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);
               z-index:200;align-items:center;justify-content:center;padding:16px}
.modal-overlay.open{display:flex}
.modal-box{background:#1a1d26;border:1px solid var(--line);border-radius:14px;
           padding:24px;max-width:680px;width:100%;position:relative;
           max-height:90vh;overflow-y:auto}
.modal-close{position:absolute;top:14px;right:18px;background:none;border:none;
             color:var(--muted);font-size:24px;cursor:pointer;line-height:1;padding:0}
.modal-close:hover{color:var(--text)}
.price-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:14px 0}
.price-box{background:var(--bg);border-radius:8px;padding:10px 12px;border:1px solid var(--line)}
.price-box.sl{border-color:rgba(239,68,68,.4)}
.price-box.tp{border-color:rgba(34,197,94,.4)}
.price-box .plabel{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.5px}
.price-box .pval{font-size:15px;font-weight:700;margin-top:4px}
.tv-btn{display:inline-flex;align-items:center;gap:6px;background:#2962ff;color:#fff;
        padding:9px 18px;border-radius:8px;text-decoration:none;font-size:13px;
        margin-top:14px;font-weight:500}
.tv-btn:hover{background:#1a4fd8}
.detail-row{display:flex;flex-wrap:wrap;gap:16px;margin:10px 0;font-size:13px}
.detail-row span{color:var(--muted)}
.detail-row b{color:var(--text)}
@media(max-width:600px){
  main{padding:14px}
  .kpi .value{font-size:18px}
  th,td{padding:6px 6px;font-size:12px}
  .price-grid{grid-template-columns:1fr}
}
"""


def build_html(ctx: Dict) -> str:
    js = (_JS
          .replace("__TRADES__", ctx["trades_json"])
          .replace("__EQ_LABELS__", ctx["eq_labels"])
          .replace("__EQ_R__", ctx["eq_r"])
          .replace("__DD__", ctx["dd"]))

    nr_cls = "green" if ctx["net_r"] > 0 else "red"
    nu_cls = "green" if ctx["net_usdt"] > 0 else "red"

    return (
        '<!DOCTYPE html>\n<html lang="tr">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>ICT Paper Trade Dashboard</title>\n'
        '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>\n'
        f'<style>{_CSS}</style>\n'
        '</head>\n<body>\n\n'
        '<div id="modal" class="modal-overlay" onclick="maybeClose(event)">\n'
        '  <div class="modal-box">\n'
        '    <button class="modal-close" onclick="closeModal()">\xd7</button>\n'
        '    <div id="modal-body"></div>\n'
        '  </div>\n'
        '</div>\n\n'
        '<header>\n'
        '  <h1>\U0001f4ca ICT Paper Trade Dashboard '
        '<span style="font-size:13px;color:#7aa;font-weight:400">· OKX Demo</span></h1>\n'
        f'  <span class="updated">Son guncelleme: <b>{ctx["updated"]}</b> UTC</span>\n'
        '</header>\n<main>\n\n'
        + (f'<div class="error">⚠️ OKX baglanti hatasi: <code>{ctx["error_banner"]}</code></div>\n'
           if ctx["error_banner"] else "")
        +
        '<div class="grid kpi-grid">\n'
        f'  <div class="card kpi"><div class="label">Bakiye</div>'
        f'<div class="value">{ctx["balance"]} <span class="muted" style="font-size:13px">USDT</span></div>'
        f'<div class="sub">{ctx["balance_source"]}</div></div>\n'
        f'  <div class="card kpi"><div class="label">Net R</div>'
        f'<div class="value {nr_cls}">{ctx["net_r"]:+.2f}</div>'
        f'<div class="sub">Toplam {ctx["n_closed"]} kapali trade</div></div>\n'
        f'  <div class="card kpi"><div class="label">Net USDT</div>'
        f'<div class="value {nu_cls}">{ctx["net_usdt"]:+.2f}</div>'
        f'<div class="sub">Gerceklesen PnL</div></div>\n'
        f'  <div class="card kpi"><div class="label">Win-rate</div>'
        f'<div class="value">{ctx["wr"]:.1f}<span class="muted" style="font-size:13px"> %</span></div>'
        f'<div class="sub">{ctx["n_wins"]} W / {ctx["n_losses"]} L</div></div>\n'
        f'  <div class="card kpi"><div class="label">Max Drawdown</div>'
        f'<div class="value red">{ctx["max_dd"]:+.2f}<span class="muted" style="font-size:13px"> R</span></div>'
        f'<div class="sub">En kotu cekilme</div></div>\n'
        f'  <div class="card kpi"><div class="label">Acik Pozisyon</div>'
        f'<div class="value blue">{ctx["n_open_live"]}</div>'
        f'<div class="sub">{ctx["n_open_log"]} log’ta · OKX’te canli</div></div>\n'
        '</div>\n\n'
        '<div class="grid charts">\n'
        '  <div class="card"><div class="section-title">Equity Curve (Cumulative R)</div>'
        '<canvas id="equity"></canvas></div>\n'
        '  <div class="grid two-col">\n'
        '    <div class="card"><div class="section-title">Drawdown (R)</div>'
        '<canvas id="dd"></canvas></div>\n'
        '    <div class="card"><div class="section-title">Per-Model Breakdown</div>'
        f'{ctx["model_table"]}</div>\n'
        '  </div>\n'
        '</div>\n\n'
        '<div class="card" style="margin-top:20px">\n'
        '  <div class="section-title">\U0001f7e2 Acik Pozisyonlar (OKX canli)</div>\n'
        f'  {ctx["open_table"]}\n'
        '</div>\n\n'
        '<div class="card" style="margin-top:16px">\n'
        '  <div class="section-title">\U0001f4dc Kapanan Trade\'ler '
        '<span class="muted" style="font-weight:400;text-transform:none">'
        '— detay icin satira tikla</span></div>\n'
        f'  {ctx["closed_table"]}\n'
        '</div>\n\n'
        '</main>\n\n'
        f'<script>{js}</script>\n'
        '</body>\n</html>'
    )


def main():
    log: List[Dict] = json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else []
    agg = aggregate(log)
    okx = fetch_okx_state()
    simulated_mode = (os.environ.get("DASHBOARD_MODE", "").lower() == "simulated")

    n_wins = sum(1 for e in agg["closed"] if e.get("outcome") == "WIN")
    n_losses = agg["n_closed"] - n_wins

    error_banner = ""
    if okx["error"] and okx["error"] not in ("credentials_missing", "simulated_mode"):
        error_banner = okx["error"]

    if simulated_mode:
        bal = 5000.0 + agg["net_usdt"]
        bal_str = fmt(bal, 2)
        bal_source = "simule · baslangic 5000"
    else:
        bal = okx["balance"]
        bal_str = fmt(bal, 2) if bal is not None else "—"
        if bal is not None:
            bal_source = "OKX Demo · canli"
        elif okx["error"] == "credentials_missing":
            bal_source = "credentials yok"
        else:
            bal_source = "baglanti hatasi"

    labels = []
    for e in agg["closed"]:
        ct = e.get("close_ts")
        try:
            labels.append(
                datetime.fromtimestamp(int(ct) / 1000, tz=timezone.utc).strftime("%m-%d %H:%M")
            )
        except Exception:
            labels.append("?")

    dd = []
    peak = 0.0
    for x in agg["cum_r"]:
        peak = max(peak, x)
        dd.append(round(x - peak, 4))

    # Son 30 kapanan trade için chart üret (daha eskiler için geç)
    closed_with_charts = []
    chart_limit = 30
    for i, e in enumerate(agg["closed"]):
        trade_copy = dict(e)
        if i >= len(agg["closed"]) - chart_limit:
            print(f"  Chart: {e.get('symbol','?')} {e.get('bar_time','')[:16]}…", end=" ", flush=True)
            trade_copy["chart_b64"] = generate_trade_chart(e)
            print("ok" if trade_copy["chart_b64"] else "skip")
        else:
            trade_copy["chart_b64"] = ""
        closed_with_charts.append(trade_copy)

    ctx = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "error_banner": error_banner,
        "balance": bal_str,
        "balance_source": bal_source,
        "net_r": agg["net_r"],
        "net_usdt": agg["net_usdt"],
        "wr": agg["wr"],
        "n_wins": n_wins,
        "n_losses": n_losses,
        "max_dd": agg["max_dd"],
        "n_closed": agg["n_closed"],
        "n_open_live": len(okx["positions"]),
        "n_open_log": agg["n_open"],
        "eq_labels": json.dumps(labels),
        "eq_r": json.dumps([round(x, 4) for x in agg["cum_r"]]),
        "dd": json.dumps(dd),
        "trades_json": json.dumps(closed_with_charts, default=str),
        "model_table": render_model_table(agg["by_model"]),
        "open_table": render_open_positions(okx["positions"], agg["placed"]),
        "closed_table": render_closed_trades(agg["closed"]),
    }

    html = build_html(ctx)
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard yazildi: {OUT_PATH} ({len(html)} bytes)")
    print(f"  closed={agg['n_closed']} placed={agg['n_open']} "
          f"balance={bal_str} netR={agg['net_r']:+.2f}")


if __name__ == "__main__":
    main()
