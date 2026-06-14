"""
Harmonik Pattern — Çok-TF derin analiz (15m + 1H + 4H).
harmonic_deep.py makinesini her TF için mevcut CSV'lerle çalıştırır.

Amaç: harmonik öze dönüş — hangi pattern + hangi puan eşiği + hangi PA onayı
kârlı? Puanlama sistemini gerçek veriyle kalibre et.

Çalıştırma:
  python analysis/harmonic_multitf.py
  python analysis/harmonic_multitf.py --tf 15m
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

import analysis.harmonic_deep as hd
from analysis.harmonic_deep import analyze, build_report

DATA_DIR = Path("data")
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
    "BNBUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT",
    "OPUSDT", "ARBUSDT", "LTCUSDT", "ADAUSDT",
]

# TF → (csv eki, kayan-pencere boyu, D-yaşı toleransı, max-pending)
TF_CFG = {
    "15m": ("15M_1Y", 400, 12, 96),
    "1h":  ("1H_1Y",  350, 10, 48),
    "4h":  ("4H_1Y",  300,  8, 12),
}


def load_csv(sym: str, suffix: str) -> pd.DataFrame | None:
    csv = DATA_DIR / f"{sym}_{suffix}.csv"
    if not csv.exists():
        return None
    df = pd.read_csv(csv, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    return df


def run_tf(tf: str) -> list[dict]:
    suffix, window, max_d, max_pending = TF_CFG[tf]
    # harmonic_deep global ayarlarını bu TF'e göre düzenle
    hd.MAX_D_BARS = max_d
    # analyze içindeki window sabit 300 — monkeypatch ile değiştir
    records_all = []
    print(f"\n{'='*60}\n  TF = {tf}  (pencere={window}, D-yaşı≤{max_d})\n{'='*60}")
    for sym in SYMBOLS:
        df = load_csv(sym, suffix)
        if df is None:
            print(f"  {sym}: veri yok")
            continue
        recs = _analyze_tf(df, sym, window, max_pending)
        w = sum(1 for r in recs if r["outcome"] == "WIN")
        l = sum(1 for r in recs if r["outcome"] == "LOSS")
        c = sum(1 for r in recs if r["outcome"] == "CANCELLED")
        nr = sum(r["r_multiple"] for r in recs
                 if r["r_multiple"] is not None and r["outcome"] in ("WIN", "LOSS"))
        for r in recs:
            r["tf"] = tf
        records_all.extend(recs)
        print(f"  {sym:<10} {len(recs):>4} sinyal | {w}W/{l}L/{c}iptal | NetR={nr:+.2f}")
    return records_all


def _analyze_tf(df, sym, window, max_pending):
    """harmonic_deep.analyze'in TF-parametrik kopyası (window + max_pending)."""
    ema    = df["close"].ewm(span=hd.EMA_PERIOD, adjust=False).mean().values
    vol    = df["volume"].values if "volume" in df.columns else np.ones(len(df))
    vol_ma = pd.Series(vol).rolling(20).mean().values

    from models.harmonics import detect_harmonics
    from models.price_action import confirm as pa_confirm

    records, seen_d = [], set()
    step = 3 if window <= 350 else 4

    for i in range(window, len(df) - 1, step):
        view = df.iloc[i - window:i + 1].reset_index(drop=True)
        try:
            signals = detect_harmonics(view, depth=hd.ZIGZAG_DEPTH, min_score=hd.MIN_SCORE)
        except Exception:
            continue
        for h in signals:
            g_d = (i - window) + h.d_index
            key = (g_d, h.pattern, h.direction)
            if key in seen_d or i - g_d > hd.MAX_D_BARS:
                continue
            seen_d.add(key)

            prz_margin = h.prz_high - h.prz_low
            last = view.iloc[-1]
            if h.direction == "bullish":
                touched = last["low"] <= h.prz_high + prz_margin
            else:
                touched = last["high"] >= h.prz_low - prz_margin
            if not touched:
                continue

            try:
                pa = pa_confirm(view, h.direction)
                pa_confs = pa.confirmations
            except Exception:
                pa_confs = []
            if not pa_confs:
                continue

            direction = "LONG" if h.direction == "bullish" else "SHORT"
            cd = abs(h.D - h.C)
            if direction == "LONG":
                sl  = min(h.D, float(last["low"])) * (1 - hd.SL_BUFFER)
                tp2 = h.D + cd * 0.618
            else:
                sl  = max(h.D, float(last["high"])) * (1 + hd.SL_BUFFER)
                tp2 = h.D - cd * 0.618

            entry = float(last["close"])
            risk  = abs(entry - sl)
            if risk <= 0:
                continue
            # min risk filtresi (fee koruması)
            if risk / entry * 100 < 0.30:
                continue
            rr2 = abs(tp2 - entry) / risk
            if rr2 < 1.5:
                continue

            trend_ok = (direction == "LONG" and entry > ema[i]) or \
                       (direction == "SHORT" and entry < ema[i])
            vr = float(vol[i] / vol_ma[i]) if vol_ma[i] > 0 else 1.0
            conf_score = hd.score_signal(h, pa_confs, trend_ok, vr)

            result = hd.simulate_trade(df, i, direction, entry, sl, tp2,
                                       max_pending=max_pending)
            records.append({
                "symbol": sym, "pattern": h.pattern, "direction": direction,
                "open_time": str(df.index[i]), "entry": round(entry, 6),
                "stop": round(sl, 6), "tp2": round(tp2, 6), "rr": round(rr2, 2),
                "fib_score": h.score, "pa_confs": pa_confs, "trend_ok": trend_ok,
                "vol_ratio": round(vr, 2), "conf_score": conf_score,
                "outcome": result["outcome"], "r_multiple": result["r_multiple"],
                "bars_to_fill": result["bars_to_fill"],
            })
    return records


