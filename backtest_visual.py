"""Backtest + gorsel rapor: son 3 ay, 4H, judas_swing + sbs, 12 parite.

Calistirir:
    python backtest_visual.py
Cikti:
    docs/backtest_report.html
"""
from __future__ import annotations

import base64
import io
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

sys.path.insert(0, ".")
from utils.okx_fetcher import OKXFetcher
from backtest_history import MODELS, Trade, run_backtest, normalize_signal

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
    "BNBUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT",
    "OPUSDT", "ARBUSDT", "LTCUSDT", "ADAUSDT",
]
TF         = "4h"
LIMIT      = 550
WINDOW     = 100
FEE_PCT    = 0.05
SLIP_PCT   = 0.02
RUN_MODELS = {k: MODELS[k] for k in ("judas_swing", "sbs") if k in MODELS}
COOLDOWN   = 10
CHART_N    = 8

WIN_C   = "#22c55e"
LOSS_C  = "#ef4444"
SL_C    = "#f87171"
TP_C    = "#4ade80"
ENTRY_C = "#60a5fa"


def fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def plot_price(df, trades, symbol, n=CHART_N) -> str:
    closed = [t for t in trades if t.outcome in ("WIN", "LOSS")][-n:]
    if not closed:
        return ""
    first = max(0, closed[0].open_idx - 20)
    last  = min(len(df) - 1, (closed[-1].close_idx or closed[-1].open_idx + 1) + 5)
    view  = df.iloc[first:last + 1].reset_index()
    view.columns = ["time"] + list(df.columns)
    off = first

    fig, ax = plt.subplots(figsize=(13, 4.5))
    fig.patch.set_facecolor("#0f1115")
    ax.set_facecolor("#181b22")

    for i, row in view.iterrows():
        c = "#22c55e" if row["close"] >= row["open"] else "#ef4444"
        ax.plot([i, i], [row["low"], row["high"]], color=c, lw=0.7, alpha=0.7)
        ax.add_patch(plt.Rectangle(
            (i - 0.35, min(row["open"], row["close"])),
            0.7, abs(row["close"] - row["open"]) or (row["high"] - row["low"]) * 0.01,
            color=c, alpha=0.85
        ))

    lv = len(view)
    for t in closed:
        oi = t.open_idx - off
        ci = min((t.close_idx or t.open_idx + 1) - off, lv - 1)
        if oi < 0 or oi >= lv:
            continue
        c = WIN_C if t.outcome == "WIN" else LOSS_C
        ax.axhline(t.entry, color=ENTRY_C, lw=0.8, ls="--", alpha=0.6,
                   xmin=oi/lv, xmax=ci/lv)
        ax.axhline(t.stop,  color=SL_C,    lw=0.8, ls=":",  alpha=0.7,
                   xmin=oi/lv, xmax=ci/lv)
        ax.axhline(t.tp,    color=TP_C,    lw=0.8, ls=":",  alpha=0.7,
                   xmin=oi/lv, xmax=ci/lv)
        top = t.tp    if t.direction == "LONG" else t.entry
        bot = t.entry if t.direction == "LONG" else t.tp
        ax.axhspan(bot, top, alpha=0.05, color=c, xmin=oi/lv, xmax=ci/lv)
        ax.scatter(oi, t.entry, marker=("^" if t.direction=="LONG" else "v"),
                   color=ENTRY_C, s=55, zorder=5)
        ax.scatter(ci, t.exit_price or t.entry, marker="x", color=c, s=55, zorder=5)

    ticks = [int(i * (lv - 1) / 7) for i in range(8)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([view.loc[p, "time"].strftime("%m-%d %Hh") for p in ticks],
                       rotation=28, fontsize=7, color="#8c93a3")
    ax.tick_params(axis="y", colors="#8c93a3", labelsize=7)
    for sp in ax.spines.values():
        sp.set_color("#22262f")
    ax.set_title(f"{symbol} -- Son {len(closed)} setup (4H)",
                 color="#e8eaed", fontsize=9, pad=6)
    ax.legend(handles=[
        mpatches.Patch(color=ENTRY_C, label="Entry"),
        mpatches.Patch(color=TP_C,    label="TP"),
        mpatches.Patch(color=SL_C,    label="SL"),
        mpatches.Patch(color=WIN_C,   label="WIN"),
        mpatches.Patch(color=LOSS_C,  label="LOSS"),
    ], loc="upper left", fontsize=7, framealpha=0.3,
       facecolor="#1a1d26", labelcolor="#e8eaed")
    b64 = fig_to_b64(fig)
    plt.close(fig)
    return b64


def plot_equity(all_trades) -> str:
    closed = sorted([t for t in all_trades if t.outcome in ("WIN","LOSS")],
                    key=lambda t: t.open_time)
    if not closed:
        return ""
    cum, xs, ys = 0.0, [], []
    for t in closed:
        cum += t.r_multiple or 0
        xs.append(t.open_time)
        ys.append(round(cum, 3))
    fig, ax = plt.subplots(figsize=(12, 3.2))
    fig.patch.set_facecolor("#0f1115")
    ax.set_facecolor("#181b22")
    ax.fill_between(xs, ys, alpha=0.15, color="#3b82f6")
    ax.plot(xs, ys, color="#3b82f6", lw=1.5)
    ax.axhline(0, color="#22262f", lw=1)
    ax.tick_params(colors="#8c93a3", labelsize=7)
    for sp in ax.spines.values():
        sp.set_color("#22262f")
    ax.set_title("Birlesik Equity Egrisi (R) -- 12 Parite",
                 color="#e8eaed", fontsize=9, pad=6)
    b64 = fig_to_b64(fig)
    plt.close(fig)
    return b64


def plot_bars(results) -> str:
    syms = list(results.keys())
    wrs  = [results[s]["wr"]    for s in syms]
    nets = [results[s]["net_r"] for s in syms]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 3.2))
    fig.patch.set_facecolor("#0f1115")
    for ax in (ax1, ax2):
        ax.set_facecolor("#181b22")
        for sp in ax.spines.values():
            sp.set_color("#22262f")
        ax.tick_params(colors="#8c93a3", labelsize=7)
    ax1.bar(syms, wrs,  color=[WIN_C if w>=50 else LOSS_C for w in wrs],  alpha=0.8)
    ax1.axhline(50, color="#8c93a3", lw=0.8, ls="--")
    ax1.set_title("Win Rate (%)", color="#e8eaed", fontsize=9)
    ax1.set_ylim(0, 100)
    ax1.set_xticklabels(syms, rotation=35, fontsize=7)
    ax2.bar(syms, nets, color=[WIN_C if n>=0  else LOSS_C for n in nets], alpha=0.8)
    ax2.axhline(0, color="#8c93a3", lw=0.8)
    ax2.set_title("Net R", color="#e8eaed", fontsize=9)
    ax2.set_xticklabels(syms, rotation=35, fontsize=7)
    for ax, vals in ((ax1, wrs), (ax2, nets)):
        for i, v in enumerate(vals):
            ax.text(i, v + (1 if v >= 0 else -3), f"{v:.0f}",
                    ha="center", fontsize=6.5, color="#e8eaed")
    fig.tight_layout()
    b64 = fig_to_b64(fig)
    plt.close(fig)
    return b64


