"""Paper trading orchestrator: signal -> OKX demo order.

Her calistirilisinda bir tur:
  1. .env'den OKX demo kredansiyelleri oku
  2. Her sembol icin son 1500 mum OKX'ten cek
  3. judas_swing + sbs modellerini calistir, en yeni sinyali al
  4. Acik pozisyonlari kontrol et (cooldown / duplicate engelle)
  5. Risk yonetimi: %2 risk/trade, max 4 acik pozisyon
  6. OKX'e market order + attached SL/TP gonder
  7. Sonuclari paper_trade_log.json'a yaz

Konservatif/agresif ayarlar CLI flag'i ile degistirilebilir.
Default risk: %2/trade, max 4 acik.

Cron mantigi: her 4 saatte bir (4h candle close'a yakin) calistir.
   */15 * * * *  cd /path/to/gmbp && .venv/bin/python paper_trade.py
   (15 dakikada bir bakar, sinyali kacirmaz)

Kullanim:
   .venv/bin/python paper_trade.py --dry-run         # OKX'e baglanma
   .venv/bin/python paper_trade.py                   # gercek demo order
   .venv/bin/python paper_trade.py --symbols BTC,ETH
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from utils.okx_fetcher import OKXFetcher
from utils.telegram import send as tg_send
from backtest_history import MODELS, normalize_signal


LOG_FILE = Path("paper_trade_log.json")
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
DEFAULT_MODELS = ["judas_swing", "sbs"]
COOLDOWN_BARS = 5  # ayni semboldeki son sinyalden sonra kac bar bekle

# OKX USDT-margined perpetual contract sizes (base currency per contract).
# Yani 1 kontrat = ctVal_base * mark_price USDT.
# Live modda get_instrument ile guncellenir; dry-run icin fallback.
CTVAL_BASE = {
    "BTC-USDT-SWAP": 0.01,
    "ETH-USDT-SWAP": 0.1,
    "SOL-USDT-SWAP": 1.0,
    "XRP-USDT-SWAP": 100.0,
    "BNB-USDT-SWAP": 0.1,
    "DOGE-USDT-SWAP": 1000.0,
    "AVAX-USDT-SWAP": 1.0,
}


def load_env(path: str = ".env") -> Dict[str, str]:
    """Basit .env okur, mevcut os.environ degerlerini override etmez."""
    env: Dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return env
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'").strip('"')
    return env


def to_okx_instid(symbol: str) -> str:
    """BTCUSDT -> BTC-USDT-SWAP (perpetual)."""
    s = symbol.upper().replace("-", "").replace("_", "")
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}-USDT-SWAP"
    raise ValueError(f"Bilinmeyen sembol formati: {symbol}")


def load_log() -> List[Dict]:
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text())
        except json.JSONDecodeError:
            return []
    return []


def save_log(entries: List[Dict]) -> None:
    LOG_FILE.write_text(json.dumps(entries, indent=2, default=str))


def already_traded_recently(log: List[Dict], symbol: str, model: str,
                            bar_time: pd.Timestamp,
                            bar_seconds: int = 14400) -> bool:
    """Bu bar zamani veya bir oncesinde ayni model+symbol icin trade actik mi?"""
    cutoff_unix = bar_time.timestamp() - bar_seconds * COOLDOWN_BARS
    for entry in log:
        if entry.get("symbol") != symbol or entry.get("model") != model:
            continue
        bt = entry.get("bar_time")
        if not bt:
            continue
        try:
            t = pd.Timestamp(bt).timestamp()
        except Exception:
            continue
        if t >= cutoff_unix:
            return True
    return False


def detect_signal(symbol: str, tf: str, selected_models: Dict, fetcher: OKXFetcher,
                  limit: int = 1500, probe_back: int = 0) -> Optional[Dict]:
    """Son bar uzerinde tum modelleri calistir, ilk normalize edilebileni dondur.

    probe_back > 0 ise son N bar boyunca geriye dogru tara, sinyal aktif olan
    ilk bar'i kullan (sadece test amaclı; production'da 0 kalmalı).
    """
    df = fetcher.fetch_ohlcv(symbol, tf, limit=limit)
    if df is None or len(df) < 250:
        logging.warning(f"{symbol}: veri yetersiz, atlandi")
        return None
    end_offsets = [0] + list(range(1, probe_back + 1))
    for off in end_offsets:
        view = df if off == 0 else df.iloc[:-off]
        if len(view) < 250:
            continue
        bar_time = view.index[-1]
        for name, cls in selected_models.items():
            try:
                model = cls()
                sig = model.detect(view)
            except Exception as e:
                logging.warning(f"{symbol}/{name} detect hatasi: {e}")
                continue
            if not sig:
                continue
            norm = normalize_signal(sig)
            if not norm:
                continue
            return {"symbol": symbol, "model": name, "bar_time": bar_time,
                    "direction": norm["direction"], "entry": float(norm["entry"]),
                    "stop": float(norm["stop"]), "tp": float(norm["tp"]),
                    "last_close": float(view.iloc[-1]["close"]),
                    "probe_offset": off}
    return None


def calc_position_size(balance: float, risk_pct: float, entry: float, stop: float,
                       contract_size_usd: float = 100.0) -> float:
    """USDT-margined perpetual icin kontrat sayisi.

    OKX SWAP'ta 1 kontrat = contract_size_usd USD notional (genelde $100 BTC, $10 alts).
    Risk = balance * risk_pct = stop_distance / entry * notional
    """
    risk_amount = balance * risk_pct / 100.0
    stop_dist_pct = abs(entry - stop) / entry
    if stop_dist_pct == 0:
        return 0.0
    notional = risk_amount / stop_dist_pct
    contracts = notional / contract_size_usd
    return contracts


def reconcile_positions(client, log: List[Dict], risk_pct: float) -> int:
    """Acik (placed) log entry'lerin durumunu OKX pozisyon gecmisiyle eslestir.

    Returns kapanan trade sayisi. Log degisirse caller save_log cagirir.
    """
    open_entries = [e for e in log if e.get("status") == "placed"]
    if not open_entries:
        return 0
    try:
        history = client.get_positions_history(limit=100)
    except Exception as e:
        logging.warning(f"positions-history alinamadi: {e}")
        return 0
    closed_count = 0
    for entry in open_entries:
        # Eslesme: ayni instId, ayni yon, open_ts >= entry'nin bar_time'ina yakin
        entry_ts_ms = int(pd.Timestamp(entry["ts"]).timestamp() * 1000)
        candidates = [
            h for h in history
            if h["instId"] == entry["instId"]
            and h["side"] == entry["direction"]
            and h["open_ts"] >= entry_ts_ms - 60_000  # 1dk tolerans (clock skew)
            and h["close_ts"] > 0
        ]
        if not candidates:
            continue
        # En yakin open_ts'i sec
        match = min(candidates, key=lambda h: abs(h["open_ts"] - entry_ts_ms))
        # Risk-cinsi R hesabi: realized_pnl / (balance_at_open * risk_pct/100)
        risk_amount = entry.get("balance_at_open", 0) * risk_pct / 100.0
        r_mult = (match["realized_pnl"] / risk_amount) if risk_amount > 0 else 0.0
        outcome = "WIN" if match["realized_pnl"] > 0 else "LOSS"
        entry["status"] = "closed"
        entry["close_ts"] = match["close_ts"]
        entry["close_price"] = match["avg_close_px"]
        entry["realized_pnl"] = match["realized_pnl"]
        entry["r_multiple"] = round(r_mult, 3)
        entry["outcome"] = outcome
        closed_count += 1
        print(f"  [CLOSE] {entry['symbol']} {entry['direction']} "
              f"{outcome} R={r_mult:+.2f} pnl={match['realized_pnl']:+.2f}USDT")
        emoji = "✅" if outcome == "WIN" else "❌"
        tg_send(
            f"{emoji} <b>{outcome}</b>  {entry['symbol']} {entry['direction']}\n"
            f"Model: {entry['model']}\n"
            f"Entry: <code>{entry['entry']:.4f}</code>  Exit: <code>{match['avg_close_px']:.4f}</code>\n"
            f"R: <b>{r_mult:+.2f}R</b>  PnL: <b>{match['realized_pnl']:+.2f} USDT</b>"
        )
    return closed_count


def execute_signal(client, sig: Dict, balance: float, risk_pct: float,
                   dry_run: bool) -> Dict:
    """Sinyali OKX order'ina cevir."""
    inst_id = to_okx_instid(sig["symbol"])
    side = "buy" if sig["direction"] == "LONG" else "sell"
    # OKX SWAP: 1 kontrat = ctVal_base * mark_price USDT
    ctval_base = CTVAL_BASE.get(inst_id, 0.01)
    lot_step = 1.0  # OKX SWAP'ta lot_step genelde 1 (kontrat tam sayisi)
    if not dry_run:
        info = client.get_instrument(inst_id)
        if info:
            try:
                ctval_base = float(info.get("ctVal") or ctval_base) * float(info.get("ctMult") or 1)
                lot_step = float(info.get("lotSz") or 1)
            except Exception:
                pass
    contract_size_usd = sig["entry"] * ctval_base
    size = calc_position_size(balance, risk_pct, sig["entry"], sig["stop"],
                              contract_size_usd=contract_size_usd)
    # OKX lot step'e yuvarla (asagi)
    if lot_step > 0:
        size = (int(size / lot_step)) * lot_step
    if size <= 0:
        return {"status": "skipped", "reason": "size=0"}
    log_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "symbol": sig["symbol"], "instId": inst_id, "model": sig["model"],
        "direction": sig["direction"], "entry": sig["entry"],
        "stop": sig["stop"], "tp": sig["tp"], "size": size,
        "bar_time": str(sig["bar_time"]),
        "balance_at_open": balance,
    }
    if dry_run:
        log_entry["status"] = "dry-run"
        print(f"  [DRY] {inst_id} {side.upper()} size={size} "
              f"entry={sig['entry']:.2f} sl={sig['stop']:.2f} tp={sig['tp']:.2f}")
        return log_entry
    # Pre-flight market alignment.  4h bar kapanisindan saatler sonra cron
    # calisabiliyor; bu arada fiyat TP veya SL araligini gecmis olabilir.
    # Stale sinyali OKX'e gondermek sCode 51052/51053 dogurur ve Telegram'a
    # ORDER ERROR dusurur -- onun yerine sessizce skip et.
    mark_px = client.get_mark_price(inst_id)
    if mark_px:
        stale_reason = None
        if sig["direction"] == "LONG":
            if mark_px >= sig["tp"]:
                stale_reason = f"market {mark_px:.4f} >= TP {sig['tp']:.4f}"
            elif mark_px <= sig["stop"]:
                stale_reason = f"market {mark_px:.4f} <= SL {sig['stop']:.4f}"
        else:
            if mark_px <= sig["tp"]:
                stale_reason = f"market {mark_px:.4f} <= TP {sig['tp']:.4f}"
            elif mark_px >= sig["stop"]:
                stale_reason = f"market {mark_px:.4f} >= SL {sig['stop']:.4f}"
        if stale_reason:
            log_entry.update({"status": "stale", "reason": stale_reason,
                              "mark_px_at_skip": mark_px})
            print(f"  [STALE] {inst_id} {sig['direction']} skipped: {stale_reason}")
            return log_entry
    try:
        result = client.place_order(inst_id, side=side, size=size,
                                    sl_price=sig["stop"], tp_price=sig["tp"])
        log_entry.update({"status": "placed", "ord_id": result.get("ord_id")})
        print(f"  [OK]  {inst_id} {side.upper()} size={size} "
              f"sl={sig['stop']:.2f} tp={sig['tp']:.2f} ord_id={result.get('ord_id')}")
        # Risk-reward
        rr = abs(sig["tp"] - sig["entry"]) / abs(sig["entry"] - sig["stop"])
        tg_send(
            f"🟢 <b>OPEN</b>  {sig['symbol']} {sig['direction']}\n"
            f"Model: {sig['model']}\n"
            f"Entry: <code>{sig['entry']:.4f}</code>\n"
            f"SL: <code>{sig['stop']:.4f}</code>  TP: <code>{sig['tp']:.4f}</code>\n"
            f"Size: {size}  RR: {rr:.2f}"
        )
    except Exception as e:
        log_entry.update({"status": "error", "error": str(e)})
        print(f"  [ERR] {inst_id}: {e}")
        tg_send(f"⚠️ <b>ORDER ERROR</b>  {sig['symbol']} {sig['direction']}\n<code>{str(e)[:200]}</code>")
    return log_entry


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    p.add_argument("--tf", default="4h")
    p.add_argument("--models", default=",".join(DEFAULT_MODELS))
    p.add_argument("--risk", type=float, default=2.0, help="%% bakiye risk per trade")
    p.add_argument("--max-positions", type=int, default=4)
    p.add_argument("--dry-run", action="store_true",
                   help="OKX'e baglanma, sadece sinyalleri yazdir")
    p.add_argument("--limit", type=int, default=1500)
    p.add_argument("--probe", type=int, default=0,
                   help="Sinyali bu kadar bar geriden ara (test icin)")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    env = load_env()
    api_key = env.get("OKX_API_KEY") or os.environ.get("OKX_API_KEY", "")
    api_secret = env.get("OKX_API_SECRET") or os.environ.get("OKX_API_SECRET", "")
    passphrase = env.get("OKX_PASSPHRASE") or os.environ.get("OKX_PASSPHRASE", "")
    demo_flag = (env.get("OKX_DEMO") or os.environ.get("OKX_DEMO", "true")).lower() == "true"

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    model_names = [m.strip() for m in args.models.split(",") if m.strip()]
    selected = {n: MODELS[n] for n in model_names if n in MODELS}
    if not selected:
        print(f"Bilinmeyen model: {args.models}")
        return 1

    print(f"Paper trade turu - {datetime.now(timezone.utc).isoformat()}")
    print(f"Mod: {'DRY-RUN' if args.dry_run else ('DEMO' if demo_flag else 'MAINNET (!)')}")
    print(f"Semboller: {', '.join(symbols)}  TF: {args.tf}  "
          f"Modeller: {', '.join(selected)}")
    print(f"Risk: %{args.risk}/trade  Max pozisyon: {args.max_positions}\n")

    client = None
    balance = 10000.0  # default dry-run baslangic
    open_positions: List[Dict] = []
    if not args.dry_run:
        if not (api_key and api_secret and passphrase):
            print("HATA: OKX_API_KEY/SECRET/PASSPHRASE .env'de eksik. "
                  "--dry-run ile test edebilirsiniz.")
            return 1
        from utils.okx_client import OKXClient
        client = OKXClient(api_key=api_key, api_secret=api_secret,
                           passphrase=passphrase, demo=demo_flag)
        try:
            balance = client.get_balance()
            open_positions = client.get_positions()
            print(f"Bakiye: {balance:.2f} USDT, acik pozisyon: {len(open_positions)}")
        except Exception as e:
            print(f"OKX bakiye/pozisyon okuma hatasi: {e}")
            return 1

    log = load_log()
    fetcher = OKXFetcher()

    # 1. Onceki placed trade'lerin kapanip kapanmadigini OKX gecmisinden kontrol et
    if client and not args.dry_run:
        n_closed = reconcile_positions(client, log, args.risk)
        if n_closed:
            print(f"  {n_closed} trade kapanmis olarak isaretlendi\n")

    open_instids = {p["instId"] for p in open_positions}

    for sym in symbols:
        inst_id = to_okx_instid(sym)
        if inst_id in open_instids:
            print(f"  {sym}: zaten acik pozisyon var, atlandi")
            continue
        if len(open_instids) >= args.max_positions:
            print(f"  Max pozisyon limitine ulasildi ({args.max_positions}), durduruluyor")
            break
        sig = detect_signal(sym, args.tf, selected, fetcher, limit=args.limit,
                            probe_back=args.probe)
        if not sig:
            print(f"  {sym}: sinyal yok")
            continue
        if already_traded_recently(log, sym, sig["model"], sig["bar_time"]):
            print(f"  {sym}/{sig['model']}: cooldown'da (son {COOLDOWN_BARS} bar)")
            continue
        print(f"  {sym}: {sig['model']} {sig['direction']} "
              f"entry={sig['entry']:.2f} sl={sig['stop']:.2f} tp={sig['tp']:.2f}")
        entry = execute_signal(client, sig, balance, args.risk, dry_run=args.dry_run)
        log.append(entry)
        if entry.get("status") in ("placed", "dry-run"):
            open_instids.add(inst_id)

    save_log(log)
    # Kumulatif rapor
    closed = [e for e in log if e.get("status") == "closed"]
    if closed:
        wins = sum(1 for e in closed if e.get("outcome") == "WIN")
        net_r = sum(e.get("r_multiple", 0) or 0 for e in closed)
        wr = wins / len(closed) * 100
        print(f"\nKumulatif: {len(closed)} kapali trade, "
              f"WR %{wr:.1f}, net {net_r:+.2f}R "
              f"(acik: {sum(1 for e in log if e.get('status') == 'placed')})")
    print(f"Log: {LOG_FILE} ({len(log)} entry toplam)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
