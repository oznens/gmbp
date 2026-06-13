"""
BTC GÜNLÜK (1D) — En son Sniper (Forever Model) setup'ını göster.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from utils.mexc_fetcher import MEXCFetcher
from models.ict_models import SniperModel

DATA_DIR = Path("data")


def simulate(df, sig, idx):
    e, sl, tp, d = sig["entry"], sig["stop"], sig["tp"], sig["direction"]
    for j in range(idx + 1, len(df)):
        hi, lo = df["high"].iloc[j], df["low"].iloc[j]
        if d == "LONG":
            if lo <= sl: return {"outcome": "LOSS", "bars": j - idx, "exit": sl}
            if hi >= tp: return {"outcome": "WIN",  "bars": j - idx, "exit": tp}
        else:
            if hi >= sl: return {"outcome": "LOSS", "bars": j - idx, "exit": sl}
            if lo <= tp: return {"outcome": "WIN",  "bars": j - idx, "exit": tp}
    return {"outcome": "OPEN", "bars": len(df) - idx, "exit": None}


def main():
    csv = DATA_DIR / "BTCUSDT_1D_2Y.csv"
    if csv.exists():
        df = pd.read_csv(csv, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        print(f"BTC 1D: CSV'den ({len(df)} bar)")
    else:
        print("BTC 1D indiriliyor...")
        df = MEXCFetcher().fetch_ohlcv("BTCUSDT", "1d", limit=730)
        df.columns = [c.lower() for c in df.columns]
        df.to_csv(csv)
        print(f"  {len(df)} bar kaydedildi")

    model = SniperModel()
    WINDOW = 80
    # Günlük TF doğal olarak yüksek kaliteli — sadece min-risk filtresi
    # (EMA trend filtresi günlükte sweep barı anlık deldiği için elemeli)

    signals = []
    last_idx = -999
    for i in range(WINDOW, len(df)):
        if i - last_idx < 3:
            continue
        view = df.iloc[i - WINDOW:i].copy().reset_index(drop=True)
        try:
            sig = model.detect(view)
        except Exception:
            continue
        if sig is None:
            continue
        risk = abs(sig["entry"] - sig["stop"])
        risk_pct = risk / sig["entry"] * 100
        if risk_pct < 0.30:
            continue
        res = simulate(df, sig, i)
        r = (((res["exit"] - sig["entry"]) if sig["direction"] == "LONG"
              else (sig["entry"] - res["exit"])) / risk) if res["exit"] else None
        signals.append({"time": df.index[i], "i": i, "risk_pct": risk_pct,
                        "r": round(r, 2) if r is not None else None, **sig, **res})
        last_idx = i

    print(f"\n{'='*72}")
    print(f"  BTC GÜNLÜK (1D) — Sniper / Forever Model")
    print(f"  Veri: {df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}  ({len(df)} gün)")
    print(f"  Toplam günlük setup: {len(signals)}")
    print(f"{'='*72}\n")

    if not signals:
        print("  Günlük TF'de filtreli setup bulunamadı.")
        # Mevcut son bar durumu
        print(f"\n  Son kapanış: {df['close'].iloc[-1]:.2f}  ({df.index[-1]:%Y-%m-%d})")
        return

    # Tüm setupları listele
    wins = sum(1 for s in signals if s["outcome"] == "WIN")
    losses = sum(1 for s in signals if s["outcome"] == "LOSS")
    net_r = sum(s["r"] for s in signals if s["r"] is not None)
    wr = wins / (wins + losses) * 100 if (wins + losses) else 0
    print(f"  Geçmiş performans: WR={wr:.0f}%  NetR={net_r:+.2f}R  "
          f"(W={wins} L={losses})\n")

    print(f"  {'Tarih':<12} {'Yön':<6} {'Giriş':>11} {'SL':>11} {'TP':>11} "
          f"{'Risk%':>6} {'Sonuç':<6} {'R':>7}")
    print(f"  {'-'*75}")
    for s in signals:
        icon = "✅" if s["outcome"] == "WIN" else ("❌" if s["outcome"] == "LOSS" else "⏳")
        rs = f"{s['r']:+.2f}R" if s["r"] is not None else "  -  "
        print(f"  {s['time']:%Y-%m-%d}  {s['direction']:<6} {s['entry']:>11.2f} "
              f"{s['stop']:>11.2f} {s['tp']:>11.2f} {s['risk_pct']:>5.2f}% "
              f"{icon}{s['outcome']:<5} {rs:>7}")

    # EN SON SETUP detayı
    last = signals[-1]
    print(f"\n{'═'*72}")
    print(f"  ★ EN SON GÜNLÜK SETUP")
    print(f"{'═'*72}")
    print(f"    Tarih      : {last['time']:%Y-%m-%d}")
    print(f"    Yön        : {last['direction']}")
    print(f"    Giriş      : ${last['entry']:,.2f}")
    print(f"    Stop-Loss  : ${last['stop']:,.2f}   (risk {last['risk_pct']:.2f}%)")
    print(f"    Take-Profit: ${last['tp']:,.2f}   (2.5R)")
    rr_dollar = abs(last['tp'] - last['entry'])
    risk_dollar = abs(last['entry'] - last['stop'])
    print(f"    R:R        : 1 : 2.5  (risk ${risk_dollar:,.0f} → ödül ${rr_dollar:,.0f})")
    if last["outcome"] == "OPEN":
        print(f"    Durum      : ⏳ AÇIK ({last['bars']} gündür sürüyor)")
        cur = df['close'].iloc[-1]
        if last["direction"] == "LONG":
            unreal = (cur - last['entry']) / risk_dollar
        else:
            unreal = (last['entry'] - cur) / risk_dollar
        print(f"    Güncel fiyat: ${cur:,.2f}  →  realize olmamış {unreal:+.2f}R")
    elif last["outcome"] == "WIN":
        print(f"    Durum      : ✅ KAZANDI ({last['bars']} gün sonra TP) → +2.50R")
    else:
        print(f"    Durum      : ❌ KAYBETTİ ({last['bars']} gün sonra SL) → -1.00R")
    print()


if __name__ == "__main__":
    main()
