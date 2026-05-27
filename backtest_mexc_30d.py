"""Paper-trade default ayarlariyla son N gunluk MEXC backtest ozeti.

4 sembol (BTC/ETH/SOL/XRP) × judas_swing+sbs × 4h, son 30 gunde KAPANAN
trade'leri filtreleyip birlesik rapor ucretir.  Stats hem 30 gunluk dilim
hem tum donem icin verilir.
"""
from __future__ import annotations
import sys, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils.mexc_fetcher import MEXCFetcher
from backtest_history import run_backtest, MODELS

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
MODELS_SEL = {k: MODELS[k] for k in ("judas_swing", "sbs")}
TF = "4h"
LIMIT = 500           # ~83 gun veri, window=200 sonrasi ~300 bar etkin
WINDOW = 200
COOLDOWN = 5
LOOKBACK_DAYS = 30
RISK_PER_TRADE_USDT = 100.0   # bakiye 5000 * %2

print(f"\n{'='*78}")
print(f"  MEXC backtest -- son {LOOKBACK_DAYS} gun")
print(f"  Modeller: {', '.join(MODELS_SEL)}  TF: {TF}  Risk/trade: ${RISK_PER_TRADE_USDT:.0f}")
print(f"{'='*78}\n")

fetcher = MEXCFetcher()
cutoff = dt.datetime.utcnow() - dt.timedelta(days=LOOKBACK_DAYS)

all_recent = []   # (symbol, trade)
all_full = []     # (symbol, trade)
symbol_summary = []

for sym in SYMBOLS:
    df = fetcher.fetch_ohlcv(sym, TF, limit=LIMIT)
    if df is None or len(df) < WINDOW + 50:
        print(f"  {sym}: veri yetersiz")
        continue
    trades, _ = run_backtest(df, MODELS_SEL, window=WINDOW, cooldown=COOLDOWN,
                             max_concurrent=1, fee_pct=0.05, slippage_pct=0.02)
    closed = [t for t in trades if t.outcome in ("WIN", "LOSS")]
    recent = [t for t in closed if t.close_time and t.close_time.replace(tzinfo=None) >= cutoff]
    all_full.extend((sym, t) for t in closed)
    all_recent.extend((sym, t) for t in recent)
    r_full = sum(t.r_multiple for t in closed)
    r_recent = sum(t.r_multiple for t in recent)
    w_recent = sum(1 for t in recent if t.outcome == "WIN")
    wr = (w_recent / len(recent) * 100) if recent else 0.0
    symbol_summary.append({
        "sym": sym, "n_full": len(closed), "r_full": r_full,
        "n_recent": len(recent), "w_recent": w_recent,
        "wr_recent": wr, "r_recent": r_recent,
        "data_from": df.index[0], "data_to": df.index[-1],
    })

print(f"  Sembol bazinda ({LOOKBACK_DAYS} gun):")
print(f"  {'sym':<10s}{'n':>4s}{'W':>4s}{'WR%':>7s}{'sumR':>9s}{'PnL$':>10s}")
for s in symbol_summary:
    pnl = s["r_recent"] * RISK_PER_TRADE_USDT
    print(f"  {s['sym']:<10s}{s['n_recent']:>4d}{s['w_recent']:>4d}"
          f"{s['wr_recent']:>6.1f} {s['r_recent']:>+8.2f}{pnl:>+10.2f}")

print()
total_n = len(all_recent)
total_w = sum(1 for _, t in all_recent if t.outcome == "WIN")
total_r = sum(t.r_multiple for _, t in all_recent)
total_wr = (total_w / total_n * 100) if total_n else 0.0
print(f"  TOPLAM ({LOOKBACK_DAYS}g) : n={total_n}  W={total_w}  WR=%{total_wr:.1f}  "
      f"R={total_r:+.2f}  PnL=${total_r * RISK_PER_TRADE_USDT:+.2f}")

# Per-model breakdown (son 30g)
per_model = {}
for sym, t in all_recent:
    d = per_model.setdefault(t.model, {"n": 0, "w": 0, "r": 0.0})
    d["n"] += 1
    if t.outcome == "WIN": d["w"] += 1
    d["r"] += t.r_multiple

print(f"\n  Model bazinda ({LOOKBACK_DAYS} gun):")
print(f"  {'model':<16s}{'n':>4s}{'W':>4s}{'WR%':>7s}{'sumR':>9s}")
for m, d in sorted(per_model.items()):
    wr = (d["w"] / d["n"] * 100) if d["n"] else 0.0
    print(f"  {m:<16s}{d['n']:>4d}{d['w']:>4d}{wr:>6.1f} {d['r']:>+8.2f}")

# Tum trade listesi (son 30g, tarih sirali)
print(f"\n  Trade listesi ({LOOKBACK_DAYS}g):")
print(f"  {'tarih':<12s}{'sembol':<10s}{'model':<14s}{'yon':<6s}"
      f"{'entry':>10s}{'exit':>10s}{'R':>7s}")
recent_sorted = sorted(all_recent, key=lambda x: x[1].close_time)
for sym, t in recent_sorted:
    mark = "✅" if t.outcome == "WIN" else "❌"
    print(f"  {t.close_time:%m-%d %H:%M}  {sym:<10s}{t.model:<14s}{t.direction:<6s}"
          f"{t.entry:>10.4f}{t.exit_price:>10.4f}{t.r_multiple:>+7.2f}  {mark}")

# Tum donem ozeti karsilastirma
full_n = len(all_full)
full_w = sum(1 for _, t in all_full if t.outcome == "WIN")
full_r = sum(t.r_multiple for _, t in all_full)
full_wr = (full_w / full_n * 100) if full_n else 0.0
data_span = (symbol_summary[0]["data_to"] - symbol_summary[0]["data_from"]).days if symbol_summary else 0
print(f"\n  Karsilastirma (tum donem ~{data_span}g): n={full_n} W={full_w} "
      f"WR=%{full_wr:.1f} R={full_r:+.2f}")
print()
