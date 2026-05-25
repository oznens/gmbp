"""Walk-forward backtest: 2.3 yillik veriyi 2 yariya bol, ayni stratejiyi
her iki dilimde test et. Out-of-sample tutarlilik testi.

Default: BTC/ETH/SOL/XRP @ 4h, 5000 mum (~2.3 yil), judas_swing + sbs,
OKX taker fee 0.05% + 0.02% slippage.

Kullanim:
    .venv/bin/python backtest_walkforward.py
    .venv/bin/python backtest_walkforward.py --symbols BTC,ETH --splits 3
"""
from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from utils.okx_fetcher import OKXFetcher
from backtest_history import MODELS, run_backtest


def summarize(trades) -> dict:
    closed = [t for t in trades if t.r_multiple is not None]
    n = len(closed)
    if n == 0:
        return {"n": 0, "wr": 0.0, "netR": 0.0, "avgR": 0.0, "max_dd": 0.0}
    wins = sum(1 for t in closed if t.r_multiple > 0)
    net = sum(t.r_multiple for t in closed)
    closed.sort(key=lambda t: t.close_time)
    cum, peak, max_dd = 0.0, 0.0, 0.0
    for t in closed:
        cum += t.r_multiple
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)
    return {"n": n, "wr": wins / n * 100, "netR": net, "avgR": net / n, "max_dd": max_dd}


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT")
    p.add_argument("--tf", default="4h")
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--splits", type=int, default=2,
                   help="Veriyi kac esit parcaya bol (2 -> ilk yari / son yari)")
    p.add_argument("--models", default="judas_swing,sbs")
    p.add_argument("--window", type=int, default=200)
    p.add_argument("--cooldown", type=int, default=5)
    p.add_argument("--fee", type=float, default=0.05)
    p.add_argument("--slippage", type=float, default=0.02)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.CRITICAL)

    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    model_names = [m.strip() for m in args.models.split(",")]
    selected = {n: MODELS[n] for n in model_names if n in MODELS}
    print(f"Walk-forward: {len(symbols)} sembol @ {args.tf}, {args.limit} mum, "
          f"{args.splits} dilim, fee={args.fee}% slip={args.slippage}%")
    print(f"Modeller: {', '.join(selected)}\n")

    fetcher = OKXFetcher()
    all_rows = []
    for sym in symbols:
        df = fetcher.fetch_ohlcv(sym, args.tf, limit=args.limit)
        if df is None or len(df) < args.window * (args.splits + 1):
            print(f"  {sym}: veri yetersiz, atlandi ({0 if df is None else len(df)} mum)")
            continue
        n_total = len(df)
        size = n_total // args.splits
        print(f"--- {sym} ({n_total} mum, {df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d}) ---")
        period_results = []
        for k in range(args.splits):
            start = k * size
            end = (k + 1) * size if k < args.splits - 1 else n_total
            seg = df.iloc[start:end]
            label = f"P{k + 1}/{args.splits}"
            trades, _ = run_backtest(seg, selected, window=args.window,
                                      cooldown=args.cooldown,
                                      fee_pct=args.fee, slippage_pct=args.slippage)
            s = summarize(trades)
            period_results.append({"sym": sym, "label": label,
                                   "start": seg.index[0], "end": seg.index[-1], **s})
            print(f"  {label}  {seg.index[0]:%Y-%m-%d} -> {seg.index[-1]:%Y-%m-%d}  "
                  f"{s['n']:>3} trade, WR {s['wr']:5.1f}%, "
                  f"net {s['netR']:+7.2f}R, DD {s['max_dd']:+6.2f}R")
        all_rows.extend(period_results)
        # Tutarlilik (R consistency between periods)
        nets = [r["netR"] for r in period_results]
        wrs = [r["wr"] for r in period_results]
        net_consistency = "✓ tutarli" if all(n > 0 for n in nets) else (
            "△ kismi" if any(n > 0 for n in nets) else "✗ basarisiz"
        )
        wr_range = max(wrs) - min(wrs) if wrs else 0
        print(f"  TUTARLILIK: {net_consistency}, WR range {wr_range:.1f}pp\n")

    # Genel ozet
    print("=" * 90)
    print("WALK-FORWARD OZETI")
    print("=" * 90)
    print(f"{'sembol':<10}{'donem':<8}{'tarih araligi':<26}{'trade':>6}{'WR%':>7}{'netR':>9}{'maxDD':>8}")
    print("-" * 90)
    for r in all_rows:
        period_str = f"{r['start']:%Y-%m-%d}..{r['end']:%Y-%m-%d}"
        print(f"{r['sym']:<10}{r['label']:<8}{period_str:<26}"
              f"{r['n']:>6}{r['wr']:>6.1f} {r['netR']:>+8.2f}{r['max_dd']:>+8.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
