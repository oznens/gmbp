"""
Kapsamlı optimizasyon:
  1. 1H veriyi MEXCFetcher ile çek ve data/*.csv'ye kaydet
  2. 4H ve 1H için parametre grid-search yap
  3. En iyi kombinasyonu bul ve raporla

Hedef: 100R+
"""
from __future__ import annotations
import sys, os, time
from pathlib import Path
from itertools import product

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from utils.mexc_fetcher import MEXCFetcher
from backtest_history import run_backtest
from models.ict_models import JUDASSWINGModel, SBSModel, SniperModel

SYMBOLS_ALL = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "AVAXUSDT",
    "ADAUSDT", "LTCUSDT", "LINKUSDT", "ARBUSDT",
    "XRPUSDT", "DOGEUSDT", "OPUSDT",
]

# Sadece 4H testinde kazanan semboller
SYMBOLS_GOOD = ["AVAXUSDT", "ARBUSDT", "BNBUSDT", "LINKUSDT", "SOLUSDT",
                "DOGEUSDT", "OPUSDT"]

MODELS = {"judas_swing": JUDASSWINGModel, "sbs": SBSModel, "sniper": SniperModel}
DATA_DIR = Path("data")
FEE_PCT  = 0.05
SLIP_PCT = 0.02


# ── 1H Veri İndirme ──────────────────────────────────────────────────────────

def download_1h(symbols: list[str], bars: int = 8800) -> dict[str, pd.DataFrame]:
    """1H OHLCV verisi indir; zaten varsa CSV'den yükle."""
    fetcher = MEXCFetcher()
    dfs = {}
    for sym in symbols:
        csv = DATA_DIR / f"{sym}_1H_1Y.csv"
        if csv.exists():
            df = pd.read_csv(csv, index_col=0, parse_dates=True)
            df.columns = [c.lower() for c in df.columns]
            print(f"  {sym} 1H: CSV'den yüklendi ({len(df)} bar)")
            dfs[sym] = df
            continue
        print(f"  {sym} 1H: indiriliyor...", end="", flush=True)
        df = fetcher.fetch_ohlcv(sym, "1h", limit=bars)
        if df is None or len(df) < 500:
            print(" HATA (atlandı)")
            continue
        df.columns = [c.lower() for c in df.columns]
        df.to_csv(csv)
        print(f" {len(df)} bar kaydedildi")
        dfs[sym] = df
        time.sleep(0.3)
    return dfs


# ── Backtest Runner ───────────────────────────────────────────────────────────

def run_sym_set(dfs: dict, symbols: list, cooldown: int, ema: int,
                slope: float, min_risk: float, window: int, max_pending: int):
    total_r = 0.0
    total_n = total_w = total_l = 0
    for sym in symbols:
        df = dfs.get(sym)
        if df is None:
            continue
        _, stats = run_backtest(
            df, MODELS,
            window=window, cooldown=cooldown,
            fee_pct=FEE_PCT, slippage_pct=SLIP_PCT,
            max_bars_pending=max_pending,
            trend_ema=ema,
            ema_slope_min=slope,
            min_risk_pct=min_risk,
        )
        total_r += stats.sum_r
        total_n += stats.total
        total_w += stats.wins
        total_l += stats.losses
    wr = total_w / (total_w + total_l) * 100 if (total_w + total_l) else 0
    avg = total_r / (total_w + total_l) if (total_w + total_l) else 0
    return total_r, total_n, wr, avg


