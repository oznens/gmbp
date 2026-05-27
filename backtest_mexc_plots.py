"""4 sembol icin son 30 gun MEXC backtest grafigi.

Her sembol icin tek PNG:
  - Ust panel: fiyat (OHLC mum-cubuk) + trade entry/exit isaretleri,
    SL/TP yatay segmentleri, model+yon+R etiketi
  - Alt panel: kumulatif R (equity curve, o sembol icin)

Cikti: docs/backtest/<symbol>.png (kullanici gondermesi icin)
"""
from __future__ import annotations
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

from utils.mexc_fetcher import MEXCFetcher
from backtest_history import run_backtest, MODELS

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
MODELS_SEL = {k: MODELS[k] for k in ("judas_swing", "sbs")}
TF = "4h"
LIMIT = 500
WINDOW = 200
COOLDOWN = 5
LOOKBACK_DAYS = 30

MODEL_COLORS = {
    "judas_swing": "#5fa8d3",
    "sbs": "#f4a261",
}


def plot_symbol(symbol: str, df, trades, out_path: Path) -> int:
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=LOOKBACK_DAYS)
    # Son 30g + entry-to-exit gostermek icin biraz fazlasi
    df_plot = df[df.index >= (cutoff - dt.timedelta(days=2))]
    if df_plot.empty:
        return 0
    trades_recent = [t for t in trades
                     if t.close_time and t.close_time.replace(tzinfo=None) >= cutoff
                     and t.outcome in ("WIN", "LOSS")]
    if not trades_recent:
        return 0

    fig = plt.figure(figsize=(15, 8))
    gs = fig.add_gridspec(3, 1, hspace=0.05)
    ax = fig.add_subplot(gs[:2])
    ax2 = fig.add_subplot(gs[2], sharex=ax)
    fig.patch.set_facecolor("#0f1419")
    for a in (ax, ax2):
        a.set_facecolor("#0f1419")
        for s in a.spines.values():
            s.set_color("#3d4855")
        a.tick_params(colors="#aeb6c2")
        a.grid(True, alpha=0.12, color="#aeb6c2")

    # OHLC mum cubugu
    width = 0.65 * (df_plot.index[1] - df_plot.index[0]).total_seconds() / 86400.0
    for ts, row in df_plot.iterrows():
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        color = "#26a69a" if c >= o else "#ef5350"
        x = mdates.date2num(ts)
        ax.plot([x, x], [l, h], color=color, linewidth=0.8, zorder=1)
        ax.add_patch(Rectangle(
            (x - width / 2, min(o, c)), width, abs(c - o) or (h - l) * 0.001,
            facecolor=color, edgecolor=color, linewidth=0.6, alpha=0.85, zorder=2,
        ))

    # Trade isaretleri
    for t in trades_recent:
        ot = t.open_time
        ct = t.close_time
        ox, cx = mdates.date2num(ot), mdates.date2num(ct)
        col = MODEL_COLORS.get(t.model, "#bbbbbb")
        # Entry-Exit segmenti
        ax.plot([ox, cx], [t.entry, t.exit_price],
                color=col, linewidth=1.4, alpha=0.85, zorder=3)
        # Entry marker
        ax.scatter([ox], [t.entry],
                   marker="^" if t.direction == "LONG" else "v",
                   color=col, edgecolor="white", linewidth=0.6,
                   s=110, zorder=4)
        # Exit marker (WIN/LOSS)
        win = t.outcome == "WIN"
        ax.scatter([cx], [t.exit_price],
                   marker="o", color="#2ecc71" if win else "#e74c3c",
                   edgecolor="white", linewidth=0.6, s=70, zorder=4)
        # SL/TP yatay parcalari (entry'den exit'e)
        ax.plot([ox, cx], [t.stop, t.stop], color="#e74c3c",
                linewidth=0.8, linestyle=":", alpha=0.55, zorder=2)
        ax.plot([ox, cx], [t.tp, t.tp], color="#2ecc71",
                linewidth=0.8, linestyle=":", alpha=0.55, zorder=2)
        # Etiket (entry uzerine)
        ax.annotate(
            f"{t.model[:3]}·{t.direction[0]}·{t.r_multiple:+.1f}R",
            xy=(ox, t.entry),
            xytext=(0, 10 if t.direction == "LONG" else -16),
            textcoords="offset points",
            color=col, fontsize=7, ha="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="#0f1419", ec=col, lw=0.5, alpha=0.85),
        )

    # X ekseni
    ax.set_xlim(mdates.date2num(cutoff), mdates.date2num(df_plot.index[-1]))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.setp(ax.get_xticklabels(), visible=False)

    # Baslik + stats
    n = len(trades_recent)
    wins = sum(1 for t in trades_recent if t.outcome == "WIN")
    sumr = sum(t.r_multiple for t in trades_recent)
    wr = (wins / n * 100) if n else 0.0
    ax.set_title(
        f"{symbol}  ·  son {LOOKBACK_DAYS}g  ·  TF {TF}  ·  "
        f"n={n}  W={wins}  WR=%{wr:.1f}  netR={sumr:+.2f}",
        color="white", fontsize=12, loc="left", pad=10,
    )
    ax.set_ylabel("Fiyat (USDT)", color="#aeb6c2")

    # Cumulative R panel
    trades_sorted = sorted(trades_recent, key=lambda t: t.close_time)
    times = [t.close_time for t in trades_sorted]
    cum_r = []
    s = 0.0
    for t in trades_sorted:
        s += t.r_multiple
        cum_r.append(s)
    ax2.fill_between(times, cum_r, 0,
                     where=[r >= 0 for r in cum_r],
                     color="#2ecc71", alpha=0.25, step="post")
    ax2.fill_between(times, cum_r, 0,
                     where=[r < 0 for r in cum_r],
                     color="#e74c3c", alpha=0.25, step="post")
    ax2.plot(times, cum_r, color="#5fa8d3", linewidth=1.4, drawstyle="steps-post")
    ax2.axhline(0, color="#aeb6c2", linewidth=0.5, alpha=0.5)
    ax2.set_ylabel("Kum. R", color="#aeb6c2")
    ax2.set_xlabel("Tarih", color="#aeb6c2")
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    # Legend (sag ust)
    handles = [
        plt.Line2D([0], [0], marker="^", color="w",
                   markerfacecolor="#5fa8d3", markersize=8, label="judas_swing"),
        plt.Line2D([0], [0], marker="^", color="w",
                   markerfacecolor="#f4a261", markersize=8, label="sbs"),
        plt.Line2D([0], [0], marker="o", color="w",
                   markerfacecolor="#2ecc71", markersize=7, label="WIN exit"),
        plt.Line2D([0], [0], marker="o", color="w",
                   markerfacecolor="#e74c3c", markersize=7, label="LOSS exit"),
        plt.Line2D([0], [0], color="#2ecc71", linestyle=":", label="TP"),
        plt.Line2D([0], [0], color="#e74c3c", linestyle=":", label="SL"),
    ]
    ax.legend(handles=handles, loc="upper left", facecolor="#1a1f26",
              edgecolor="#3d4855", labelcolor="white", fontsize=8,
              framealpha=0.85, ncol=3)

    fig.savefig(out_path, dpi=110, facecolor=fig.get_facecolor(),
                bbox_inches="tight")
    plt.close(fig)
    return n


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default="docs/backtest")
    p.add_argument("--lookback", type=int, default=LOOKBACK_DAYS)
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fetcher = MEXCFetcher()
    print(f"\n  MEXC futures backtest plots  ·  son {args.lookback}g  ·  {TF}\n")
    written = []
    for sym in SYMBOLS:
        df = fetcher.fetch_ohlcv(sym, TF, limit=LIMIT)
        if df is None or len(df) < WINDOW + 50:
            print(f"  {sym}: veri yetersiz")
            continue
        trades, _ = run_backtest(df, MODELS_SEL, window=WINDOW, cooldown=COOLDOWN,
                                 max_concurrent=1, fee_pct=0.05, slippage_pct=0.02)
        out = out_dir / f"{sym}.png"
        n = plot_symbol(sym, df, trades, out)
        if n:
            print(f"  {sym}: {n} trade -> {out}")
            written.append(str(out))
        else:
            print(f"  {sym}: son {args.lookback}g trade yok")
    print()
    for p in written:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
