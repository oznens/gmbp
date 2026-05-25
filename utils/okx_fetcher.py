"""OKX public market data fetcher.

DataFetcher ile ayni interface'i tasir (fetch_ohlcv) ama OKX'in public REST
endpoint'ini kullanir, API key gerektirmez. Geographic restrictions nedeniyle
Bybit'e ulasilamadiginda backtest icin kullanilir.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
import pandas as pd
import requests

_OKX_BASE_URL = "https://www.okx.com"
_OKX_KLINE_PATH = "/api/v5/market/history-candles"  # gecmis veriler icin
_OKX_KLINE_LATEST_PATH = "/api/v5/market/candles"   # son 1440 mum

# Trader timeframe -> OKX bar
_TF_MAP = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1H", "2h": "2H", "4h": "4H",
    "1d": "1Dutc", "1w": "1Wutc", "1M": "1Mutc",
}


def _normalize_symbol(symbol: str) -> str:
    """BTCUSDT -> BTC-USDT (OKX format)."""
    s = symbol.upper().replace("/", "").replace(":USDT", "")
    if "-" in s:
        return s
    if s.endswith("USDT"):
        return f"{s[:-4]}-USDT"
    if s.endswith("USD"):
        return f"{s[:-3]}-USD"
    return s


class OKXFetcher:
    """OHLCV-only OKX client. Auth gerektirmez."""

    def __init__(self, base_url: str = _OKX_BASE_URL, timeout: int = 10):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> Optional[pd.DataFrame]:
        """OKX'ten OHLCV cek, eskiden yeniye sirali DataFrame dondur.

        Indeks: timestamp (datetime), sutunlar: open, high, low, close, volume, turnover.
        Hata durumunda None doner.
        """
        bar = _TF_MAP.get(timeframe)
        if bar is None:
            logging.error(f"Bilinmeyen timeframe: {timeframe}")
            return None

        inst_id = _normalize_symbol(symbol)
        rows: list[list[str]] = []
        # OKX limit basina 100 mum, bircok sayfa cekmek gerekebilir.
        # Once en gunceli al, sonra geri donerek paginate et.
        before = ""  # bos -> en guncel
        per_page = 100
        path = _OKX_KLINE_LATEST_PATH

        while len(rows) < limit:
            params = {"instId": inst_id, "bar": bar, "limit": str(per_page)}
            if before:
                params["after"] = before  # 'after' = bu ts'den ESKI mumlari getir
                path = _OKX_KLINE_PATH
            try:
                r = self.session.get(
                    f"{self.base_url}{path}", params=params, timeout=self.timeout
                )
                r.raise_for_status()
                payload = r.json()
            except Exception as e:
                logging.error(f"OKX fetch hatasi: {e}")
                return None

            if payload.get("code") != "0":
                logging.error(f"OKX API hatasi: {payload}")
                return None

            data = payload.get("data") or []
            if not data:
                break

            rows.extend(data)
            # OKX yeniden eskiye sirali doner, en eski mumun ts'i bir sonraki 'after'
            before = data[-1][0]
            if len(data) < per_page:
                break
            time.sleep(0.1)  # rate limit nezaketi

        if not rows:
            return None

        # OKX kline kolonlari: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        df = pd.DataFrame(
            rows,
            columns=[
                "timestamp", "open", "high", "low", "close",
                "volume", "vol_ccy", "turnover", "confirm",
            ],
        )
        # Sayisal donusum
        for col in ["open", "high", "low", "close", "volume", "turnover"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(np.int64), unit="ms")
        df = df.set_index("timestamp").sort_index()
        df = df[~df.index.duplicated(keep="first")]
        df = df[["open", "high", "low", "close", "volume", "turnover"]]

        # Sadece istenen kadarini dondur (en yeni 'limit' tane)
        return df.tail(limit)
