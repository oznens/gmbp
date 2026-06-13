"""
1 yıllık BTC + top-11 veri üzerinde harmonic pattern derinlemesine analiz.

Çıktı:
  data/<SYM>_4H_1Y.csv      — ham OHLCV
  analysis/harmonic_stats.json — pattern bazlı istatistikler
  analysis/harmonic_report.html — HTML rapor

Çalıştırma:
  python analysis/harmonic_deep.py
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.okx_fetcher import OKXFetcher
from models.harmonics import detect_harmonics, HarmonicSignal
from models.price_action import confirm as pa_confirm

# ── Ayarlar ──────────────────────────────────────────────────────────────────
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
    "BNBUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT",
    "OPUSDT", "ARBUSDT", "LTCUSDT", "ADAUSDT",
]
TF          = "4h"
LIMIT_1Y    = 2200          # 365 * 6 + 100 buffer
ZIGZAG_DEPTH = 5
MIN_SCORE   = 0.50          # geniş tut, sonra filtreleriz
MAX_D_BARS  = 8             # D noktasından kaç bar içinde sinyal geçerli
SL_BUFFER   = 0.002
FEE_SLIP    = 0.08          # round-trip %0.08 (fee+slip+funding)
EMA_PERIOD  = 50
DATA_DIR    = Path("data")
DATA_DIR.mkdir(exist_ok=True)


# ── Yardımcılar ──────────────────────────────────────────────────────────────

def fetch_and_save(sym: str, fetcher: OKXFetcher) -> pd.DataFrame | None:
    csv = DATA_DIR / f"{sym}_4H_1Y.csv"
    if csv.exists():
        df = pd.read_csv(csv, index_col=0, parse_dates=True)
        print(f"  {sym}: CSV'den yüklendi ({len(df)} bar)")
        return df
    print(f"  {sym}: OKX'ten çekiliyor…", end="", flush=True)
    df = fetcher.fetch_ohlcv(sym, TF, limit=LIMIT_1Y)
    if df is None or len(df) < 200:
        print(" HATA")
        return None
    df.to_csv(csv)
    print(f" {len(df)} bar kaydedildi → {csv}")
    return df


def simulate_trade(df: pd.DataFrame, open_idx: int, direction: str,
                   entry: float, stop: float, tp: float,
                   max_pending: int = 12) -> dict:
    """Limit fill + SL/TP simülasyonu. Sonuç: outcome, r_multiple, bars_to_fill."""
    pending = 0
    filled = False
    for j in range(open_idx + 1, len(df)):
        hi, lo = df.iloc[j]["high"], df.iloc[j]["low"]
        if not filled:
            pending += 1
            if pending > max_pending:
                return {"outcome": "CANCELLED", "r_multiple": None, "bars_to_fill": None}
            if direction == "LONG" and lo <= entry:
                filled = True
            elif direction == "SHORT" and hi >= entry:
                filled = True
            else:
                continue
        # filled — SL/TP kontrolü
        if direction == "LONG":
            hit_sl, hit_tp = lo <= stop, hi >= tp
        else:
            hit_sl, hit_tp = hi >= stop, lo <= tp
        if hit_sl or hit_tp:
            outcome = "LOSS" if (hit_sl and hit_tp) or hit_sl else "WIN"
            exit_p  = stop if outcome == "LOSS" else tp
            risk    = abs(entry - stop)
            move    = (exit_p - entry) if direction == "LONG" else (entry - exit_p)
            cost_r  = (FEE_SLIP / 100 * entry) / risk if risk > 0 else 0
            r       = move / risk - cost_r if risk > 0 else 0
            return {"outcome": outcome, "r_multiple": round(r, 3),
                    "bars_to_fill": pending}
    return {"outcome": "OPEN", "r_multiple": None, "bars_to_fill": pending}


def score_signal(h: HarmonicSignal, pa_confirmations: list,
                 trend_aligned: bool, vol_ratio: float) -> int:
    """0-100 arası güven puanı."""
    s = 0
    # 1) Fibonacci kalitesi (max 35)
    s += int(h.score * 35)
    # 2) PA onayı (max 30): 1 onay=15, 2=25, 3=30
    pa_pts = {0: 0, 1: 15, 2: 25, 3: 30}
    s += pa_pts.get(min(len(pa_confirmations), 3), 30)
    # 3) Trend hizası (15)
    if trend_aligned:
        s += 15
    # 4) Hacim (max 20): son mumun hacmi ortalamanın 1.5x+ üstündeyse
    if vol_ratio >= 2.0:
        s += 20
    elif vol_ratio >= 1.5:
        s += 12
    elif vol_ratio >= 1.0:
        s += 6
    return min(s, 100)


# ── Ana analiz döngüsü ────────────────────────────────────────────────────────

def analyze(df: pd.DataFrame, sym: str) -> list[dict]:
    """Tam dataset üzerinde kayan pencereyle harmonic sinyalleri üret + backtest et.
    Pencere: 300 bar (harmonic oluşumu için yeterli), her 3 barda bir kaydır.
    """
    ema   = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean().values
    vol   = df["volume"].values if "volume" in df.columns else np.ones(len(df))
    vol_ma = pd.Series(vol).rolling(20).mean().values

    records = []
    seen_d  = set()   # (global_d_idx, pattern, direction) tekrar önle
    window  = 300     # harmonic oluşumu için yeterli pencere

    for i in range(window, len(df) - 1, 3):   # her 3 barda bir tara
        # view: reset_index zorunlu — harmonics positional index kullanıyor
        view = df.iloc[i - window:i + 1].reset_index(drop=True)
        try:
            signals = detect_harmonics(view, depth=ZIGZAG_DEPTH, min_score=MIN_SCORE)
        except Exception:
            continue

        for h in signals:
            # D noktasının global dataframe indeksine çevir
            g_d = (i - window) + h.d_index
            key = (g_d, h.pattern, h.direction)
            if key in seen_d:
                continue
            # D noktası çok eski mi?
            if i - g_d > MAX_D_BARS:
                continue
            seen_d.add(key)

            # PRZ dokunuşu kontrolü
            prz_margin = h.prz_high - h.prz_low
            last = view.iloc[-1]
            if h.direction == "bullish":
                touched = last["low"] <= h.prz_high + prz_margin
            else:
                touched = last["high"] >= h.prz_low - prz_margin
            if not touched:
                continue

            # PA onayı
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
                sl  = min(h.D, float(last["low"])) * (1 - SL_BUFFER)
                tp1 = h.D + cd * 0.382
                tp2 = h.D + cd * 0.618
            else:
                sl  = max(h.D, float(last["high"])) * (1 + SL_BUFFER)
                tp1 = h.D - cd * 0.382
                tp2 = h.D - cd * 0.618

            entry = float(last["close"])
            risk  = abs(entry - sl)
            if risk <= 0:
                continue
            rr2 = abs(tp2 - entry) / risk
            if rr2 < 1.5:
                continue

            trend_ok = (direction == "LONG" and entry > ema[i]) or \
                       (direction == "SHORT" and entry < ema[i])

            vr = float(vol[i] / vol_ma[i]) if vol_ma[i] > 0 else 1.0
            conf_score = score_signal(h, pa_confs, trend_ok, vr)

            result = simulate_trade(df, i, direction, entry, sl, tp2)

            records.append({
                "symbol":       sym,
                "pattern":      h.pattern,
                "direction":    direction,
                "open_time":    str(df.index[i]),
                "entry":        round(entry, 6),
                "stop":         round(sl, 6),
                "tp1":          round(tp1, 6),
                "tp2":          round(tp2, 6),
                "rr":           round(rr2, 2),
                "fib_score":    h.score,
                "pa_confs":     pa_confs,
                "trend_ok":     trend_ok,
                "vol_ratio":    round(vr, 2),
                "conf_score":   conf_score,
                "outcome":      result["outcome"],
                "r_multiple":   result["r_multiple"],
                "bars_to_fill": result["bars_to_fill"],
            })
    return records


# ── HTML rapor ───────────────────────────────────────────────────────────────

def build_report(all_records: list[dict], ran_at: str) -> str:
    df = pd.DataFrame(all_records)
    if df.empty:
        return "<h1>Sonuç yok</h1>"

    closed  = df[df["outcome"].isin(["WIN", "LOSS"])].copy()
    total_n = len(closed)
    total_w = (closed["outcome"] == "WIN").sum()
    total_wr = total_w / total_n * 100 if total_n else 0
    total_r  = closed["r_multiple"].sum()
    cancelled = (df["outcome"] == "CANCELLED").sum()

    # ── Pattern bazı istatistik ──
    pat_rows = []
    for pat in sorted(df["pattern"].unique()):
        sub = closed[closed["pattern"] == pat]
        if len(sub) == 0:
            continue
        w  = (sub["outcome"] == "WIN").sum()
        wr = w / len(sub) * 100
        nr = sub["r_multiple"].sum()
        ar = sub["r_multiple"].mean()
        wrc = "color:#22c55e" if wr >= 50 else "color:#ef4444"
        nrc = "color:#22c55e" if nr >= 0 else "color:#ef4444"
        pat_rows.append(
            f'<tr><td><b>{pat}</b></td><td>{len(sub)}</td>'
            f'<td style="{wrc}">{wr:.1f}%</td>'
            f'<td style="{nrc}">{nr:+.2f}</td>'
            f'<td style="{nrc}">{ar:+.3f}</td></tr>'
        )

    # ── Skor eşiği analizi ──
    score_rows = []
    for thresh in range(30, 85, 5):
        sub = closed[closed["conf_score"] >= thresh]
        if len(sub) == 0:
            score_rows.append(f'<tr><td>≥{thresh}</td><td>0</td><td>—</td><td>—</td><td>—</td></tr>')
            continue
        w  = (sub["outcome"] == "WIN").sum()
        wr = w / len(sub) * 100
        nr = sub["r_multiple"].sum()
        ar = sub["r_multiple"].mean()
        wrc = "color:#22c55e" if wr >= 50 else "color:#ef4444"
        nrc = "color:#22c55e" if nr >= 0 else "color:#ef4444"
        score_rows.append(
            f'<tr><td>≥{thresh}</td><td>{len(sub)}</td>'
            f'<td style="{wrc}">{wr:.1f}%</td>'
            f'<td style="{nrc}">{nr:+.2f}</td>'
            f'<td style="{nrc}">{ar:+.3f}</td></tr>'
        )

    # ── PA tipi analizi ──
    pa_stats: dict = {}
    for _, row in closed.iterrows():
        for conf in row["pa_confs"]:
            b = pa_stats.setdefault(conf, {"n": 0, "w": 0, "r": 0.0})
            b["n"] += 1
            if row["outcome"] == "WIN":
                b["w"] += 1
            b["r"] += row["r_multiple"]
    pa_rows = []
    for conf_type, b in sorted(pa_stats.items()):
        wr = b["w"] / b["n"] * 100 if b["n"] else 0
        wrc = "color:#22c55e" if wr >= 50 else "color:#ef4444"
        nrc = "color:#22c55e" if b["r"] >= 0 else "color:#ef4444"
        pa_rows.append(
            f'<tr><td><b>{conf_type}</b></td><td>{b["n"]}</td>'
            f'<td style="{wrc}">{wr:.1f}%</td>'
            f'<td style="{nrc}">{b["r"]:+.2f}</td></tr>'
        )

    # ── Trend hizası analizi ──
    trend_yes = closed[closed["trend_ok"] == True]
    trend_no  = closed[closed["trend_ok"] == False]
    def trend_row(label, sub):
        if len(sub) == 0: return f'<tr><td>{label}</td><td>0</td><td>—</td><td>—</td></tr>'
        w  = (sub["outcome"] == "WIN").sum()
        wr = w / len(sub) * 100
        nr = sub["r_multiple"].sum()
        wrc = "color:#22c55e" if wr >= 50 else "color:#ef4444"
        nrc = "color:#22c55e" if nr >= 0 else "color:#ef4444"
        return f'<tr><td>{label}</td><td>{len(sub)}</td><td style="{wrc}">{wr:.1f}%</td><td style="{nrc}">{nr:+.2f}</td></tr>'

    # ── Son 30 trade listesi ──
    last30 = closed.sort_values("open_time", ascending=False).head(30)
    trade_rows = []
    for _, r in last30.iterrows():
        oc = "#22c55e" if r["outcome"] == "WIN" else "#ef4444"
        dc = "#22c55e" if r["direction"] == "LONG" else "#ef4444"
        rc = "#22c55e" if (r["r_multiple"] or 0) >= 0 else "#ef4444"
        trade_rows.append(
            f'<tr>'
            f'<td>{str(r["open_time"])[:16]}</td>'
            f'<td><b>{r["symbol"]}</b></td>'
            f'<td>{r["pattern"]}</td>'
            f'<td style="color:{dc}">{r["direction"]}</td>'
            f'<td style="color:{oc}">{r["outcome"]}</td>'
            f'<td style="color:{rc}">{(r["r_multiple"] or 0):+.2f}R</td>'
            f'<td>{r["conf_score"]}</td>'
            f'<td>{", ".join(r["pa_confs"])}</td>'
            f'<td>{"✅" if r["trend_ok"] else "❌"}</td>'
            f'<td>{r["rr"]:.1f}x</td>'
            f'</tr>'
        )

    css = """
