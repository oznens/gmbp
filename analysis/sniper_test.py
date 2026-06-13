"""
Sniper Model — 1 yillik 4H backtest (12 sembol).
Min-risk filtresi aktif (backtest_history.normalize_signal icinde).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from backtest_history import run_backtest, Stats
from models.ict_models import SniperModel, JUDASSWINGModel, SBSModel

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "AVAXUSDT",
    "ADAUSDT", "DOTUSDT", "LTCUSDT", "LINKUSDT", "ARBUSDT",
    "MATICUSDT", "XRPUSDT",
]

MODELS = {
    "sniper": SniperModel,
    "judas_swing": JUDASSWINGModel,
    "sbs": SBSModel,
}

FEE_PCT      = 0.05   # %0.05 taker
SLIP_PCT     = 0.02   # %0.02 slippage + funding
TREND_EMA    = 20
MIN_BARS_PENDING = 12  # 4H × 12 = 2 gün bekleme limiti
WINDOW       = 200
COOLDOWN     = 10

print(f"{'Sembol':<12} {'n':>5} {'WR%':>6} {'NetR':>8} {'avgR':>7}  model dagilimi")
print("-" * 70)

total_stats = Stats()

for sym in SYMBOLS:
    path = os.path.join(DATA_DIR, f"{sym}_4H_1Y.csv")
    if not os.path.exists(path):
        print(f"{sym:<12}  veri yok")
        continue
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]

    trades, stats = run_backtest(
        df, MODELS,
        window=WINDOW,
        cooldown=COOLDOWN,
        fee_pct=FEE_PCT,
        slippage_pct=SLIP_PCT,
        max_bars_pending=MIN_BARS_PENDING,
        trend_ema=TREND_EMA,
    )

    if stats.total == 0:
        print(f"{sym:<12}  sinyal yok (cancelled={stats.cancelled})")
        continue

    decided = stats.wins + stats.losses
    wr  = stats.wins / decided * 100 if decided else 0
    avg = stats.sum_r / decided if decided else 0

    model_line = "  ".join(
        f"{k}:{v['n']}({v['r']:+.1f}R)" for k, v in sorted(stats.per_model.items())
    )
    print(f"{sym:<12} {stats.total:>5d} {wr:>5.1f}% {stats.sum_r:>+8.2f} {avg:>+7.3f}  {model_line}")

    for t in trades:
        total_stats.add(t)

print("-" * 70)
decided_t = total_stats.wins + total_stats.losses
wr_t  = total_stats.wins / decided_t * 100 if decided_t else 0
avg_t = total_stats.sum_r / decided_t if decided_t else 0
print(f"{'TOPLAM':<12} {total_stats.total:>5d} {wr_t:>5.1f}% {total_stats.sum_r:>+8.2f} {avg_t:>+7.3f}")
print()

# Model bazında özet
print("Model bazında (tüm semboller):")
for k, v in sorted(total_stats.per_model.items()):
    dec = v["w"] + v["l"]
    wr_m = v["w"] / dec * 100 if dec else 0
    avg_m = v["r"] / dec if dec else 0
    print(f"  {k:<18} n={v['n']:>4d}  WR={wr_m:>5.1f}%  sumR={v['r']:>+8.2f}  avgR={avg_m:>+6.3f}")
