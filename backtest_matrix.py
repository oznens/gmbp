"""Multi-symbol / multi-TF backtest matrisi.

Karli 3 modeli (judas_swing, sbs, inducement) farkli sembol/TF
kombinasyonlarinda calistirir, sonuclari ozet tablo halinde basar.

Kullanim:
    .venv/bin/python backtest_matrix.py
    .venv/bin/python backtest_matrix.py --symbols BTC,ETH --tfs 1h,4h
    .venv/bin/python backtest_matrix.py --plot equity_{symbol}_{tf}.png
"""
from __future__ import annotations

import argparse
import logging
import sys

from utils.okx_fetcher import OKXFetcher
from backtest_history import MODELS, run_backtest, plot_equity

DEFAULT_MODELS = ["judas_swing", "sbs", "inducement"]
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
DEFAULT_TFS = ["15m", "1h", "4h"]


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    p.add_argument("--tfs", default=",".join(DEFAULT_TFS))
    p.add_argument("--models", default=",".join(DEFAULT_MODELS))
    p.add_argument("--limit", type=int, default=1500)
    p.add_argument("--window", type=int, default=200)
    p.add_argument("--cooldown", type=int, default=5)
    p.add_argument("--concurrent", type=int, default=1)
    p.add_argument("--plot", default="",
                   help="Path template, kullanilabilir placeholder: {symbol},{tf}")
    p.add_argument("--fee", type=float, default=0.0,
                   help="Tek-yon komisyon yuzdesi (orn. 0.05 = %%0.05).")
    p.add_argument("--slippage", type=float, default=0.0,
                   help="Tek-yon slippage+spread yuzdesi.")
    args = p.parse_args(argv)

    # Modellerin DEBUG/ERROR loglarini bastir
    logging.basicConfig(level=logging.CRITICAL)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    tfs = [t.strip() for t in args.tfs.split(",") if t.strip()]
    model_names = [m.strip() for m in args.models.split(",") if m.strip()]
    selected = {n: MODELS[n] for n in model_names if n in MODELS}
    if not selected:
        print("Hicbir model secilemedi.")
        return 1

    print(f"Matrix: {len(symbols)} sembol x {len(tfs)} TF = {len(symbols) * len(tfs)} run")
    print(f"Modeller: {', '.join(selected)}\n")

    fetcher = OKXFetcher()
    rows = []  # (sembol, tf, trades, wr, avgR, netR, max_dd, bars)
    for sym in symbols:
        for tf in tfs:
            df = fetcher.fetch_ohlcv(sym, tf, limit=args.limit)
            if df is None or df.empty:
                print(f"  {sym}/{tf}: veri yok, atlandi")
                continue
            trades, stats = run_backtest(df, selected, window=args.window,
                                          cooldown=args.cooldown,
                                          max_concurrent=args.concurrent,
                                          fee_pct=args.fee,
                                          slippage_pct=args.slippage)
            closed = [t for t in trades if t.r_multiple is not None]
            n = len(closed)
            wins = sum(1 for t in closed if t.r_multiple > 0)
            wr = (wins / n * 100) if n else 0.0
            net = sum(t.r_multiple for t in closed)
            avg = (net / n) if n else 0.0
            # Drawdown
            closed.sort(key=lambda t: t.close_time)
            cum, peak, max_dd = 0.0, 0.0, 0.0
            for t in closed:
                cum += t.r_multiple
                peak = max(peak, cum)
                max_dd = min(max_dd, cum - peak)
            rows.append({
                "symbol": sym, "tf": tf, "bars": len(df),
                "trades": n, "wr": wr, "avgR": avg, "netR": net, "max_dd": max_dd,
            })
            print(f"  {sym}/{tf}: {n:>3} trade, WR {wr:5.1f}%, "
                  f"net {net:+7.2f}R, max DD {max_dd:+6.2f}R")
            if args.plot and n > 0:
                path = args.plot.format(symbol=sym, tf=tf)
                plot_equity(trades, df, sym, tf, path)

    # Sirali ozet
    rows.sort(key=lambda r: -r["netR"])
    print()
    print("=" * 78)
    print("MATRIX OZETI (netR'e gore sirali)")
    print("=" * 78)
    print(f"{'sembol/TF':<14} {'bars':>5} {'trade':>6} {'WR%':>6} "
          f"{'avgR':>7} {'netR':>8} {'maxDD':>8}")
    print("-" * 78)
    for r in rows:
        print(f"{r['symbol']+'/'+r['tf']:<14} {r['bars']:>5} {r['trades']:>6} "
              f"{r['wr']:>5.1f} {r['avgR']:>+7.2f} {r['netR']:>+8.2f} {r['max_dd']:>+8.2f}")
    print()
    pos = [r for r in rows if r["netR"] > 0]
    if pos:
        best = pos[0]
        print(f"En karli: {best['symbol']}/{best['tf']} -> "
              f"{best['netR']:+.2f}R, {best['trades']} trade, WR %{best['wr']:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