:root{--bg:#0f1115;--card:#181b22;--line:#22262f;--text:#e8eaed;--muted:#8c93a3;
      --green:#22c55e;--red:#ef4444;--blue:#3b82f6;--orange:#f59e0b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
     font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:18px 24px;border-bottom:1px solid var(--line)}
h1{margin:0;font-size:18px;font-weight:600}
h2{font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin:0 0 12px}
main{padding:20px 24px;max-width:1300px;margin:0 auto}
.grid{display:grid;gap:16px}
.kpi-row{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-bottom:16px}
.kpi .label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.kpi .value{font-size:22px;font-weight:700;margin-top:6px}
.kpi .sub{color:var(--muted);font-size:11px;margin-top:2px}
.green{color:var(--green)} .red{color:var(--red)} .blue{color:var(--blue)} .orange{color:var(--orange)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--muted);font-weight:500;font-size:11px;
   text-transform:uppercase;letter-spacing:.5px;padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:8px 10px;border-bottom:1px solid #1d2028}
tr:last-child td{border-bottom:0}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.warn{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);
      color:var(--orange);padding:10px 14px;border-radius:8px;margin-bottom:16px;font-size:13px}
.highlight{background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.25);
           padding:10px 14px;border-radius:8px;margin-bottom:16px;font-size:13px;color:var(--green)}