def main():
    print("=" * 70)
    print("KAPSAMLI OPTİMİZASYON — Hedef 100R+")
    print("=" * 70)

    # ── 1. 1H Veri İndirme ───────────────────────────────────────────────────
    print("\n[1/3] 1H veri indiriliyor / yükleniyor...")
    dfs_1h = download_1h(SYMBOLS_ALL, bars=8800)
    dfs_4h = {}
    for sym in SYMBOLS_ALL:
        csv = DATA_DIR / f"{sym}_4H_1Y.csv"
        if csv.exists():
            df = pd.read_csv(csv, index_col=0, parse_dates=True)
            df.columns = [c.lower() for c in df.columns]
            dfs_4h[sym] = df

    print(f"  4H: {len(dfs_4h)} sembol  |  1H: {len(dfs_1h)} sembol")

    # ── 2. Parametre Grid-Search ──────────────────────────────────────────────
    print("\n[2/3] Grid-Search başlıyor...\n")

    configs = []

    # 4H konfigürasyonları
    for cooldown, ema, slope, min_risk, sym_set in product(
        [5, 8],          # cooldown
        [20, 50],        # trend EMA
        [0.0, 0.2],      # EMA slope min
        [0.30, 0.50],    # min risk %
        ["ALL", "GOOD"], # sembol seti
    ):
        dfs = dfs_4h
        syms = SYMBOLS_ALL if sym_set == "ALL" else SYMBOLS_GOOD
        r, n, wr, avg = run_sym_set(dfs, syms, cooldown, ema, slope,
                                    min_risk, window=150, max_pending=12)
        configs.append(("4H", sym_set, cooldown, ema, slope, min_risk, r, n, wr, avg))

    # 1H konfigürasyonları
    for cooldown, ema, slope, min_risk, sym_set in product(
        [10, 20],        # cooldown (1H'ta daha büyük = 4H cooldown kadar)
        [20, 50],
        [0.0, 0.2],
        [0.30, 0.50],
        ["ALL", "GOOD"],
    ):
        dfs = dfs_1h
        syms = SYMBOLS_ALL if sym_set == "ALL" else SYMBOLS_GOOD
        r, n, wr, avg = run_sym_set(dfs, syms, cooldown, ema, slope,
                                    min_risk, window=300, max_pending=48)
        configs.append(("1H", sym_set, cooldown, ema, slope, min_risk, r, n, wr, avg))

    # ── 3. Sonuçları Sırala ──────────────────────────────────────────────────
    configs.sort(key=lambda x: x[6], reverse=True)

    print(f"{'TF':<4} {'SYM':<5} {'CD':<4} {'EMA':<5} {'SLP':<5} {'MR':<5}"
          f" {'NetR':>8} {'n':>5} {'WR%':>6} {'avgR':>7}")
    print("-" * 65)
    for cfg in configs[:20]:
        tf, sym, cd, ema, slp, mr, r, n, wr, avg = cfg
        print(f"{tf:<4} {sym:<5} {cd:<4} {ema:<5} {slp:<5.1f} {mr:<5.2f}"
              f" {r:>+8.2f} {n:>5} {wr:>5.1f}% {avg:>+7.3f}")

    print("\n" + "=" * 65)
    best = configs[0]
    tf, sym, cd, ema, slp, mr, r, n, wr, avg = best
    print(f"EN İYİ: TF={tf}  Semboller={sym}  Cooldown={cd}  "
          f"EMA={ema}  Slope>={slp}  MinRisk>={mr}%")
    print(f"        NetR={r:+.2f}R  n={n}  WR={wr:.1f}%  avgR={avg:+.3f}R")
    print("=" * 65)

    # En iyi 1H konfigürasyonu (ayrıca göster)
    best_1h = next(c for c in configs if c[0] == "1H")
    tf, sym, cd, ema, slp, mr, r, n, wr, avg = best_1h
    print(f"\nEn iyi 1H: {sym}  Cooldown={cd}  EMA={ema}  "
          f"Slope>={slp}  MinRisk>={mr}%")
    print(f"           NetR={r:+.2f}R  n={n}  WR={wr:.1f}%  avgR={avg:+.3f}R")

    # Sembol bazında en iyi 1H detayı
    print(f"\nEn iyi 1H konfigürasyonunda sembol bazında sonuçlar:")
    print(f"{'Sembol':<12} {'n':>5} {'WR%':>6} {'NetR':>8} {'avgR':>7}")
    print("-" * 45)
    syms = SYMBOLS_ALL if best_1h[1] == "ALL" else SYMBOLS_GOOD
    for s in syms:
        df = dfs_1h.get(s)
        if df is None:
            continue
        _, stats = run_backtest(
            df, MODELS,
            window=300, cooldown=best_1h[2], fee_pct=FEE_PCT, slippage_pct=SLIP_PCT,
            max_bars_pending=48, trend_ema=best_1h[3],
            ema_slope_min=best_1h[4], min_risk_pct=best_1h[5],
        )
        dec = stats.wins + stats.losses
        wr_s = stats.wins / dec * 100 if dec else 0
        avg_s = stats.sum_r / dec if dec else 0
        flag = "✅" if stats.sum_r > 0 else "❌"
        print(f"{s:<12} {stats.total:>5} {wr_s:>5.1f}% {stats.sum_r:>+8.2f} {avg_s:>+7.3f} {flag}")

    print("\nTamamlandı.")


if __name__ == "__main__":
    main()
