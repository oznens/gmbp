"""
1 yıllık veride judas_swing + sbs modelleri için kapsamlı backtest.
Veri zaten data/*.csv'de mevcut.

Çalıştırma:
  python analysis/fulltest_1y.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from backtest_history import MODELS, run_backtest

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
    "BNBUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT",
    "OPUSDT", "ARBUSDT", "LTCUSDT", "ADAUSDT",
]
RUN_MODELS = {k: MODELS[k] for k in ("judas_swing", "sbs") if k in MODELS}
DATA_DIR   = Path("data")

PARAMS = {
    "window":       100,
    "cooldown":     10,
    "fee_pct":      0.05,
    "slip_pct":     0.03,
    "max_pending":  12,
    "ema":          50,
}


def run_all(ema: int):
    total_n = total_w = total_l = total_r = total_cancelled = 0
    sym_results = {}
    for sym in SYMBOLS:
        csv = DATA_DIR / f"{sym}_4H_1Y.csv"
        if not csv.exists():
            continue
        df = pd.read_csv(csv, index_col=0, parse_dates=True)
        trades, stats = run_backtest(
            df, RUN_MODELS,
            window=PARAMS["window"], cooldown=PARAMS["cooldown"],
            max_concurrent=1,
            fee_pct=PARAMS["fee_pct"], slippage_pct=PARAMS["slip_pct"],
            max_bars_pending=PARAMS["max_pending"],
            trend_ema=ema,
        )
        closed_r = [t.r_multiple for t in trades
                    if t.r_multiple is not None and t.outcome in ("WIN", "LOSS")]
        net_r = sum(closed_r)
        wr    = stats.wins / (stats.wins + stats.losses) * 100 if (stats.wins + stats.losses) else 0
        total_n += stats.total; total_w += stats.wins; total_l += stats.losses
        total_r += net_r; total_cancelled += stats.cancelled
        sym_results[sym] = {
            "n": stats.total, "wins": stats.wins, "losses": stats.losses,
            "cancelled": stats.cancelled, "net_r": round(net_r, 3),
            "wr": round(wr, 1),
            "avg_r": round(net_r / max(len(closed_r), 1), 3),
            "period": f"{df.index[0].strftime('%Y-%m-%d')} → {df.index[-1].strftime('%Y-%m-%d')}",
        }
    overall_wr = total_w / (total_w + total_l) * 100 if (total_w + total_l) else 0
    return {
        "ema": ema,
        "total_n": total_n, "total_w": total_w, "total_l": total_l,
        "total_r": round(total_r, 3), "total_cancelled": total_cancelled,
        "overall_wr": round(overall_wr, 1),
        "avg_r": round(total_r / max(total_w + total_l, 1), 3),
        "symbols": sym_results,
    }


def main():
    print("1 Yıllık Backtest — judas_swing + sbs | EMA karşılaştırması\n")

    best_ema = 0
    best_r   = -999
    all_results = {}

    for ema in [0, 20, 50, 100, 200]:
        r = run_all(ema)
        all_results[ema] = r
        marker = ""
        if r["total_r"] > best_r:
            best_r = r["total_r"]
            best_ema = ema
            marker = " ◄ EN İYİ"
        print(f"EMA={ema:3d} | n={r['total_n']:4d} WR={r['overall_wr']:5.1f}% "
              f"NetR={r['total_r']:+8.2f} avgR={r['avg_r']:+.3f} "
              f"iptal={r['total_cancelled']}{marker}")

    print(f"\n► Optimal EMA: {best_ema}  Net R: {best_r:+.2f}R\n")

    # Optimal EMA ile sembol detayı
    best = all_results[best_ema]
    print(f"{'Sembol':<12} {'n':>4} {'WR%':>7} {'NetR':>8} {'AvgR':>7} {'İptal':>6}")
    print("-" * 50)
    sorted_syms = sorted(best["symbols"].items(), key=lambda x: x[1]["net_r"], reverse=True)
    for sym, s in sorted_syms:
        flag = " ✅" if s["net_r"] > 0 else " ❌"
        print(f"{sym:<12} {s['n']:>4d} {s['wr']:>6.1f}% {s['net_r']:>+8.3f} "
              f"{s['avg_r']:>+7.3f} {s['cancelled']:>6}{flag}")

    # JSON kaydet
    out = Path("analysis/fulltest_1y_results.json")
    out.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nSonuçlar: {out}")

    # Zararlı sembolleri belirle
    losers = [s for s, d in best["symbols"].items() if d["net_r"] < -3]
    winners = [s for s, d in best["symbols"].items() if d["net_r"] > 0]
    print(f"\nKarlı semboller: {winners}")
    print(f"Kötü semboller (öneri: çıkar): {losers}")


if __name__ == "__main__":
    main()