"""

    wr_cls = "green" if total_wr >= 50 else "red"
    nr_cls = "green" if total_r >= 0 else "red"

    # Optimal eşiği bul
    best_thresh = 30
    best_r = total_r
    for thresh in range(30, 85, 5):
        sub = closed[closed["conf_score"] >= thresh]
        if len(sub) >= 5:
            r = sub["r_multiple"].sum()
            if r > best_r:
                best_r = r
                best_thresh = thresh

    html = f"""<!DOCTYPE html>
<html lang="tr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Harmonik Pattern Derin Analiz — 1 Yıl 4H</title>
<style>{css}</style></head><body>
<header>
  <h1>🔍 Harmonik Pattern Derin Analiz — 1 Yıl 4H</h1>
  <div style="color:#8c93a3;font-size:12px;margin-top:4px">Oluşturuldu: {ran_at} UTC | {', '.join(SYMBOLS)}</div>
</header>
<main>

<div class="warn">⚠️ PA onaylı sinyaller analiz edildi. Fee+slip+funding %0.08 round-trip dahil. EMA-{EMA_PERIOD} trend filtresi uygulandı.</div>

<div class="highlight">✅ Önerilen minimum puan eşiği: <b>≥{best_thresh}</b> → Net R: <b>{best_r:+.2f}R</b></div>

