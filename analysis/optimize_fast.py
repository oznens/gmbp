"""
Hızlı optimizasyon: 4H baseline vs 1H en iyi konfigürasyonları karşılaştır.
1H verisi zaten data/*_1H_1Y.csv'de mevcut.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from backtest_history import run_backtest
from models.ict_models import JUDASSWINGModel, SBSModel, SniperModel

SYMBOLS_ALL  = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "AVAXUSDT",
                "ADAUSDT", "LTCUSDT", "LINKUSDT", "ARBUSDT",
                "XRPUSDT", "DOGEUSDT", "OPUSDT"]
# 4H'ta kaybeden semboller çıkarıldı
SYMBOLS_GOOD = ["AVAXUSDT", "ARBUSDT", "BNBUSDT", "LINKUSDT", "SOLUSDT",
                "DOGEUSDT", "OPUSDT"]

MODELS = {"judas_swing": JUDASSWINGModel, "sbs": SBSModel, "sniper": SniperModel}
DATA_DIR = Path("data")
FEE_PCT  = 0.05
SLIP_PCT = 0.02


def load_dfs(tf: str, syms: list) -> dict:
    dfs = {}
    for sym in syms:
        csv = DATA_DIR / f"{sym}_{tf}_1Y.csv"
        if not csv.exists():
            continue
        df = pd.read_csv(csv, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        dfs[sym] = df
    return dfs


def run_all(dfs, syms, window, cooldown, ema, slope, min_risk, max_pending):
    total_r = 0.0; total_n = total_w = total_l = 0
    per_sym = {}
    for sym in syms:
        df = dfs.get(sym)
        if df is None:
            continue
        _, stats = run_backtest(
            df, MODELS, window=window, cooldown=cooldown,
            fee_pct=FEE_PCT, slippage_pct=SLIP_PCT,
            max_bars_pending=max_pending,
            trend_ema=ema, ema_slope_min=slope, min_risk_pct=min_risk,
        )
        total_r += stats.sum_r
        total_n += stats.total
        total_w += stats.wins
        total_l += stats.losses
        per_sym[sym] = {"r": stats.sum_r, "n": stats.total,
                        "w": stats.wins, "l": stats.losses,
                        "pm": stats.per_model}
    wr  = total_w / (total_w + total_l) * 100 if (total_w + total_l) else 0
    avg = total_r / (total_w + total_l) if (total_w + total_l) else 0
    return total_r, total_n, wr, avg, per_sym


CONFIGS = [
    # Label,  TF,   syms,         window, cd, ema, slope, mr,   pend
    ("4H-baseline",  "4H", "ALL",  150, 10, 20,  0.0, 0.30, 12),
    ("4H-cd5",       "4H", "ALL",  150,  5, 20,  0.0, 0.30, 12),
    ("4H-slope",     "4H", "ALL",  150,  5, 20,  0.2, 0.30, 12),
    ("4H-mr50",      "4H", "ALL",  150,  5, 20,  0.0, 0.50, 12),
    ("4H-GOOD",      "4H", "GOOD", 150,  5, 20,  0.0, 0.30, 12),
    ("4H-GOOD-slope","4H", "GOOD", 150,  5, 20,  0.2, 0.50, 12),
    ("1H-cd20",      "1H", "ALL",  300, 20, 20,  0.0, 0.30, 48),
    ("1H-cd10",      "1H", "ALL",  300, 10, 20,  0.0, 0.30, 48),
    ("1H-ema50",     "1H", "ALL",  300, 10, 50,  0.0, 0.30, 48),
    ("1H-slope",     "1H", "ALL",  300, 10, 20,  0.2, 0.30, 48),
    ("1H-mr50",      "1H", "ALL",  300, 10, 20,  0.0, 0.50, 48),
    ("1H-GOOD",      "1H", "GOOD", 300, 10, 20,  0.0, 0.30, 48),
    ("1H-GOOD-ema50","1H", "GOOD", 300, 10, 50,  0.0, 0.30, 48),
    ("1H-GOOD-slope","1H", "GOOD", 300, 10, 20,  0.2, 0.30, 48),
    ("1H-GOOD-mr50", "1H", "GOOD", 300, 10, 20,  0.0, 0.50, 48),
    ("1H-BEST",      "1H", "GOOD", 300,  8, 20,  0.2, 0.50, 48),
]

dfs_4h = load_dfs("4H", SYMBOLS_ALL)
dfs_1h = load_dfs("1H", SYMBOLS_ALL)

print(f"{'Konfigürasyon':<22} {'NetR':>8} {'n':>5} {'WR%':>6} {'avgR':>7}")
print("-" * 55)

results = []
for label, tf, sym_set, window, cd, ema, slope, mr, pend in CONFIGS:
    dfs  = dfs_4h if tf == "4H" else dfs_1h
    syms = SYMBOLS_ALL if sym_set == "ALL" else SYMBOLS_GOOD
    r, n, wr, avg, per_sym = run_all(dfs, syms, window, cd, ema, slope, mr, pend)
    results.append((label, r, n, wr, avg, per_sym))
    flag = "★" if r > 100 else ("✅" if r > 0 else "❌")
    print(f"{label:<22} {r:>+8.2f} {n:>5} {wr:>5.1f}% {avg:>+7.3f}  {flag}")

print("\n" + "=" * 55)
best = max(results, key=lambda x: x[1])
label, r, n, wr, avg, per_sym = best
print(f"\nEN İYİ: {label}  →  {r:+.2f}R  (n={n}, WR={wr:.1f}%, avgR={avg:+.3f})")

print(f"\nSembol detayı ({label}):")
print(f"  {'Sembol':<12} {'n':>5} {'NetR':>8}  Model dağılımı")
for sym, s in sorted(per_sym.items(), key=lambda x: x[1]["r"], reverse=True):
    dec = s["w"] + s["l"]
    wr_s = s["w"] / dec * 100 if dec else 0
    model_str = "  ".join(
        f"{k}:{v['n']}({v['r']:+.1f}R)" for k, v in sorted(s["pm"].items())
    )
    flag = "✅" if s["r"] > 0 else "❌"
    print(f"  {sym:<12} {s['n']:>5} {s['r']:>+8.2f}  {model_str}  {flag}")

print(f"\nModel bazında (tüm semboller, {label}):")
total_pm: dict = {}
for s in per_sym.values():
    for k, v in s["pm"].items():
        b = total_pm.setdefault(k, {"n": 0, "w": 0, "l": 0, "r": 0.0})
        b["n"] += v["n"]; b["w"] += v["w"]
        b["l"] += v["l"]; b["r"] += v["r"]
for k, v in sorted(total_pm.items()):
    dec = v["w"] + v["l"]
    wr_m = v["w"] / dec * 100 if dec else 0
    avg_m = v["r"] / dec if dec else 0
    print(f"  {k:<18} n={v['n']:>4}  WR={wr_m:>5.1f}%  sumR={v['r']:>+8.2f}  avgR={avg_m:>+6.3f}")