CSS = """
:root{--bg:#0f1115;--card:#181b22;--line:#22262f;--text:#e8eaed;--muted:#8c93a3;
      --green:#22c55e;--red:#ef4444;--blue:#3b82f6;--orange:#f59e0b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
     font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{padding:16px 22px;border-bottom:1px solid var(--line);
       display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px}
h1{margin:0;font-size:17px;font-weight:600}
h2{font-size:12px;color:var(--muted);text-transform:uppercase;
   letter-spacing:.5px;margin:0 0 10px}
main{padding:18px 22px;max-width:1400px;margin:0 auto}
.grid{display:grid;gap:14px}
.krow{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi .lbl{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.5px}
.kpi .val{font-size:21px;font-weight:700;margin-top:5px}
.kpi .sub{color:var(--muted);font-size:10px;margin-top:2px}
.green{color:var(--green)}.red{color:var(--red)}.blue{color:var(--blue)}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;color:var(--muted);font-weight:500;font-size:10px;
   text-transform:uppercase;letter-spacing:.4px;padding:7px 9px;
   border-bottom:1px solid var(--line)}
td{padding:8px 9px;border-bottom:1px solid #1d2028}
tr:last-child td{border-bottom:0}
.tag{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:600}
.tw{background:rgba(34,197,94,.15);color:var(--green)}
.tl{background:rgba(239,68,68,.15);color:var(--red)}
.tlo{background:rgba(34,197,94,.15);color:var(--green)}
.tsh{background:rgba(239,68,68,.15);color:var(--red)}
.empty{padding:20px;text-align:center;color:var(--muted)}
img{max-width:100%;border-radius:8px;margin-top:3px}
.ss{margin-bottom:22px}
.warn{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);
      color:var(--orange);padding:9px 13px;border-radius:8px;
      margin-bottom:14px;font-size:12px}
@media(max-width:600px){main{padding:12px}.kpi .val{font-size:17px}}
"""


