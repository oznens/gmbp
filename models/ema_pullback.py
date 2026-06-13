"""
EMA Pullback Strategy — Kanıtlanmış basit trend-pullback modeli.

Mantık:
  LONG: Fiyat EMA-50 üstünde (uptrend) → EMA-20'ye geri çekilir →
        geri dönüş mumundan sonra bullish kapanış + hacim onayı.
  SHORT: Ayna görüntüsü.

Giriş: sinyal mumu kapanışı (market order).
SL: son swing low/high dışı (%0.3 tampon).
TP: 2.5x risk.
"""
from __future__ import annotations
from typing import Optional, Dict
import pandas as pd
import numpy as np


def detect(df: pd.DataFrame,
           ema_fast: int = 20,
           ema_slow: int = 50,
           vol_ratio_min: float = 1.2,
           min_bars: int = 60) -> Optional[Dict]:
    """
    df: kapanmış OHLCV mumları, son = en güncel.
    Döner: {direction, entry, stop, tp} veya None.
    """
    if len(df) < min_bars:
        return None

    close = df["close"].values
    high  = df["high"].values
    low   = df["low"].values
    open_ = df["open"].values
    vol   = df["volume"].values if "volume" in df.columns else np.ones(len(df))

    # EMA hesabı (causal, lookahead yok)
    ema_f = df["close"].ewm(span=ema_fast, adjust=False).mean().values
    ema_s = df["close"].ewm(span=ema_slow, adjust=False).mean().values

    # Son tamamlanmış bar = [-1], ondan önceki = [-2]
    i  = len(df) - 1   # sinyal barı
    i1 = i - 1         # önceki bar

    c  = close[i];  c1 = close[i1]
    h  = high[i];   h1 = high[i1]
    l  = low[i];    l1 = low[i1]
    o  = open_[i];  o1 = open_[i1]
    ef = ema_f[i];  es = ema_s[i]
    ef1 = ema_f[i1]; es1 = ema_s[i1]

    # Hacim oranı
    vol_avg = np.mean(vol[max(0, i - 20):i]) if i >= 5 else 1.0
    vr = vol[i] / vol_avg if vol_avg > 0 else 1.0

    # ── LONG koşulları ──────────────────────────────────────────────────────
    # 1. Uptrend: EMA-fast > EMA-slow (her iki barda da)
    # 2. Geri çekilme: i1'de fiyat EMA-fast'a dokunmuş veya altına inmiş
    # 3. Reversal onayı: i'de bullish mum (close > open) ve close > EMA-fast
    # 4. Hacim: i barda ortalamanın vol_ratio_min katı+
    long_trend    = ef > es and ef1 > es1
    long_pullback = l1 <= ef1 * 1.003       # önceki barda EMA-fast'a değdik
    long_reversal = (c > o) and (c > ef)    # şu an bullish + EMA üstünde kapat
    long_volume   = vr >= vol_ratio_min

    if long_trend and long_pullback and long_reversal and long_volume:
        # SL: son 5 bar minimumu - %0.3 tampon
        sl  = min(low[max(0, i - 5):i + 1]) * 0.997
        risk = c - sl
        if risk <= 0 or risk / c > 0.05:   # SL çok uzaksa geç
            return None
        tp  = c + risk * 2.5
        return {"direction": "LONG", "entry": round(c, 6),
                "stop": round(sl, 6), "tp": round(tp, 6)}

    # ── SHORT koşulları ─────────────────────────────────────────────────────
    short_trend    = ef < es and ef1 < es1
    short_pullback = h1 >= ef1 * 0.997
    short_reversal = (c < o) and (c < ef)
    short_volume   = vr >= vol_ratio_min

    if short_trend and short_pullback and short_reversal and short_volume:
        sl  = max(high[max(0, i - 5):i + 1]) * 1.003
        risk = sl - c
        if risk <= 0 or risk / c > 0.05:
            return None
        tp  = c - risk * 2.5
        return {"direction": "SHORT", "entry": round(c, 6),
                "stop": round(sl, 6), "tp": round(tp, 6)}

    return None


class EMAPullbackModel:
    """backtest_history MODELS dict'ine eklenebilir wrapper."""
    name = "ema_pullback"

    def detect(self, df: pd.DataFrame) -> Optional[Dict]:
        return detect(df)
