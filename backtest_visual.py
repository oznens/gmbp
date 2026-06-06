"""Backtest + görsel rapor: son 3 ay, 4H, judas_swing + sbs, 12 parite.

Calistirir:
    python backtest_visual.py
Cikti:
    docs/backtest_report.html  — tarayicida ac
"""
from __future__ import annotations

import base64
import io
import json
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

sys.path.insert(0, ".")
from utils.okx_fetcher import OKXFetcher
from backtest_history import MODELS, Trade, run_backtest, simulate_trade, normalize_signal

SYMBOLS   = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
    "BNBUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT",
    "OPUSDT", "ARBUSDT", "LTCUSDT", "ADAUSDT",
]
TF        = "4h"
LIMIT     = 550          # ~3 ay 4H (4h * 550 = 91 gun)
WINDOW    = 100          # model için geriye bakış
FEE_PCT   = 0.05         # OKX taker %0.05
SLIP_PCT  = 0.02         # gerçekçi slippage
RUN_MODELS = {k: MODELS[k] for k in ("judas_swing", "sbs") if k in MODELS}
COOLDOWN  = 10           # ayni modelde min 10 bar aralik
CHART_TRADES = 8         # grafik başına max gösterilecek setup sayısı

WIN_C  = "#22c55e"
LOSS_C = "#ef4444"
SL_C   = "#f87171"
TP_C   = "#4ade80"
ENTRY_C = "#60a5fa"


# ── yardımcı ──────────────────────────────────────────────────────────────────

def fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def plot_price_with_trades(df: pd.DataFrame, trades: list[Trade],
                           symbol: str, n: int = CHART_TRADES) -> str:
    """Son N setup'ı 4H grafik üzerinde göster."""
    closed = [t for t in trades if t.outcome in ("WIN", "LOSS")][-n:]
    if not closed:
        return ""

    # Grafik için yeterli veri: en erken trade başlamadan 20 bar önce
    first_idx = max(0, closed[0].open_idx - 20)
    last_idx  = min(len(df) - 1, closed[-1].close_idx + 5 if closed[-1].close_idx else len(df) - 1)
    view = df.iloc[first_idx:last_idx + 1].reset_index()
    view.columns = ["time"] + list(df.columns)

    idx_offset = first_idx  # view indeksine çevirmek için

    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor("#0f1115")
    ax.set_facecolor("#181b22")

    # Mum grafik
    for i, row in view.iterrows():
        color = "#22c55e" if row["close"] >= row["open"] else "#ef4444"
        ax.plot([i, i], [row["low"], row["high"]], color=color, lw=0.7, alpha=0.7)
        ax.add_patch(plt.Rectangle(
            (i - 0.35, min(row["open"], row["close"])),
            0.7, abs(row["close"] - row["open"]) or (row["high"] - row["low"]) * 0.01,
            color=color, alpha=0.85
        ))

    # Trade kurulumlarını çiz
    for t in closed:
        oi = t.open_idx - idx_offset
        ci = (t.close_idx or t.open_idx + 1) - idx_offset
        if oi < 0 or oi >= len(view):
            continue
        ci = min(ci, len(view) - 1)

        c = WIN_C if t.outcome == "WIN" else LOSS_C

        # Entry çizgisi (kesik)
        ax.axhline(t.entry, color=ENTRY_C, lw=0.8, ls="--", alpha=0.6,
                   xmin=oi / len(view), xmax=ci / len(view))
        # SL çizgisi
        ax.axhline(t.stop, color=SL_C, lw=0.8, ls=":", alpha=0.7,
                   xmin=oi / len(view), xmax=ci / len(view))
        # TP çizgisi
        ax.axhline(t.tp, color=TP_C, lw=0.8, ls=":", alpha=0.7,
                   xmin=oi / len(view), xmax=ci / len(view))

        # Shaded zone: entry→TP veya entry→SL
        top = t.tp if t.direction == "LONG" else t.entry
        bot = t.entry if t.direction == "LONG" else t.tp
        ax.axhspan(bot, top, alpha=0.05, color=c, xmin=oi / len(view), xmax=ci / len(view))

        # Entry marker
        marker = "^" if t.direction == "LONG" else "v"
        ax.scatter(oi, t.entry, marker=marker, color=ENTRY_C, s=60, zorder=5)
        # Close marker
        ax.scatter(ci, t.exit_price or t.entry, marker="x", color=c, s=60, zorder=5)

    # Eksen stilleri
    n_ticks = min(8, len(view))
    tick_positions = [int(i * (len(view) - 1) / (n_ticks - 1)) for i in range(n_ticks)]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(
        [view.loc[p, "time"].strftime("%m-%d %Hh") for p in tick_positions],
        rotation=30, fontsize=7, color="#8c93a3"
    )
    ax.tick_params(axis="y", colors="#8c93a3", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#22262f")
    ax.set_title(f"{symbol} — Son {len(closed)} setup (4H)", color="#e8eaed", fontsize=10, pad=8)

    # Legend
    patches = [
        mpatches.Patch(color=ENTRY_C, label="Entry"),
        mpatches.Patch(color=TP_C,    label="TP"),
        mpatches.Patch(color=SL_C,    label="SL"),
        mpatches.Patch(color=WIN_C,   label="WIN"),
        mpatches.Patch(color=LOSS_C,  label="LOSS"),
    ]
    ax.legend(handles=patches, loc="upper left", fontsize=7, framealpha=0.3,
              facecolor="#1a1d26", labelcolor="#e8eaed")

    b64 = fig_to_b64(fig)
    plt.close(fig)
    return b64


def plot_equity(all_trades: list[Trade]) -> str:
    closed = [t for t in all_trades if t.outcome in ("WIN", "LOSS")]
    closed.sort(key=lambda t: t.open_time)
    if not closed:
        return ""

    cum = 0.0
    xs, ys = [], []
    for t in closed:
        cum += t.r_multiple or 0
        xs.append(t.open_time)
        ys.append(round(cum, 3))

    fig, ax = plt.subplots(figsize=(12, 3.5))
    fig.patch.set_facecolor("#0f1115")
    ax.set_facecolor("#181b22")
    ax.fill_between(xs, ys, alpha=0.15, color="#3b82f6")
    ax.plot(xs, ys, color="#3b82f6", lw=1.5)
    ax.axhline(0, color="#22262f", lw=1)
    ax.tick_params(colors="#8c93a3", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#22262f")
    ax.set_title("Birleşik Equity Eğrisi (R) — Tüm Pariteler", color="#e8eaed", fontsize=10, pad=8)
    b64 = fig_to_b64(fig)
    plt.close(fig)
    return b64


def plot_per_symbol_bar(results: dict) -> str:
    """Her parite için WR + Net R çubuk grafik."""
    symbols = list(results.keys())
    wrs = [results[s]["wr"] for s in symbols]
    nets = [results[s]["net_r"] for s in symbols]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.5))
    fig.patch.set_facecolor("#0f1115")
    for ax in (ax1, ax2):
        ax.set_facecolor("#181b22")
        for spine in ax.spines.values():
            spine.set_color("#22262f")
        ax.tick_params(colors="#8c93a3", labelsize=8)

    colors_wr = [WIN_C if w >= 50 else LOSS_C for w in wrs]
    colors_net = [WIN_C if n >= 0 else LOSS_C for n in nets]

    ax1.bar(symbols, wrs, color=colors_wr, alpha=0.8)
    ax1.axhline(50, color="#8c93a3", lw=0.8, ls="--")
    ax1.set_title("Win Rate (%)", color="#e8eaed", fontsize=9)
    ax1.set_ylim(0, 100)

    ax2.bar(symbols, nets, color=colors_net, alpha=0.8)
    ax2.axhline(0, color="#8c93a3", lw=0.8)
    ax2.set_title("Net R", color="#e8eaed", fontsize=9)

    for ax, vals in ((ax1, wrs), (ax2, nets)):
        for i, v in enumerate(vals):
            ax.text(i, v + (0.5 if v >= 0 else -2), f"{v:.1f}",
                    ha="center", va="bottom", fontsize=7.5, color="#e8eaed")

    fig.tight_layout()
    b64 = fig_to_b64(fig)
    plt.close(fig)
    return b64


# ── HTML ──────────────────────────────────────────────────────────────────────