def summarize(records: list[dict], tf_label: str):
    df = pd.DataFrame(records)
    if df.empty:
        print(f"\n[{tf_label}] kayıt yok")
        return
    closed = df[df["outcome"].isin(["WIN", "LOSS"])].copy()
    if closed.empty:
        print(f"\n[{tf_label}] kapalı trade yok ({len(df)} sinyal, hepsi açık/iptal)")
        return

    n  = len(closed)
    w  = (closed["outcome"] == "WIN").sum()
    wr = w / n * 100
    nr = closed["r_multiple"].sum()
    print(f"\n┌─ {tf_label} ÖZET ─ n={n}  WR={wr:.1f}%  NetR={nr:+.2f}R  avgR={nr/n:+.3f}")

    # Pattern bazlı
    print("│  Pattern    n    WR     NetR")
    for pat in sorted(closed["pattern"].unique()):
        sub = closed[closed["pattern"] == pat]
        sw  = (sub["outcome"] == "WIN").sum()
        print(f"│   {pat:<9} {len(sub):>3}  {sw/len(sub)*100:>4.0f}%  {sub['r_multiple'].sum():>+7.2f}")

    # Skor eşiği — kârlı kesim
    print("│  Skor≥    n    WR     NetR   avgR")
    best_t, best_r = 0, nr
    for t in range(30, 90, 10):
        sub = closed[closed["conf_score"] >= t]
        if len(sub) < 3:
            continue
        sw = (sub["outcome"] == "WIN").sum()
        sr = sub["r_multiple"].sum()
        if sr > best_r:
            best_r, best_t = sr, t
        print(f"│   ≥{t:<5} {len(sub):>3}  {sw/len(sub)*100:>4.0f}%  {sr:>+7.2f}  {sr/len(sub):+.3f}")
    print(f"└─ En iyi eşik: ≥{best_t} → {best_r:+.2f}R")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="all", help="15m / 1h / 4h / all")
    args = ap.parse_args()

    tfs = ["15m", "1h", "4h"] if args.tf == "all" else [args.tf]
    grand = []
    for tf in tfs:
        recs = run_tf(tf)
        summarize(recs, tf.upper())
        grand.extend(recs)

    # Birleşik JSON + HTML
    import json
    Path("analysis").mkdir(exist_ok=True)
    Path("analysis/harmonic_multitf.json").write_text(
        json.dumps(grand, indent=2, default=str))
    from datetime import datetime, timezone
    html = build_report(grand, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))
    Path("docs").mkdir(exist_ok=True)
    Path("docs/harmonic_multitf.html").write_text(html, encoding="utf-8")
    print(f"\n→ analysis/harmonic_multitf.json  ({len(grand)} kayıt)")
    print(f"→ docs/harmonic_multitf.html")


if __name__ == "__main__":
    main()
