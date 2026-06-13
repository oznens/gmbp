"""
ATR Breakout Strategy — Donchian Channel tabanlı trend-following.

Mantık:
  LONG: Fiyat son N barın en yüksek seviyesini kırar + EMA yükseliyor +
        hacim onayı → trend yönünde giriş.
  SHORT: Ayna görüntüsü.

Bu modelin asıl gücü reversal değil trend riding:
  - Yanlış breakout'larda hızla stop → küçük kayıp
  - Doğru breakout'larda trend ride → büyük kazanç
"""
from __future__ import annotations
from typing import Optional, Dict
import pandas as pd
import numpy as np


def detect(df: pd.DataFrame,
           dc_period: int = 20,
           atr_period: int = 14,
           atr_sl_mult: float = 1.5,
           ema_period: int = 50,
           vol_ratio_min: float = 1.3,
           min_bars: int = 70) -> Optional[Dict]:
    if len(df) < min_bars:
        return None

    close = df["close"].values
    high  = df["high"].values
    low   = df["low"].values
    vol   = df["volume"].values if "volume" in df.columns else np.ones(len(df))

    i = len(df) - 1

    # Donchian kanalı (son dc_period bar, mevcut bar hariç — lookahead önlemi)
    dc_high = max(high[i - dc_period:i])
    dc_low  = min(low[i - dc_period:i])

    # ATR
    tr = np.maximum(high - np.roll(close, 1), np.abs(high - np.roll(close, 1)))
    tr = np.maximum(tr, np.abs(low - np.roll(close, 1)))
    tr[0] = high[0] - low[0]
    atr_s = pd.Series(tr).ewm(span=atr_period, adjust=False).mean().values
    atr   = atr_s[i]

    # EMA trend yönü
    ema = df["close"].ewm(span=ema_period, adjust=False).mean().values
    ema_rising  = ema[i] > ema[i - 5]
    ema_falling = ema[i] < ema[i - 5]

    # Hacim
    vol_avg = np.mean(vol[max(0, i - 20):i]) if i >= 5 else 1.0
    vr = vol[i] / vol_avg if vol_avg > 0 else 1.0

    c = close[i]

    # ── LONG: Donchian yüksek kırılımı ───────────────────────────────────────
    if (c > dc_high          # üst kanal kırıldı
            and ema_rising    # trend yukarı
            and vr >= vol_ratio_min):
        sl   = c - atr * atr_sl_mult
        risk = c - sl
        if risk <= 0 or risk / c > 0.06:
            return None
        tp = c + risk * 2.5
        return {"direction": "LONG", "entry": round(c, 6),
                "stop": round(sl, 6), "tp": round(tp, 6)}

    # ── SHORT: Donchian alçak kırılımı ───────────────────────────────────────
    if (c < dc_low
            and ema_falling
            and vr >= vol_ratio_min):
        sl   = c + atr * atr_sl_mult
        risk = sl - c
        if risk <= 0 or risk / c > 0.06:
            return None
        tp = c - risk * 2.5
        return {"direction": "SHORT", "entry": round(c, 6),
                "stop": round(sl, 6), "tp": round(tp, 6)}

    return None


class ATRBreakoutModel:
    """backtest_history MODELS dict'ine eklenebilir wrapper."""
    name = "atr_breakout"

    def detect(self, df: pd.DataFrame) -> Optional[Dict]:
        return detect(df)