CSS = """
:root{--bg:#0f1115;--card:#181b22;--line:#22262f;--text:#e8eaed;--muted:#8c93a3;
      --green:#22c55e;--red:#ef4444;--blue:#3b82f6;--orange:#f59e0b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
     font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:18px 24px;border-bottom:1px solid var(--line);
       display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
h1{margin:0;font-size:18px;font-weight:600}
h2{font-size:14px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin:0 0 12px}
main{padding:20px 24px;max-width:1400px;margin:0 auto}
.grid{display:grid;gap:16px}
.kpi-row{grid-template-columns:repeat(auto-fit,minmax(160px,1fr));margin-bottom:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.kpi .label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.kpi .value{font-size:22px;font-weight:700;margin-top:6px}
.kpi .sub{color:var(--muted);font-size:11px;margin-top:2px}
.green{color:var(--green)} .red{color:var(--red)} .blue{color:var(--blue)} .orange{color:var(--orange)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--muted);font-weight:500;font-size:11px;
   text-transform:uppercase;letter-spacing:.5px;padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:9px 10px;border-bottom:1px solid #1d2028}
tr:last-child td{border-bottom:0}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}
.tag-win{background:rgba(34,197,94,.15);color:var(--green)}
.tag-loss{background:rgba(239,68,68,.15);color:var(--red)}
.tag-long{background:rgba(34,197,94,.15);color:var(--green)}
.tag-short{background:rgba(239,68,68,.15);color:var(--red)}
.empty{padding:24px;text-align:center;color:var(--muted)}
img{max-width:100%;border-radius:8px;margin-top:4px}
.sym-section{margin-bottom:28px}
.warn{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);
      color:var(--orange);padding:10px 14px;border-radius:8px;margin-bottom:16px;font-size:13px}
.trade-row{cursor:pointer;transition:background .15s}
.trade-row:hover{background:rgba(59,130,246,.07)}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.78);
               z-index:200;align-items:center;justify-content:center;padding:16px}
.modal-overlay.open{display:flex}
.modal-box{background:#1a1d26;border:1px solid var(--line);border-radius:14px;
           padding:24px;max-width:520px;width:100%;position:relative;max-height:90vh;overflow-y:auto}
.modal-close{position:absolute;top:14px;right:18px;background:none;border:none;
             color:var(--muted);font-size:24px;cursor:pointer;line-height:1;padding:0}
.modal-close:hover{color:var(--text)}
.price-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:14px 0}
.price-box{background:var(--bg);border-radius:8px;padding:10px 12px;border:1px solid var(--line)}
.price-box.sl{border-color:rgba(239,68,68,.4)}
.price-box.tp{border-color:rgba(34,197,94,.4)}
.price-box .plabel{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.5px}
.price-box .pval{font-size:15px;font-weight:700;margin-top:4px}
.detail-row{display:flex;flex-wrap:wrap;gap:14px;margin:10px 0;font-size:13px}
.detail-row span{color:var(--muted)} .detail-row b{color:var(--text)}
.tv-btn{display:inline-flex;align-items:center;gap:6px;background:#2962ff;color:#fff;
        padding:9px 18px;border-radius:8px;text-decoration:none;font-size:13px;
        margin-top:14px;font-weight:500}
.tv-btn:hover{background:#1a4fd8}
@media(max-width:600px){main{padding:14px}.kpi .value{font-size:18px}.price-grid{grid-template-columns:1fr}}
"""