def build_html(results, all_trades, eq_b64, bar_b64, period_str, ran_at):
    tw = sum(r["wins"]   for r in results.values())
    tl = sum(r["losses"] for r in results.values())
    tn = sum(r["n"]      for r in results.values())
    tr_ = sum(r["net_r"] for r in results.values())
    dec = tw + tl
    wr  = (tw / dec * 100) if dec else 0.0
    nrc = "green" if tr_ >= 0 else "red"
    wrc = "green" if wr   >= 50 else "red"

    kpis = (
        '<div class="grid krow">'
        f'<div class="card kpi"><div class="lbl">Toplam Trade</div>'
        f'<div class="val blue">{tn}</div><div class="sub">{period_str}</div></div>'
        f'<div class="card kpi"><div class="lbl">Win Rate</div>'
        f'<div class="val {wrc}">{wr:.1f}<span style="font-size:13px"> %</span></div>'
        f'<div class="sub">{tw} W / {tl} L</div></div>'
        f'<div class="card kpi"><div class="lbl">Net R</div>'
        f'<div class="val {nrc}">{tr_:+.2f}</div>'
        f'<div class="sub">Fee {FEE_PCT}% + Slip {SLIP_PCT}% dahil</div></div>'
        f'<div class="card kpi"><div class="lbl">Parite</div>'
        f'<div class="val">{len(SYMBOLS)}</div>'
        f'<div class="sub">OKX Perp 4H</div></div>'
        f'<div class="card kpi"><div class="lbl">Model</div>'
        f'<div class="val">{len(RUN_MODELS)}</div>'
        f'<div class="sub">{" / ".join(RUN_MODELS)}</div></div>'
        '</div>'
    )

    rows = []
    for sym, r in results.items():
        d   = r["wins"] + r["losses"]
        w   = (r["wins"] / d * 100) if d else 0.0
        wc  = "green" if w      >= 50 else "red"
        nc  = "green" if r["net_r"] >= 0  else "red"
        rows.append(
            f'<tr><td><b>{sym}</b></td><td>{r["n"]}</td>'
            f'<td class="{wc}">{w:.1f}%</td>'
            f'<td class="{nc}">{r["net_r"]:+.2f}</td>'
            f'<td class="{nc}">{r["avg_r"]:+.2f}</td>'
            f'<td>{r["max_win"]:+.2f}</td>'
            f'<td class="red">{r["max_loss"]:+.2f}</td>'
            f'<td>{r["open"]}</td></tr>'
        )
    smry = (
        '<table><thead><tr><th>Sembol</th><th>n</th><th>WR</th><th>Net R</th>'
        '<th>Avg R</th><th>Best</th><th>Worst</th><th>Acik</th></tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody></table>'
    )

    allc = sorted([t for t in all_trades if t.outcome in ("WIN","LOSS")],
                  key=lambda t: t.open_time, reverse=True)[:60]
    trows = []
    for t in allc:
        oc = "tw" if t.outcome=="WIN" else "tl"
        dc = "tlo" if t.direction=="LONG" else "tsh"
        rc = "green" if (t.r_multiple or 0) >= 0 else "red"
        rr = abs(t.tp-t.entry)/abs(t.entry-t.stop) if abs(t.entry-t.stop)>0 else 0
        sym = getattr(t, "symbol", "?")
        trows.append(
            f'<tr>'
            f'<td>{t.open_time.strftime("%m-%d %H:%M") if t.open_time else "—"}</td>'
            f'<td><b>{sym}</b></td>'
            f'<td><b>{t.model.replace("_"," ").upper()}</b></td>'
            f'<td><span class="tag {dc}">{t.direction}</span></td>'
            f'<td>{t.entry:.4f}</td>'
            f'<td style="color:#f87171">{t.stop:.4f}</td>'
            f'<td style="color:#4ade80">{t.tp:.4f}</td>'
            f'<td style="color:#8c93a3">{rr:.1f}x</td>'
            f'<td><span class="tag {oc}">{t.outcome}</span></td>'
            f'<td class="{rc}">{(t.r_multiple or 0):+.2f}R</td>'
            f'</tr>'
        )
    ttbl = (
        '<table><thead><tr>'
        '<th>Zaman</th><th>Sembol</th><th>Model</th><th>Yon</th>'
        '<th>Entry</th><th style="color:#f87171">SL</th>'
        '<th style="color:#4ade80">TP</th><th>RR</th><th>Sonuc</th><th>R</th>'
        '</tr></thead><tbody>' + ''.join(trows) + '</tbody></table>'
        if trows else '<div class="empty">Trade yok</div>'
    )

    symsec = ""
    for sym, r in results.items():
        img  = f'<img src="data:image/png;base64,{r["cb64"]}" />' if r.get("cb64") else ""
        noc  = '<div class="empty">Yeterli trade yok</div>'
        symsec += (
            f'<div class="ss"><div class="card">'
            f'<h2>{sym} -- 4H setup goruntumu</h2>'
            f'{img or noc}</div></div>'
        )

    eq_img  = f'<img src="data:image/png;base64,{eq_b64}" />'  if eq_b64  else ""
    bar_img = f'<img src="data:image/png;base64,{bar_b64}" />' if bar_b64 else ""

    return (
        '<!DOCTYPE html><html lang="tr"><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>ICT Backtest -- Son 3 Ay</title>'
        f'<style>{CSS}</style></head><body>'
        '<header>'
        '<h1>\U0001f4ca ICT Backtest Raporu -- Son 3 Ay (4H, 12 Parite)</h1>'
        f'<span style="color:#8c93a3;font-size:11px">Olusturuldu: {ran_at} UTC</span>'
        '</header><main>'
        '<div class="warn">Bu backtest in-sample sonuclaridir. '
        f'Fee: {FEE_PCT}% + Slippage: {SLIP_PCT}% her yon dahil. '
        'Gecmis performans gelecegi garanti etmez.</div>'
        + kpis
        + '<div class="grid" style="grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px">'
        f'<div class="card"><h2>Equity Egrisi</h2>{eq_img}</div>'
        f'<div class="card"><h2>Parite Karsilastirma</h2>{bar_img}</div>'
        '</div>'
        f'<div class="card" style="margin-bottom:18px"><h2>Parite Ozet</h2>{smry}</div>'
        + symsec
        + f'<div class="card"><h2>\U0001f4cb Trade Listesi (son 60)</h2>{ttbl}</div>'
        '</main></body></html>'
    )