<div class="grid kpi-row">
  <div class="card kpi"><div class="label">Toplam Sinyal (closed)</div>
    <div class="value blue">{total_n}</div>
    <div class="sub">{cancelled} iptal (fill olmadı)</div></div>
  <div class="card kpi"><div class="label">Win Rate</div>
    <div class="value {wr_cls}">{total_wr:.1f}%</div>
    <div class="sub">{total_w} W / {total_n - total_w} L</div></div>
  <div class="card kpi"><div class="label">Net R (tüm)</div>
    <div class="value {nr_cls}">{total_r:+.2f}</div>
    <div class="sub">Avg: {closed["r_multiple"].mean():+.3f}R</div></div>
  <div class="card kpi"><div class="label">Optimal Eşik</div>
    <div class="value green">≥{best_thresh}</div>
    <div class="sub">{best_r:+.2f}R en iyi puan</div></div>
  <div class="card kpi"><div class="label">Avg RR</div>
    <div class="value">{closed["rr"].mean():.2f}x</div>
    <div class="sub">min {closed["rr"].min():.1f} / max {closed["rr"].max():.1f}</div></div>
</div>

<div class="two-col">
  <div class="card">
    <h2>Pattern Bazlı Sonuçlar</h2>
    <table><thead><tr><th>Pattern</th><th>n</th><th>WR</th><th>Net R</th><th>Avg R</th></tr></thead>
    <tbody>{''.join(pat_rows)}</tbody></table>
  </div>
  <div class="card">
    <h2>PA Onay Tipi</h2>
    <table><thead><tr><th>Onay</th><th>n</th><th>WR</th><th>Net R</th></tr></thead>
    <tbody>{''.join(pa_rows)}</tbody></table>
  </div>
