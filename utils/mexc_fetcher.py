"""MEXC public futures market data fetcher.

OKXFetcher ile ayni interface (fetch_ohlcv) -- paper_trade dry-run icin
ikinci bir veri kaynagi olarak kullanilir. Auth gerektirmez.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
import pandas as pd
import requests

_MEXC_BASE_URL = "https://contract.mexc.com"
_MEXC_KLINE_PATH = "/api/v1/contract/kline/{symbol}"

# Trader timeframe -> MEXC interval
_TF_MAP = {
    "1m": "Min1", "5m": "Min5", "15m": "Min15", "30m": "Min30",
    "1h": "Min60", "4h": "Hour4", "8h": "Hour8",
    "1d": "Day1", "1w": "Week1", "1M": "Month1",
}

# Saniye cinsinden timeframe suresi (pagination icin)
_TF_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "8h": 28800,
    "1d": 86400, "1w": 604800,
}


def _normalize_symbol(symbol: str) -> str:
    """BTCUSDT -> BTC_USDT (MEXC futures format)."""
    s = symbol.upper().replace("/", "").replace(":USDT", "").replace("-", "")
    if "_" in s:
        return s
    if s.endswith("USDT"):
        return f"{s[:-4]}_USDT"
    if s.endswith("USD"):
        return f"{s[:-3]}_USD"
    return s


class MEXCFetcher:
    """OHLCV-only MEXC futures client. Auth gerektirmez."""

    def __init__(self, base_url: str = _MEXC_BASE_URL, timeout: int = 10):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> Optional[pd.DataFrame]:
        """MEXC'ten OHLCV cek, eskiden yeniye sirali DataFrame dondur.

        Sutunlar: open, high, low, close, volume, turnover. Indeks: timestamp.
        Hata durumunda None doner.
        """
        interval = _TF_MAP.get(timeframe)
        if interval is None:
            logging.error(f"Bilinmeyen timeframe: {timeframe}")
            return None
        tf_sec = _TF_SECONDS.get(timeframe)
        if tf_sec is None:
            logging.error(f"Pagination icin desteklenmeyen timeframe: {timeframe}")
            return None

        inst = _normalize_symbol(symbol)
        # MEXC tek istekte en fazla 2000 mum doner; istenen `limit` buyukse
        # geriye dogru pencereyi kaydirarak birden cok istek at.
        max_per_req = 2000
        end_ts = int(time.time())
        all_rows: dict[int, tuple] = {}

        while len(all_rows) < limit:
            need = limit - len(all_rows)
            window = min(need, max_per_req)
            start_ts = end_ts - window * tf_sec
            try:
                r = self.session.get(
                    self.base_url + _MEXC_KLINE_PATH.format(symbol=inst),
                    params={"interval": interval, "start": start_ts, "end": end_ts},
                    timeout=self.timeout,
                )
                r.raise_for_status()
                payload = r.json()
            except Exception as e:
                logging.error(f"MEXC fetch hatasi: {e}")
                return None

            if not payload.get("success"):
                logging.error(f"MEXC API hatasi: {payload}")
                return None

            data = payload.get("data") or {}
            times = data.get("time") or []
            if not times:
                break

            for i, ts in enumerate(times):
                if ts in all_rows:
                    continue
                all_rows[ts] = (
                    float(data["open"][i]),
                    float(data["high"][i]),
                    float(data["low"][i]),
                    float(data["close"][i]),
                    float(data["vol"][i]),
                    float(data["amount"][i]),
                )

            if len(times) < window:
                # Daha eski veri yok
                break
            end_ts = min(times) - 1
            time.sleep(0.1)

        if not all_rows:
            return None

        sorted_ts = sorted(all_rows.keys())
        df = pd.DataFrame(
            [all_rows[t] for t in sorted_ts],
            columns=["open", "high", "low", "close", "volume", "turnover"],
            index=pd.to_datetime(np.array(sorted_ts, dtype=np.int64), unit="s"),
        )
        df.index.name = "timestamp"
        return df.tail(limit)

    def get_mark_price(self, symbol: str) -> Optional[float]:
        """MEXC futures ticker'dan son fiyat (mark price proxy)."""
        inst = _normalize_symbol(symbol)
        try:
            r = self.session.get(
                f"{self.base_url}/api/v1/contract/ticker",
                params={"symbol": inst}, timeout=self.timeout,
            )
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            logging.error(f"MEXC ticker hatasi: {e}")
            return None
        if not payload.get("success"):
            return None
        data = payload.get("data") or {}
        last = data.get("lastPrice") or data.get("fairPrice")
        return float(last) if last else None