# JavaScript modal — placeholder'lar build_html içinde .replace ile doldurulur
_BT_JS = r"""
const BT_TRADES = __BT_TRADES__;
function p(v,d){return v==null?'—':parseFloat(v).toFixed(d||4);}
function showTrade(idx){
  const t=BT_TRADES[idx]; if(!t) return;
  const sc=t.direction==='LONG'?'#22c55e':'#ef4444';
  const oc=t.outcome==='WIN'?'#22c55e':'#ef4444';
  const sym=(t.symbol||'?');
  const base=sym.replace('USDT','');
  const tvUrl='https://www.tradingview.com/chart/?symbol=OKX:'+base+'USDT.P&interval=240';
  const rr=t.entry&&t.stop&&t.tp?(Math.abs(t.tp-t.entry)/Math.abs(t.entry-t.stop)).toFixed(2):'—';
  const openT=t.open_time?String(t.open_time).slice(0,16).replace('T',' '):'—';
  const sideBadge='<span style="color:'+sc+';font-weight:600;background:'+sc+'22;padding:3px 10px;border-radius:5px">'+t.direction+'</span>';
  const outBadge=t.outcome?'<span style="color:'+oc+';font-weight:600;background:'+oc+'22;padding:3px 10px;border-radius:5px">'+t.outcome+'</span>':'';
  document.getElementById('bt-modal-body').innerHTML=
    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;flex-wrap:wrap">'
    +'<span style="font-size:22px;font-weight:700">'+sym+'</span>'+sideBadge+outBadge+'</div>'
    +'<div style="color:#8c93a3;font-size:12px;margin-bottom:12px">'
    +'Model: <b style="color:#e8eaed">'+t.model+'</b>'
    +' &nbsp;·&nbsp; Setup: <b style="color:#e8eaed">'+openT+'</b>'
    +' &nbsp;·&nbsp; RR: <b style="color:#e8eaed">1:'+rr+'</b></div>'
    +'<div class="price-grid">'
    +'<div class="price-box"><div class="plabel">Entry</div><div class="pval">'+p(t.entry)+'</div></div>'
    +'<div class="price-box sl"><div class="plabel" style="color:#ef4444">Stop Loss</div><div class="pval" style="color:#ef4444">'+p(t.stop)+'</div></div>'
    +'<div class="price-box tp"><div class="plabel" style="color:#22c55e">Take Profit</div><div class="pval" style="color:#22c55e">'+p(t.tp)+'</div></div>'
    +'</div>'
    +'<div class="detail-row">'
    +'<div><span>Sonuç</span> <b style="color:'+oc+'">'+( t.outcome||'—')+'</b></div>'
    +'<div><span>R</span> <b style="color:'+oc+'">'+(t.r_multiple!=null?(t.r_multiple>0?'+':'')+parseFloat(t.r_multiple).toFixed(2)+'R':'—')+'</b></div>'
    +'<div><span>Exit</span> <b>'+p(t.exit_price)+'</b></div>'
    +'</div>'
    +'<a href="'+tvUrl+'" target="_blank" rel="noopener" class="tv-btn">📈 TradingView\'de Gör (OKX 4h)</a>';
  document.getElementById('bt-modal').classList.add('open');
}
function closeBtModal(){document.getElementById('bt-modal').classList.remove('open');}
function maybeBtClose(e){if(e.target===document.getElementById('bt-modal'))closeBtModal();}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeBtModal();});
"""


