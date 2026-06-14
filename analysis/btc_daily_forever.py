"""
BTC Günlük (1D) — Forever Model [Pro+] (Sniper) backtest.
SMT eşi: ETH. Sadece BTC, sadece günlük.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from backtest_history import Trade, Stats, simulate_trade, normalize_signal
from models.forever_model import ForeverModel

DATA_DIR = Path("data")
FEE_PCT  = 0.05
SLIP_PCT = 0.02
WINDOW   = 80
COOLDOWN = 3


def load(sym: str) -> pd.DataFrame:
    csv = DATA_DIR / f"{sym}_1D_2Y.csv"
    df = pd.read_csv(csv, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    return df


def main():
    btc = load("BTCUSDT")
    eth = load("ETHUSDT")

    # Ortak indeks hizala
    common = btc.index.intersection(eth.index)
    btc = btc.loc[common]
    eth = eth.loc[common]

    model = ForeverModel()
    model.REQUIRE_SMT = True
    model.TP_MODE = "erl"   # karşı ERL = gerçek model gibi

    trades: list[Trade] = []
    open_trades: list[Trade] = []
    last_sig = -10**9
    n = len(btc)

    for i in range(WINDOW, n - 1):
        # Açık trade'leri güncelle
        still = []
        for t in open_trades:
            simulate_trade(btc, t, fee_pct=FEE_PCT, slippage_pct=SLIP_PCT,
                           max_bars_pending=5)
            if t.outcome in ("WIN", "LOSS", "CANCELLED"):
                trades.append(t)
            else:
                still.append(t)
        open_trades = still

        if open_trades or i - last_sig < COOLDOWN:
            continue

        win_btc = btc.iloc[i - WINDOW:i]
        win_eth = eth.iloc[i - WINDOW:i]
        try:
            sig = model.detect(win_btc, win_eth)
        except Exception:
            continue
        if not sig:
            continue

        norm = normalize_signal(sig, min_risk_pct=0.30)
        if not norm:
            continue

        t = Trade(model="forever_1d", direction=norm["direction"],
                  entry=norm["entry"], stop=norm["stop"], tp=norm["tp"],
                  open_idx=i, open_time=btc.index[i])
        open_trades.append(t)
        last_sig = i

    for t in open_trades:
        simulate_trade(btc, t, fee_pct=FEE_PCT, slippage_pct=SLIP_PCT,
                       max_bars_pending=5)
        trades.append(t)

    # ── Rapor ────────────────────────────────────────────────────────────────
    print()
    print("=" * 72)
    print("  BTC GÜNLÜK (1D) — Forever Model [Pro+] Sniper")
    print("  SMT eşi: ETH  |  IRL+SMT+CISD+CE+ERL-TP  |  fee+slip dahil")
    print(f"  Dönem: {btc.index[0]:%Y-%m-%d} → {btc.index[-1]:%Y-%m-%d} ({n} gün)")
    print("=" * 72)

    decided = [t for t in trades if t.outcome in ("WIN", "LOSS")]
    wins    = [t for t in decided if t.outcome == "WIN"]
    losses  = [t for t in decided if t.outcome == "LOSS"]
    open_   = [t for t in trades if t.outcome == "OPEN"]
    cancelled = [t for t in trades if t.outcome == "CANCELLED"]
    net_r   = sum(t.r_multiple for t in decided if t.r_multiple is not None)
    wr      = len(wins) / len(decided) * 100 if decided else 0
    avg_r   = net_r / len(decided) if decided else 0

    print(f"\n  Toplam setup : {len(trades)}")
    print(f"  Karar (W/L)  : {len(wins)}W / {len(losses)}L  |  fill olmadı: {len(cancelled)}")
    print(f"  Win-rate     : {wr:.0f}%")
    print(f"  Net R        : {net_r:+.2f}R")
    print(f"  Ortalama R   : {avg_r:+.3f}R")

    print()
    print(f"  {'#':<3} {'Tarih':<12} {'Yön':<6} {'Giriş':>10} {'SL':>10} {'TP':>10} {'Risk%':>6} {'Sonuç':<10} {'R':>7}")
    print("  " + "-" * 75)

    cur_price = float(btc["close"].iloc[-1])
    for idx, t in enumerate(sorted(trades, key=lambda x: x.open_time), 1):
        risk_pct = abs(t.entry - t.stop) / t.entry * 100
        if t.outcome == "WIN":
            icon = "✅ WIN"
            r_str = f"+{t.r_multiple:.2f}R"
        elif t.outcome == "LOSS":
            icon = "❌ LOSS"
            r_str = f"{t.r_multiple:.2f}R"
        elif t.outcome == "CANCELLED":
            icon = "⛔ CANCEL"
            r_str = "-"
        else:
            icon = "⏳ AÇIK"
            unreal = ((cur_price - t.entry) / abs(t.entry - t.stop)
                      if t.direction == "LONG"
                      else (t.entry - cur_price) / abs(t.entry - t.stop))
            r_str = f"{unreal:+.2f}R*"
        print(f"  {idx:<3} {t.open_time:%Y-%m-%d}  {t.direction:<6} "
              f"{t.entry:>10.2f} {t.stop:>10.2f} {t.tp:>10.2f} "
              f"{risk_pct:>5.2f}%  {icon:<10} {r_str:>7}")

    if open_:
        print(f"\n  * = anlık fiyata göre unrealized R  (BTC şu an: ${cur_price:,.2f})")

    # En son setup özeti
    if trades:
        last = sorted(trades, key=lambda x: x.open_time)[-1]
        risk = abs(last.entry - last.stop)
        print()
        print("  ┌─────────────────────────────────────────────────────────")
        print(f"  │ EN SON SETUP  ({last.open_time:%Y-%m-%d})")
        print(f"  │ Yön      : {last.direction}")
        print(f"  │ Giriş    : ${last.entry:>10,.2f}  (CE — FVG %50)")
        print(f"  │ SL       : ${last.stop:>10,.2f}  (sweep wick + buffer)")
        print(f"  │ TP       : ${last.tp:>10,.2f}  (karşı ERL)")
        print(f"  │ Risk     : ${risk:>,.0f}  ({abs(last.entry-last.stop)/last.entry*100:.2f}%)")
        if last.outcome == "OPEN":
            unreal = ((cur_price - last.entry) / risk if last.direction == "LONG"
                      else (last.entry - cur_price) / risk)
            print(f"  │ Durum    : ⏳ AÇIK  →  ${cur_price:,.2f}  ({unreal:+.2f}R)")
        elif last.outcome == "WIN":
            print(f"  │ Durum    : ✅ KAZANDI  +{last.r_multiple:.2f}R")
        elif last.outcome == "LOSS":
            print(f"  │ Durum    : ❌ KAYBETTİ  {last.r_multiple:.2f}R")
        print("  └─────────────────────────────────────────────────────────")
    print()


if __name__ == "__main__":
    main()