def main():
    fetcher = OKXFetcher()
    results, all_trades = {}, []
    period_str = ""

    print(f"Backtest: {len(SYMBOLS)} parite | TF={TF} | "
          f"Modeller={list(RUN_MODELS)} | {LIMIT} mum")
    print(f"Fee={FEE_PCT}%  Slippage={SLIP_PCT}%  Cooldown={COOLDOWN}\n")

    for sym in SYMBOLS:
        print(f"  {sym}...", end="", flush=True)
        df = fetcher.fetch_ohlcv(sym, TF, limit=LIMIT)
        if df is None or len(df) < WINDOW + 20:
            print(" HATA")
            continue
        if not period_str:
            period_str = (f"{df.index[0].strftime('%Y-%m-%d')} -> "
                          f"{df.index[-1].strftime('%Y-%m-%d')}")
        trades, stats = run_backtest(
            df, RUN_MODELS, window=WINDOW, cooldown=COOLDOWN,
            max_concurrent=1, fee_pct=FEE_PCT, slippage_pct=SLIP_PCT,
        )
        for t in trades:
            t.symbol = sym
        all_trades.extend(trades)
        dec = stats.wins + stats.losses
        wr  = (stats.wins / dec * 100) if dec else 0.0
        cr  = [t.r_multiple for t in trades
               if t.r_multiple is not None and t.outcome in ("WIN","LOSS")]
        net_r = sum(cr)
        print(f" {stats.total}t WR{wr:.0f}% Net{net_r:+.1f}R")
        results[sym] = {
            "n": stats.total, "wins": stats.wins, "losses": stats.losses,
            "open": stats.open,
            "net_r": round(net_r, 3),
            "avg_r": round(net_r/len(cr), 3) if cr else 0.0,
            "max_win":  round(max(cr, default=0.0), 3),
            "max_loss": round(min(cr, default=0.0), 3),
            "wr": wr, "cb64": plot_price(df, trades, sym),
        }

    print("\nGrafikler...")
    eq_b64  = plot_equity(all_trades)
    bar_b64 = plot_bars(results)
    ran_at  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    html    = build_html(results, all_trades, eq_b64, bar_b64, period_str, ran_at)

    import pathlib
    pathlib.Path("docs").mkdir(exist_ok=True)
    out = "docs/backtest_report.html"
    pathlib.Path(out).write_text(html, encoding="utf-8")
    print(f"Rapor: {out}  ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