def build_html(results: dict, all_trades: list, eq_b64: str, bar_b64: str,
               period_str: str, ran_at: str) -> str:
    total_trades  = sum(r["n"] for r in results.values())
    total_wins    = sum(r["wins"] for r in results.values())
    total_losses  = sum(r["losses"] for r in results.values())
    total_net_r   = sum(r["net_r"] for r in results.values())
    decided       = total_wins + total_losses
    wr_all        = (total_wins / decided * 100) if decided else 0.0

    nr_cls  = "green" if total_net_r >= 0 else "red"
    wr_cls  = "green" if wr_all >= 50 else "red"

    # KPI kartları
    kpis = (
        '<div class="grid kpi-row">'
        f'<div class="card kpi"><div class="label">Toplam Trade</div>'
        f'<div class="value blue">{total_trades}</div>'
        f'<div class="sub">{period_str}</div></div>'
        f'<div class="card kpi"><div class="label">Win Rate</div>'
        f'<div class="value {wr_cls}">{wr_all:.1f}<span style="font-size:14px"> %</span></div>'
        f'<div class="sub">{total_wins} W / {total_losses} L</div></div>'
        f'<div class="card kpi"><div class="label">Net R</div>'
        f'<div class="value {nr_cls}">{total_net_r:+.2f}</div>'
        f'<div class="sub">Fee+slippage dahil ({FEE_PCT+SLIP_PCT:.2f}% round-trip)</div></div>'
        f'<div class="card kpi"><div class="label">Parite</div>'
        f'<div class="value">{len(SYMBOLS)}</div>'
        f'<div class="sub">{" · ".join(SYMBOLS)}</div></div>'
        f'<div class="card kpi"><div class="label">Model</div>'
        f'<div class="value">{len(RUN_MODELS)}</div>'
        f'<div class="sub">{" · ".join(RUN_MODELS)}</div></div>'
        '</div>'
    )

    # Per-symbol özet tablo
    rows = []
    for sym, r in results.items():
        d = r["wins"] + r["losses"]
        wr = (r["wins"] / d * 100) if d else 0.0
        wrc = "green" if wr >= 50 else "red"
        nrc = "green" if r["net_r"] >= 0 else "red"
        rows.append(
            f'<tr><td><b>{sym}</b></td><td>{r["n"]}</td>'
            f'<td class="{wrc}">{wr:.1f}%</td>'
            f'<td class="{nrc}">{r["net_r"]:+.2f}</td>'
            f'<td class="{nrc}">{r["avg_r"]:+.2f}</td>'
            f'<td>{r["max_win"]:+.2f}</td><td class="red">{r["max_loss"]:+.2f}</td>'
            f'<td>{r["open"]}</td></tr>'
        )
    summary_table = (
        '<table><thead><tr><th>Sembol</th><th>n</th><th>WR</th><th>Net R</th>'
        '<th>Avg R</th><th>Best</th><th>Worst</th><th>Açık</th></tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody></table>'
    )

    # Tüm trade listesi (son 50) — tıklanabilir
    all_sorted = sorted(
        [t for t in all_trades if t.outcome in ("WIN", "LOSS")],
        key=lambda t: t.open_time, reverse=True
    )[:50]
    trade_rows = []
    bt_trade_data = []  # JS modal için
    for idx, t in enumerate(all_sorted):
        oc = "tag-win" if t.outcome == "WIN" else "tag-loss"
        dc = "tag-long" if t.direction == "LONG" else "tag-short"
        rc = "green" if (t.r_multiple or 0) >= 0 else "red"
        rr = abs(t.tp - t.entry) / abs(t.entry - t.stop) if abs(t.entry - t.stop) > 0 else 0
        trade_rows.append(
            f'<tr class="trade-row" onclick="showTrade({idx})" title="Detay için tıkla">'
            f'<td>{t.open_time.strftime("%m-%d %H:%M") if t.open_time else "—"}</td>'
            f'<td><b>{getattr(t, "symbol", "?")}</b></td>'
            f'<td><b>{t.model.replace("_", " ").upper()}</b></td>'
            f'<td><span class="tag {dc}">{t.direction}</span></td>'
            f'<td>{t.entry:.4f}</td>'
            f'<td style="color:#f87171">{t.stop:.4f}</td>'
            f'<td style="color:#4ade80">{t.tp:.4f}</td>'
            f'<td style="color:#8c93a3">{rr:.1f}x</td>'
            f'<td><span class="tag {oc}">{t.outcome}</span></td>'
            f'<td class="{rc}">{(t.r_multiple or 0):+.2f}R</td>'
            f'</tr>'
        )
        bt_trade_data.append({
            "symbol": getattr(t, "symbol", "?"),
            "model": t.model,
            "direction": t.direction,
            "entry": t.entry,
            "stop": t.stop,
            "tp": t.tp,
            "outcome": t.outcome,
            "r_multiple": t.r_multiple,
            "exit_price": t.exit_price,
            "open_time": t.open_time.isoformat() if t.open_time else None,
        })
    trade_table = (
        '<table><thead><tr>'
        '<th>Zaman</th><th>Sembol</th><th>Model</th><th>Yön</th>'
        '<th>Entry</th><th style="color:#f87171">SL</th><th style="color:#4ade80">TP</th>'
        '<th>RR</th><th>Sonuç</th><th>R</th>'
        '</tr></thead><tbody>' + ''.join(trade_rows) + '</tbody></table>'
        if trade_rows else '<div class="empty">Trade yok</div>'
    )

    # Per-symbol grafik bölümleri
    sym_sections = ""
    for sym, r in results.items():
        img_tag = f'<img src="data:image/png;base64,{r["chart_b64"]}" />' if r.get("chart_b64") else ""
        no_chart = '<div class="empty">Grafik için yeterli trade yok</div>'
        sym_sections += (
            f'<div class="sym-section">'
            f'<div class="card">'
            f'<h2>{sym} — 4H setup görünümü</h2>'
            f'{img_tag or no_chart}'
            f'</div></div>'
        )

    eq_img  = f'<img src="data:image/png;base64,{eq_b64}" />' if eq_b64 else ""
    bar_img = f'<img src="data:image/png;base64,{bar_b64}" />' if bar_b64 else ""

    import json as _json
    js = _BT_JS.replace("__BT_TRADES__", _json.dumps(bt_trade_data))

    return (
        '<!DOCTYPE html>\n<html lang="tr"><head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>ICT Backtest Raporu — Son 3 Ay</title>\n'
        f'<style>{CSS}</style></head><body>\n\n'
        '<div id="bt-modal" class="modal-overlay" onclick="maybeBtClose(event)">\n'
        '  <div class="modal-box">\n'
        '    <button class="modal-close" onclick="closeBtModal()">×</button>\n'
        '    <div id="bt-modal-body"></div>\n'
        '  </div>\n'
        '</div>\n\n'
        '<header>'
        '  <h1>📊 ICT Backtest Raporu — Son 3 Ay (4H)</h1>'
        f'  <span style="color:#8c93a3;font-size:12px">Oluşturuldu: {ran_at} UTC</span>'
        '</header>\n<main>\n\n'
        '<div class="warn">⚠️ Bu backtest in-sample sonuçlarıdır. '
        'Geçmiş performans gelecekteki sonuçların garantisi değildir. '
        f'Fee: {FEE_PCT}% + Slippage: {SLIP_PCT}% her yön dahil.</div>\n\n'
        + kpis +
        '<div class="grid" style="grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">\n'
        f'  <div class="card"><h2>Equity Eğrisi</h2>{eq_img}</div>\n'
        f'  <div class="card"><h2>Parite Karşılaştırma</h2>{bar_img}</div>\n'
        '</div>\n\n'
        f'<div class="card" style="margin-bottom:20px"><h2>Parite Özet</h2>{summary_table}</div>\n\n'
        + sym_sections +
        f'<div class="card" style="margin-top:8px"><h2>📋 Trade Listesi (son 50) '
        f'<span style="color:#8c93a3;font-weight:400;font-size:12px;text-transform:none">— detay için satıra tıkla</span></h2>'
        f'{trade_table}</div>\n\n'
        f'</main><script>{js}</script></body></html>'
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    fetcher = OKXFetcher()
    results = {}
    all_trades: list[Trade] = []

    print(f"Backtest: {', '.join(SYMBOLS)} | TF={TF} | "
          f"Modeller={list(RUN_MODELS)} | {LIMIT} mum (~3 ay)")
    print(f"Fee={FEE_PCT}%  Slippage={SLIP_PCT}%  Cooldown={COOLDOWN} bar\n")

    period_str = ""
    for sym in SYMBOLS:
        print(f"  {sym}: veri çekiliyor…", end="", flush=True)
        df = fetcher.fetch_ohlcv(sym, TF, limit=LIMIT)
        if df is None or len(df) < WINDOW + 20:
            print(" HATA — atlandi")
            continue
        if not period_str:
            period_str = f"{df.index[0].strftime('%Y-%m-%d')} → {df.index[-1].strftime('%Y-%m-%d')}"
        print(f" {len(df)} mum ({df.index[0].strftime('%Y-%m-%d')} → {df.index[-1].strftime('%Y-%m-%d')})")

        trades, stats = run_backtest(
            df, RUN_MODELS,
            window=WINDOW, cooldown=COOLDOWN, max_concurrent=1,
            fee_pct=FEE_PCT, slippage_pct=SLIP_PCT,
        )

        # Parite etiketleri ekle
        for t in trades:
            t.symbol = sym  # type: ignore[attr-defined]
        all_trades.extend(trades)

        decided = stats.wins + stats.losses
        wr = (stats.wins / decided * 100) if decided else 0.0
        closed_r = [t.r_multiple for t in trades if t.r_multiple is not None and t.outcome in ("WIN","LOSS")]
        net_r  = sum(closed_r)
        avg_r  = (net_r / len(closed_r)) if closed_r else 0.0
        max_win  = max(closed_r, default=0.0)
        max_loss = min(closed_r, default=0.0)

        print(f"    → {stats.total} trade | WR {wr:.1f}% | Net {net_r:+.2f}R | "
              f"Avg {avg_r:+.2f}R | Open {stats.open} | Fill yok {stats.cancelled}")

        chart_b64 = plot_price_with_trades(df, trades, sym)

        results[sym] = {
            "n": stats.total, "wins": stats.wins, "losses": stats.losses,
            "open": stats.open, "net_r": round(net_r, 3), "avg_r": round(avg_r, 3),
            "max_win": round(max_win, 3), "max_loss": round(max_loss, 3),
            "wr": wr, "chart_b64": chart_b64,
        }

    print("\nGrafikler üretiliyor…")
    eq_b64  = plot_equity(all_trades)
    bar_b64 = plot_per_symbol_bar(results)

    ran_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    html = build_html(results, all_trades, eq_b64, bar_b64, period_str, ran_at)

    out = "docs/backtest_report.html"
    import pathlib; pathlib.Path("docs").mkdir(exist_ok=True)
    pathlib.Path(out).write_text(html, encoding="utf-8")
    print(f"\nRapor: {out}  ({len(html)//1024} KB)")
    print("Tarayıcıda aç: python -m http.server 8080 → localhost:8080/docs/backtest_report.html")


if __name__ == "__main__":
    main()