</div>

<div class="two-col">
  <div class="card">
    <h2>Güven Puanı Eşiği Analizi (≥X puan)</h2>
    <table><thead><tr><th>Eşik</th><th>n</th><th>WR</th><th>Net R</th><th>Avg R</th></tr></thead>
    <tbody>{''.join(score_rows)}</tbody></table>
  </div>
  <div class="card">
    <h2>Trend Hizası</h2>
    <table><thead><tr><th>Durum</th><th>n</th><th>WR</th><th>Net R</th></tr></thead>
    <tbody>
      {trend_row("✅ Trend hizalı", trend_yes)}
      {trend_row("❌ Trend karşı", trend_no)}
    </tbody></table>
  </div>
</div>

<div class="card">
  <h2>Son 30 Sinyal Detayı</h2>
  <table><thead><tr>
    <th>Zaman</th><th>Sembol</th><th>Pattern</th><th>Yön</th>
    <th>Sonuç</th><th>R</th><th>Puan</th><th>PA Onay</th><th>Trend</th><th>RR</th>
  </tr></thead>
  <tbody>{''.join(trade_rows)}</tbody></table>
</div>

</main></body></html>"""
    return html


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    fetcher = OKXFetcher()
    Path("analysis").mkdir(exist_ok=True)

    all_records = []
    for sym in SYMBOLS:
        df = fetch_and_save(sym, fetcher)
        if df is None:
            continue
        print(f"  {sym}: pattern analizi…", end="", flush=True)
        records = analyze(df, sym)
        print(f" {len(records)} sinyal bulundu "
              f"({sum(1 for r in records if r['outcome']=='WIN')} W / "
              f"{sum(1 for r in records if r['outcome']=='LOSS')} L / "
              f"{sum(1 for r in records if r['outcome']=='CANCELLED')} iptal)")
        all_records.extend(records)

    # JSON kaydet
    stats_path = Path("analysis/harmonic_stats.json")
    stats_path.write_text(json.dumps(all_records, indent=2, default=str))
    print(f"\nJSON: {stats_path}  ({len(all_records)} kayıt)")

    # HTML rapor
    ran_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    html = build_report(all_records, ran_at)
    report_path = Path("analysis/harmonic_report.html")
    report_path.write_text(html, encoding="utf-8")
    print(f"Rapor: {report_path}  ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
