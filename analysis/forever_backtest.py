"""
Forever Model [Pro+] (Sniper) — eksiksiz backtest (SMT için çift varlık).

Her sembol bir SMT eşiyle hizalanır (ortak zaman indeksi), model her barda
hem kendi penceresini hem eş varlığın penceresini görür → gerçek SMT diverjansı.

Limit giriş (FVG CE) backtest_history.simulate_trade ile fill kontrolüne tabidir.

Çalıştırma:
  python analysis/forever_backtest.py --tf 1h
  python analysis/forever_backtest.py --tf 4h --no-smt
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from backtest_history import Trade, Stats, simulate_trade, normalize_signal
from models.forever_model import ForeverModel

DATA_DIR = Path("data")
FEE_PCT  = 0.05
SLIP_PCT = 0.02

# SMT eş varlık haritası (korelasyonlu çiftler)
SMT_PAIR = {
    "BTCUSDT": "ETHUSDT",  "ETHUSDT": "BTCUSDT",
    "SOLUSDT": "AVAXUSDT", "AVAXUSDT": "SOLUSDT",
    "ARBUSDT": "OPUSDT",   "OPUSDT": "ARBUSDT",
    "BNBUSDT": "BTCUSDT",  "LTCUSDT": "BTCUSDT",
    "ADAUSDT": "XRPUSDT",  "XRPUSDT": "ADAUSDT",
    "LINKUSDT": "ETHUSDT", "DOGEUSDT": "SOLUSDT",
}

SYMBOLS = list(SMT_PAIR.keys())


def load(tf: str, sym: str) -> pd.DataFrame | None:
    csv = DATA_DIR / f"{sym}_{tf.upper()}_1Y.csv"
    if not csv.exists():
        return None
    df = pd.read_csv(csv, index_col=0, parse_dates=True)
    df.columns = [x.lower() for x in df.columns]
    return df


TP_MODE = "rr"  # main() ile override edilir


def run_symbol(tf: str, sym: str, require_smt: bool,
               window: int, cooldown: int, max_pending: int,
               trend_ema: int = 0):
    prim = load(tf, sym)
    if prim is None:
        return None
    pair = load(tf, SMT_PAIR[sym]) if require_smt else None

    # Ortak zaman indeksine hizala
    if pair is not None:
        common = prim.index.intersection(pair.index)
        prim = prim.loc[common]
        pair = pair.loc[common]
        if len(prim) < window + 50:
            return None

    model = ForeverModel()
    model.REQUIRE_SMT = require_smt
    model.TP_MODE = TP_MODE

    ema = prim["close"].ewm(span=trend_ema, adjust=False).mean().values if trend_ema else None

    trades: list[Trade] = []
    open_trades: list[Trade] = []
    last_sig = -10**9

    n = len(prim)
    for i in range(window, n - 1):
        # açık trade'leri güncelle
        still = []
        for t in open_trades:
            simulate_trade(prim, t, fee_pct=FEE_PCT, slippage_pct=SLIP_PCT,
                           max_bars_pending=max_pending)
            if t.outcome == "CANCELLED":
                trades.append(t); continue
            if t.outcome and t.outcome != "OPEN" and t.close_idx is not None and t.close_idx <= i:
                trades.append(t); continue
            still.append(t)
        open_trades = still
        if open_trades:
            continue
        if i - last_sig < cooldown:
            continue

        win_p = prim.iloc[i - window:i]
        win_q = pair.iloc[i - window:i] if pair is not None else None
        try:
            sig = model.detect(win_p, win_q)
        except Exception:
            continue
        if not sig:
            continue
        norm = normalize_signal(sig, min_risk_pct=0.30)
        if norm is None:
            continue
        # trend filtresi (opsiyonel)
        if ema is not None:
            close_now = float(prim["close"].iloc[i])
            if norm["direction"] == "LONG" and close_now < ema[i]:
                continue
            if norm["direction"] == "SHORT" and close_now > ema[i]:
                continue
        t = Trade(model="forever", direction=norm["direction"],
                  entry=norm["entry"], stop=norm["stop"], tp=norm["tp"],
                  open_idx=i, open_time=prim.index[i])
        open_trades.append(t)
        last_sig = i

    for t in open_trades:
        simulate_trade(prim, t, fee_pct=FEE_PCT, slippage_pct=SLIP_PCT,
                       max_bars_pending=max_pending)
        trades.append(t)

    stats = Stats()
    for t in trades:
        stats.add(t)
    return stats, trades, prim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--no-smt", action="store_true", help="SMT'siz (saf sniper)")
    ap.add_argument("--ema", type=int, default=0)
    ap.add_argument("--tp", default="rr", choices=["rr", "erl"], help="TP modu")
    ap.add_argument("--cooldown", type=int, default=-1)
    args = ap.parse_args()

    global TP_MODE
    TP_MODE = args.tp

    tf = args.tf
    require_smt = not args.no_smt
    _cfg = {"15m": (300, 12, 96), "1h": (300, 10, 48), "4h": (150, 5, 12)}
    window, def_cd, max_pending = _cfg.get(tf, (300, 10, 48))
    cooldown = def_cd if args.cooldown < 0 else args.cooldown

    mode = "SMT'li (EKSIKSIZ)" if require_smt else "SMT'siz (saf sniper)"
    print("=" * 72)
    print(f"  FOREVER MODEL [Pro+] (Sniper) — {tf.upper()} — {mode}")
    print(f"  IRL(FVG) + SMT + CISD + CE limit giriş | fee+slip dahil")
    print("=" * 72)
    print(f"\n  {'Sembol':<12} {'n':>4} {'WR%':>6} {'NetR':>8} {'avgR':>7} {'iptal':>6}")
    print("  " + "-" * 50)

    tot = Stats()
    sym_rows = []
    for sym in SYMBOLS:
        res = run_symbol(tf, sym, require_smt, window, cooldown, max_pending, args.ema)
        if res is None:
            print(f"  {sym:<12}  veri yok")
            continue
        stats, trades, _ = res
        dec = stats.wins + stats.losses
        wr  = stats.wins / dec * 100 if dec else 0
        avg = stats.sum_r / dec if dec else 0
        flag = "✅" if stats.sum_r > 0 else "❌"
        print(f"  {sym:<12} {stats.total:>4} {wr:>5.1f}% {stats.sum_r:>+8.2f} "
              f"{avg:>+7.3f} {stats.cancelled:>6} {flag}")
        for t in trades:
            tot.add(t)
        sym_rows.append((sym, stats.sum_r))

    print("  " + "-" * 50)
    dec = tot.wins + tot.losses
    wr  = tot.wins / dec * 100 if dec else 0
    avg = tot.sum_r / dec if dec else 0
    print(f"  {'TOPLAM':<12} {tot.total:>4} {wr:>5.1f}% {tot.sum_r:>+8.2f} "
          f"{avg:>+7.3f} {tot.cancelled:>6}")

    winners = [s for s, r in sym_rows if r > 0]
    print(f"\n  Kazanan semboller: {winners}")
    print(f"  Toplam karar verilen trade: {dec}  | iptal (fill olmadı): {tot.cancelled}")


if __name__ == "__main__":
    main()
