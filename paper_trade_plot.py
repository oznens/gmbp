"""paper_trade_log.json'dan live equity curve + drawdown PNG cizer.

Cron her run sonunda calistirabilir ya da elle:
    .venv/bin/python paper_trade_plot.py
    .venv/bin/python paper_trade_plot.py --out live.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--log", default="paper_trade_log.json")
    p.add_argument("--out", default="paper_trade_equity.png")
    args = p.parse_args(argv)

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"Log yok: {log_path}")
        return 1
    entries = json.loads(log_path.read_text())
    closed = [e for e in entries if e.get("status") == "closed"]
    if not closed:
        print(f"{len(entries)} entry var ama kapanmis trade yok (henuz).")
        print("Cron birkac sefer calistiktan sonra tekrar dene.")
        return 0

    closed.sort(key=lambda e: e.get("close_ts", 0))
    times = [pd.Timestamp(e["close_ts"], unit="ms") for e in closed]
    rs = [float(e.get("r_multiple", 0) or 0) for e in closed]
    pnls = [float(e.get("realized_pnl", 0) or 0) for e in closed]
    cum_r, cum_pnl = [], []
    s_r, s_p = 0.0, 0.0
    for r, pnl in zip(rs, pnls):
        s_r += r; s_p += pnl
        cum_r.append(s_r); cum_pnl.append(s_p)
    peak = cum_r[0]
    dd = []
    for x in cum_r:
        peak = max(peak, x)
        dd.append(x - peak)

    wins = sum(1 for r in rs if r > 0)
    wr = wins / len(rs) * 100
    open_count = sum(1 for e in entries if e.get("status") == "placed")

    fig, axes = plt.subplots(2, 1, figsize=(10, 7),
                             gridspec_kw={"height_ratios": [3, 2]})
    fig.suptitle(
        f"OKX Paper Trade — {len(closed)} kapali trade, WR %{wr:.1f}, "
        f"net {s_r:+.2f}R / {s_p:+.2f} USDT  ({open_count} acik)",
        fontsize=11, fontweight="bold",
    )

    ax = axes[0]
    ax.plot(times, cum_r, color="tab:blue", linewidth=1.8, label="Cumulative R")
    ax.axhline(0, color="grey", linewidth=0.6, linestyle="--")
    ax.set_ylabel("Cumulative R", color="tab:blue")
    ax.grid(alpha=0.3)
    ax2 = ax.twinx()
    ax2.plot(times, cum_pnl, color="tab:orange", linewidth=1.2, alpha=0.7,
             label="Cumulative USDT")
    ax2.set_ylabel("Cumulative USDT", color="tab:orange")
    win_pts = [(t, c) for t, c, r in zip(times, cum_r, rs) if r > 0]
    loss_pts = [(t, c) for t, c, r in zip(times, cum_r, rs) if r <= 0]
    if win_pts:
        ax.scatter(*zip(*win_pts), color="green", s=20, zorder=5, label=f"WIN ({len(win_pts)})")
    if loss_pts:
        ax.scatter(*zip(*loss_pts), color="red", s=20, zorder=5, label=f"LOSS ({len(loss_pts)})")
    ax.legend(loc="upper left", fontsize=8)

    ax = axes[1]
    ax.fill_between(times, dd, 0, color="tab:red", alpha=0.3)
    ax.plot(times, dd, color="tab:red", linewidth=1.2)
    ax.set_ylabel("Drawdown (R)")
    ax.set_title(f"Max drawdown: {min(dd):+.2f}R", fontsize=10)
    ax.grid(alpha=0.3)
    for a in axes:
        a.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    fig.autofmt_xdate(rotation=0)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(args.out, dpi=120)
    print(f"Kaydedildi: {args.out}  ({len(closed)} trade, net {s_r:+.2f}R)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
