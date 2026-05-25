"""Historical backtest with trade simulation.

Sliding window halinde OKX historical mumlarda gezer, modellerin uretrigi
sinyalleri al/sat emrine cevirir, sonraki mumlarda SL/TP'den hangisinin
once vuruldugunu hesaplar, win-rate ve net P&L raporlar.

Kullanim:
    .venv/bin/python backtest_history.py
    .venv/bin/python backtest_history.py --symbol ETHUSDT --tf 1h --limit 2000
    .venv/bin/python backtest_history.py --models po3,bos_fvg --tf 15m
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from utils.okx_fetcher import OKXFetcher
from models.ict_models import (
    PO3Model, BOSFVGModel, CHOCHOBModel, OTEModel,
    SILVERBULLETModel, LONDONREVERSALModel, NYREVERSALModel,
    TURTLESOUPModel, JUDASSWINGModel, SBSModel,
    INDUCEMENTModel, BREADBUTTERModel, MMXMModel, TGIFModel,
    IMBALANCEPLAYModel, SMTDivergenceModel, BPRModel,
)

MODELS = {
    "po3": PO3Model, "bos_fvg": BOSFVGModel, "choch_ob": CHOCHOBModel,
    "ote": OTEModel, "silver_bullet": SILVERBULLETModel,
    "london_reversal": LONDONREVERSALModel, "ny_reversal": NYREVERSALModel,
    "turtle_soup": TURTLESOUPModel, "judas_swing": JUDASSWINGModel,
    "sbs": SBSModel, "inducement": INDUCEMENTModel,
    "bread_butter": BREADBUTTERModel, "mmxm": MMXMModel, "tgif": TGIFModel,
    "imbalance": IMBALANCEPLAYModel, "smt_divergence": SMTDivergenceModel,
    "bpr": BPRModel,
}


@dataclass
class Trade:
    model: str
    direction: str
    entry: float
    stop: float
    tp: float
    open_idx: int
    open_time: pd.Timestamp
    close_idx: Optional[int] = None
    close_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    outcome: Optional[str] = None  # WIN / LOSS / OPEN
    r_multiple: Optional[float] = None

    def risk(self) -> float:
        return abs(self.entry - self.stop)

    def reward(self) -> float:
        return abs(self.tp - self.entry)


def simulate_trade(df: pd.DataFrame, trade: Trade,
                   fee_pct: float = 0.0, slippage_pct: float = 0.0) -> Trade:
    """Trade'in entry'den sonraki mumlarda SL veya TP'den hangisinin
    once vuruldugunu bul. Ayni mumda ikisi de varsa pesimist davran (SL once).

    fee_pct / slippage_pct: tek-yon yuzdesi. R-multiple round-trip maliyetle
    dusurulur: cost_R = 2 * (fee+slippage) * entry / risk
    """
    for j in range(trade.open_idx + 1, len(df)):
        row = df.iloc[j]
        hi, lo = row["high"], row["low"]
        if trade.direction == "LONG":
            hit_sl = lo <= trade.stop
            hit_tp = hi >= trade.tp
        else:  # SHORT
            hit_sl = hi >= trade.stop
            hit_tp = lo <= trade.tp
        if hit_sl and hit_tp:
            outcome, exit_price = "LOSS", trade.stop
        elif hit_sl:
            outcome, exit_price = "LOSS", trade.stop
        elif hit_tp:
            outcome, exit_price = "WIN", trade.tp
        else:
            continue
        trade.close_idx = j
        trade.close_time = df.index[j]
        trade.exit_price = exit_price
        trade.outcome = outcome
        risk = trade.risk()
        if risk == 0:
            trade.r_multiple = 0.0
        else:
            move = (exit_price - trade.entry) if trade.direction == "LONG" else (trade.entry - exit_price)
            trade.r_multiple = move / risk
            # Round-trip cost (entry+exit slippage + 2x fee) -> R cinsi
            if fee_pct > 0 or slippage_pct > 0:
                cost_pct = 2.0 * (fee_pct + slippage_pct) / 100.0
                cost_R = (cost_pct * trade.entry) / risk
                trade.r_multiple -= cost_R
        return trade
    trade.outcome = "OPEN"  # backtest sonuna kadar acik kaldi
    return trade


def normalize_signal(sig: dict, default_rr: float = 2.0) -> Optional[dict]:
    """Modeller arasi tutarsiz cikti formatlarini standart hale getir.

    direction: 1/-1 ya da 'LONG'/'SHORT' kabul edilir; cikti her zaman 'LONG'/'SHORT'.
    tp: eksikse default_rr kullanilarak entry +/- (entry-stop)*rr hesaplanir.
    Donus: {direction, entry, stop, tp} - sinyalin gecerli kismi.
    """
    try:
        d_raw = sig.get("direction")
        if d_raw in (1, "1", "LONG", "long", "BUY", "buy"):
            direction = "LONG"
        elif d_raw in (-1, "-1", "SHORT", "short", "SELL", "sell"):
            direction = "SHORT"
        else:
            return None
        entry = float(sig["entry"])
        stop = float(sig.get("stop") if sig.get("stop") is not None else sig.get("sl"))
    except (TypeError, ValueError, KeyError):
        return None

    if direction == "LONG" and not stop < entry:
        return None
    if direction == "SHORT" and not stop > entry:
        return None

    tp_raw = sig.get("tp")
    if tp_raw is None:
        risk = abs(entry - stop)
        tp = entry + risk * default_rr if direction == "LONG" else entry - risk * default_rr
    else:
        try:
            tp = float(tp_raw)
        except (TypeError, ValueError):
            return None
        if direction == "LONG" and not tp > entry:
            return None
        if direction == "SHORT" and not tp < entry:
            return None

    return {"direction": direction, "entry": entry, "stop": float(stop), "tp": float(tp)}


@dataclass
class Stats:
    total: int = 0
    wins: int = 0
    losses: int = 0
    open: int = 0
    sum_r: float = 0.0
    per_model: dict = field(default_factory=dict)

    def add(self, t: Trade) -> None:
        self.total += 1
        bucket = self.per_model.setdefault(t.model, {"n": 0, "w": 0, "l": 0, "r": 0.0})
        bucket["n"] += 1
        if t.outcome == "WIN":
            self.wins += 1
            bucket["w"] += 1
        elif t.outcome == "LOSS":
            self.losses += 1
            bucket["l"] += 1
        else:
            self.open += 1
        if t.r_multiple is not None:
            self.sum_r += t.r_multiple
            bucket["r"] += t.r_multiple


def run_backtest(
    df: pd.DataFrame,
    models: dict,
    window: int = 200,
    cooldown: int = 5,
    max_concurrent: int = 1,
    fee_pct: float = 0.0,
    slippage_pct: float = 0.0,
) -> tuple[list[Trade], Stats]:
    open_trades: list[Trade] = []
    closed: list[Trade] = []
    last_signal_idx: dict[str, int] = {}

    for i in range(window, len(df) - 1):
        # Onceden acilan trade'lerden tamamlananları kapat (her bar guncellenir)
        still_open = []
        for t in open_trades:
            simulate_trade(df, t, fee_pct=fee_pct, slippage_pct=slippage_pct)
            if t.outcome and t.outcome != "OPEN":
                if t.close_idx is not None and t.close_idx <= i:
                    closed.append(t)
                    continue
            still_open.append(t)
        open_trades = still_open

        if len(open_trades) >= max_concurrent:
            continue

        window_df = df.iloc[i - window:i].copy()
        for name, cls in models.items():
            if i - last_signal_idx.get(name, -10**9) < cooldown:
                continue
            # Her detect cagrisi icin fresh instance; bircok model stateful.
            try:
                model = cls()
                sig = model.detect(window_df)
            except Exception:
                continue
            if not sig:
                continue
            norm = normalize_signal(sig)
            if norm is None:
                continue
            trade = Trade(
                model=name,
                direction=norm["direction"],
                entry=norm["entry"],
                stop=norm["stop"],
                tp=norm["tp"],
                open_idx=i,
                open_time=df.index[i],
            )
            open_trades.append(trade)
            last_signal_idx[name] = i
            if len(open_trades) >= max_concurrent:
                break

    # Geri kalan acik trade'leri tamamla (backtest sonunda)
    for t in open_trades:
        simulate_trade(df, t)
        closed.append(t)

    stats = Stats()
    for t in closed:
        stats.add(t)
    return closed, stats


def print_report(symbol: str, tf: str, df: pd.DataFrame, trades: list[Trade], stats: Stats) -> None:
    print()
    print("=" * 70)
    print(f"  Historical backtest - {symbol} @ {tf}")
    print(f"  Donem: {df.index[0]} -> {df.index[-1]}  ({len(df)} mum)")
    print("=" * 70)
    if stats.total == 0:
        print("  Hicbir model trade uretmedi.")
        return
    decided = stats.wins + stats.losses
    wr = (stats.wins / decided * 100) if decided else 0.0
    avg_r = stats.sum_r / decided if decided else 0.0
    print(f"  Toplam trade : {stats.total}  (kazanan {stats.wins} / kaybeden {stats.losses} / acik {stats.open})")
    print(f"  Win-rate     : %{wr:5.1f}")
    print(f"  Ortalama R   : {avg_r:+.2f}R")
    print(f"  Net P&L      : {stats.sum_r:+.2f}R")
    print()
    print("  Model basina:")
    print(f"  {'model':<18s}{'n':>4s}{'W':>4s}{'L':>4s}{'WR%':>7s}{'sumR':>9s}")
    for name in sorted(stats.per_model):
        b = stats.per_model[name]
        dec = b["w"] + b["l"]
        wr_m = (b["w"] / dec * 100) if dec else 0.0
        print(f"  {name:<18s}{b['n']:>4d}{b['w']:>4d}{b['l']:>4d}{wr_m:>6.1f} {b['r']:>+8.2f}")
    print()
    print("  Son 5 kapali trade:")
    for t in [x for x in trades if x.outcome in ("WIN", "LOSS")][-5:]:
        print(f"  [{t.outcome:<4s}] {t.model:<14s} {t.direction:<5s} "
              f"entry={t.entry:.2f}  exit={t.exit_price:.2f}  R={t.r_multiple:+.2f}  "
              f"open={t.open_time:%Y-%m-%d %H:%M}")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--tf", default="1h", help="Timeframe (1m,5m,15m,1h,4h,...)")
    p.add_argument("--limit", type=int, default=1500, help="Toplam mum sayisi")
    p.add_argument("--window", type=int, default=200, help="Sliding window boyu")
    p.add_argument("--cooldown", type=int, default=5, help="Ayni modelden iki sinyal arasi min mum")
    p.add_argument("--concurrent", type=int, default=1, help="Ayni anda max acik trade")
    p.add_argument("--models", default="", help="Virgulle ayrilmis liste; bos -> hepsi")
    p.add_argument("--plot", default="", help="PNG path; verilirse equity curve + drawdown cizilir")
    p.add_argument("--fee", type=float, default=0.0,
                   help="Tek-yon komisyon yuzdesi (orn. 0.05 = %%0.05). Round-trip 2x uygulanir.")
    p.add_argument("--slippage", type=float, default=0.0,
                   help="Tek-yon slippage+spread yuzdesi (orn. 0.02 = %%0.02). Round-trip 2x.")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if not args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # Modellerin kendi INFO/ERROR spam'ini bastir
    logging.getLogger().setLevel(logging.WARNING if not args.verbose else logging.INFO)

    selected = {k: v for k, v in MODELS.items() if not args.models or k in args.models.split(",")}
    if not selected:
        print(f"Bilinmeyen model: {args.models}. Secenekler: {list(MODELS)}")
        return 1

    fetcher = OKXFetcher()
    print(f"Veri cekiliyor: {args.symbol} {args.tf} limit={args.limit}...")
    df = fetcher.fetch_ohlcv(args.symbol, args.tf, limit=args.limit)
    if df is None or len(df) < args.window + 50:
        print("Yeterli veri cekilemedi.")
        return 1
    print(f"  {len(df)} mum, {df.index[0]} -> {df.index[-1]}")
    print(f"Backtest calistiriliyor ({len(selected)} model, window={args.window})...")
    trades, stats = run_backtest(df, selected, window=args.window, cooldown=args.cooldown,
                                 max_concurrent=args.concurrent,
                                 fee_pct=args.fee, slippage_pct=args.slippage)
    print_report(args.symbol, args.tf, df, trades, stats)
    if args.plot:
        plot_equity(trades, df, args.symbol, args.tf, args.plot)
    return 0


def plot_equity(trades: list[Trade], df: pd.DataFrame, symbol: str, tf: str, out_path: str) -> None:
    """Equity curve + drawdown + R-distribution + price PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    closed = [t for t in trades if t.r_multiple is not None and t.close_time is not None]
    if not closed:
        print("Plot: kapali trade yok.")
        return
    closed.sort(key=lambda t: t.close_time)
    times = [t.close_time for t in closed]
    rs = [t.r_multiple for t in closed]
    cum = []
    s = 0.0
    for r in rs:
        s += r
        cum.append(s)
    # Drawdown (R cinsinden)
    peak = cum[0]
    dd = []
    for x in cum:
        peak = max(peak, x)
        dd.append(x - peak)

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), gridspec_kw={"height_ratios": [3, 2, 2]})
    fig.suptitle(f"ICT Backtest — {symbol} @ {tf}  ({df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d})",
                 fontsize=12, fontweight="bold")

    # 1) Equity (cumulative R) + price overlay
    ax = axes[0]
    ax.plot(times, cum, color="tab:blue", linewidth=1.8, label="Cumulative R")
    ax.set_ylabel("Cumulative R", color="tab:blue")
    ax.axhline(0, color="grey", linewidth=0.6, linestyle="--")
    ax.grid(alpha=0.3)
    ax2 = ax.twinx()
    ax2.plot(df.index, df["close"], color="tab:orange", alpha=0.35, linewidth=0.9, label="Price")
    ax2.set_ylabel(f"{symbol} price", color="tab:orange")
    # Trade markers
    wins = [(t.close_time, c) for t, c in zip(closed, cum) if t.outcome == "WIN"]
    losses = [(t.close_time, c) for t, c in zip(closed, cum) if t.outcome == "LOSS"]
    if wins:
        ax.scatter(*zip(*wins), color="green", s=18, zorder=5, label=f"WIN ({len(wins)})")
    if losses:
        ax.scatter(*zip(*losses), color="red", s=18, zorder=5, label=f"LOSS ({len(losses)})")
    ax.legend(loc="upper left", fontsize=8)

    # 2) Drawdown
    ax = axes[1]
    ax.fill_between(times, dd, 0, color="tab:red", alpha=0.35)
    ax.plot(times, dd, color="tab:red", linewidth=1.2)
    ax.set_ylabel("Drawdown (R)")
    ax.set_title(f"Max drawdown: {min(dd):+.2f}R", fontsize=10)
    ax.grid(alpha=0.3)

    # 3) R-multiple histogram per model
    ax = axes[2]
    by_model: dict[str, list[float]] = {}
    for t in closed:
        by_model.setdefault(t.model, []).append(t.r_multiple)
    colors = plt.cm.tab10.colors
    bottom = None
    bins = [-3, -2, -1, -0.5, 0, 0.5, 1, 2, 3, 5]
    import numpy as np
    centers = np.arange(len(bins) - 1)
    width = 0.8
    for i, (m, vals) in enumerate(sorted(by_model.items(), key=lambda kv: -len(kv[1]))):
        counts, _ = np.histogram(vals, bins=bins)
        ax.bar(centers, counts, width=width, bottom=bottom,
               color=colors[i % len(colors)], label=f"{m} (n={len(vals)})", edgecolor="white")
        bottom = counts if bottom is None else bottom + counts
    ax.set_xticks(centers)
    ax.set_xticklabels([f"{bins[i]}..{bins[i+1]}" for i in range(len(bins) - 1)], rotation=30, fontsize=8)
    ax.set_ylabel("Trade count")
    ax.set_title("R-multiple distribution (stacked by model)", fontsize=10)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.3, axis="y")

    for ax in axes[:2]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate(rotation=0)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_path, dpi=120)
    print(f"Plot kaydedildi: {out_path}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
