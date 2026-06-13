"""
BTC 1H — Son günlerdeki Sniper (Forever Model) sinyallerini simüle et ve göster.
Her sinyal bar'ında: entry, SL, TP ve sonucu (WIN/LOSS/OPEN) yazdır.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from models.ict_models import SniperModel

DATA_DIR = Path("data")

def simulate_signal(df: pd.DataFrame, sig: dict, open_idx: int) -> dict:
    """Sinyal bar'ından sonra SL/TP'ye hangisinin önce vurulduğunu simüle et."""
    entry = sig["entry"]
    sl    = sig["stop"]
    tp    = sig["tp"]
    direction = sig["direction"]

    for j in range(open_idx + 1, len(df)):
        hi = df["high"].iloc[j]
        lo = df["low"].iloc[j]

        if direction == "LONG":
            if lo <= sl and hi >= tp:
                return {"outcome": "LOSS", "bars": j - open_idx, "exit": sl}
            elif lo <= sl:
                return {"outcome": "LOSS", "bars": j - open_idx, "exit": sl}
            elif hi >= tp:
                return {"outcome": "WIN",  "bars": j - open_idx, "exit": tp}
        else:
            if hi >= sl and lo <= tp:
                return {"outcome": "LOSS", "bars": j - open_idx, "exit": sl}
            elif hi >= sl:
                return {"outcome": "LOSS", "bars": j - open_idx, "exit": sl}
            elif lo <= tp:
                return {"outcome": "WIN",  "bars": j - open_idx, "exit": tp}

    return {"outcome": "OPEN", "bars": len(df) - open_idx, "exit": None}


def run_demo(symbol: str = "BTCUSDT", tf: str = "1H"):
    csv = DATA_DIR / f"{symbol}_{tf}_1Y.csv"
    if not csv.exists():
        print(f"CSV bulunamadı: {csv}")
        return

    df = pd.read_csv(csv, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]

    model = SniperModel()
    WINDOW    = 80
    EMA_SPAN  = 20    # trend filtresi
    MIN_RISK  = 0.30  # min risk %
    COOLDOWN  = 6     # aynı yönde minimum 6 bar bekleme (1H × 6 = 6 saat)

    ema = df["close"].ewm(span=EMA_SPAN, adjust=False).mean().values
    signals = []
    last_signal_idx = -999

    # Son 30 günü tara (1H: 720 bar)
    start_idx = max(WINDOW, len(df) - 720)

    for i in range(start_idx, len(df)):
        # Cooldown kontrolü
        if i - last_signal_idx < COOLDOWN:
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

        # Min risk filtresi
        if risk_pct < MIN_RISK:
            continue

        # EMA trend filtresi
        close_now = float(df["close"].iloc[i])
        if sig["direction"] == "LONG" and close_now < ema[i]:
            continue
        if sig["direction"] == "SHORT" and close_now > ema[i]:
            continue

        result = simulate_signal(df, sig, i)
        r_mult = ((result["exit"] - sig["entry"]) if sig["direction"] == "LONG"
                  else (sig["entry"] - result["exit"])) / risk if result["exit"] else None

        signals.append({
            "time": df.index[i],
            "direction": sig["direction"],
            "entry": sig["entry"],
            "stop": sig["stop"],
            "tp": sig["tp"],
            "risk_pct": risk_pct,
            **result,
            "r_mult": round(r_mult, 2) if r_mult is not None else None,
        })
        last_signal_idx = i

    print(f"\n{'='*75}")
    print(f"  ICT Sniper (Forever Model) — {symbol} @ {tf}")
    print(f"  Dönem: {df.index[start_idx]:%Y-%m-%d %H:%M}  →  {df.index[-1]:%Y-%m-%d %H:%M}")
    print(f"  Toplam sinyal: {len(signals)}")
    print(f"{'='*75}")

    if not signals:
        print("  Bu dönemde sinyal üretilmedi.")
        return

    wins   = [s for s in signals if s["outcome"] == "WIN"]
    losses = [s for s in signals if s["outcome"] == "LOSS"]
    opens  = [s for s in signals if s["outcome"] == "OPEN"]
    decided = wins + losses
    wr = len(wins) / len(decided) * 100 if decided else 0
    net_r = sum(s["r_mult"] for s in decided if s["r_mult"])

    print(f"\n  WR: {wr:.0f}%  |  NetR: {net_r:+.2f}R  |  "
          f"WIN={len(wins)} LOSS={len(losses)} OPEN={len(opens)}")
    print()

    print(f"  {'Tarih':<18} {'Yon':<6} {'Giriş':>10} {'SL':>10} {'TP':>10} "
          f"{'Risk%':>6} {'Sonuç':<7} {'R':>6}  {'Bar'}")
    print(f"  {'-'*80}")

    for s in signals:
        outcome_icon = "✅" if s["outcome"] == "WIN" else ("❌" if s["outcome"] == "LOSS" else "⏳")
        r_str = f"{s['r_mult']:+.2f}R" if s["r_mult"] is not None else "  -  "
        print(f"  {s['time']:%Y-%m-%d %H:%M}  {s['direction']:<6} "
              f"{s['entry']:>10.2f} {s['stop']:>10.2f} {s['tp']:>10.2f} "
              f"{s['risk_pct']:>5.2f}%  {outcome_icon}{s['outcome']:<5}  {r_str}  "
              f"+{s['bars']}h")

    # Son 3 sinyali detaylıca açıkla
    print(f"\n{'─'*75}")
    print("  SON SİNYALLERİN AÇIKLAMASI:")
    for s in signals[-3:]:
        print(f"\n  [{s['time']:%d %b %H:%M}]  {s['direction']} @ {s['entry']:.2f}")
        print(f"    ↳ Swing sweep sonrası güçlü deplasman mumı")
        print(f"    ↳ SL = {s['stop']:.2f}  (sweep wick altı, risk={s['risk_pct']:.2f}%)")
        print(f"    ↳ TP = {s['tp']:.2f}  (2.5R)")
        if s['outcome'] == "WIN":
            print(f"    ↳ ✅ {s['bars']} saat sonra TP'ye ulaştı  → {s['r_mult']:+.2f}R")
        elif s['outcome'] == "LOSS":
            print(f"    ↳ ❌ {s['bars']} saat sonra SL'ye çarptı  → {s['r_mult']:+.2f}R")
        else:
            print(f"    ↳ ⏳ Hâlâ açık ({s['bars']} saattir)")


if __name__ == "__main__":
    run_demo("BTCUSDT", "1H")
