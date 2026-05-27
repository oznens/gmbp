"""MEXC public futures market data fetcher.

OKXFetcher ile ayni interface (fetch_ohlcv) -- paper_trade dry-run icin
ikinci bir veri kaynagi olarak kullanilir. Auth gerektirmez.

contract.mexc.com Cloudflare'in 403'unu pek cok IP icin doner; .co mirror
ayni veriyi blok olmadan servis eder.  Symbol format BTC_USDT.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
import pandas as pd
import requests

_MEXC_BASE_URL = "https://contract.mexc.co"
_MEXC_KLINE_PATH = "/api/v1/contract/kline"
_MEXC_TICKER_PATH = "/api/v1/contract/ticker"

# Trader timeframe -> MEXC futures interval
_TF_MAP = {
    "1m": "Min1", "5m": "Min5", "15m": "Min15", "30m": "Min30",
    "1h": "Min60", "4h": "Hour4", "8h": "Hour8",
    "1d": "Day1", "1w": "Week1", "1M": "Month1",
}

_TF_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "8h": 28800,
    "1d": 86400, "1w": 604800,
}


def _normalize_symbol(symbol: str) -> str:
    """BTCUSDT / BTC/USDT / BTC-USDT -> BTC_USDT (MEXC futures format)."""
    s = symbol.upper().replace("/", "_").replace(":USDT", "").replace("-", "_")
    if "_" in s:
        return s
    if s.endswith("USDT"):
        return s[:-4] + "_USDT"
    return s


class MEXCFetcher:
    """OHLCV-only MEXC futures (USDT-perp) client. Auth gerektirmez."""

    def __init__(self, base_url: str = _MEXC_BASE_URL, timeout: int = 15):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        })

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> Optional[pd.DataFrame]:
        """MEXC futures'tan OHLCV cek, eskiden yeniye sirali DataFrame dondur.

        Sutunlar: open, high, low, close, volume, turnover. Indeks: timestamp.
        Hata durumunda None doner.

        MEXC futures tek istekte ~2000 mum, [start, end] saniye cinsinden.
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
        # Tek istek max 2000 kayit doner (MEXC limiti)
        max_per_req = 1900
        end_sec = int(time.time())
        all_rows: dict[int, tuple] = {}

        while len(all_rows) < limit:
            need = limit - len(all_rows)
            window = min(need, max_per_req)
            start_sec = end_sec - window * tf_sec
            params = {
                "interval": interval,
                "start": start_sec,
                "end": end_sec,
            }
            try:
                r = self.session.get(
                    f"{self.base_url}{_MEXC_KLINE_PATH}/{inst}",
                    params=params, timeout=self.timeout,
                )
                r.raise_for_status()
                payload = r.json()
            except Exception as e:
                logging.error(f"MEXC fetch hatasi: {e}")
                return None

            if not payload.get("success"):
                logging.error(f"MEXC API error: {payload}")
                return None
            data = payload.get("data", {})
            times = data.get("time", []) or []
            if not times:
                break

            opens = data.get("open", [])
            highs = data.get("high", [])
            lows = data.get("low", [])
            closes = data.get("close", [])
            vols = data.get("vol", [])
            amts = data.get("amount", vols)

            for i, ts in enumerate(times):
                ts = int(ts)
                if ts in all_rows:
                    continue
                all_rows[ts] = (
                    float(opens[i]), float(highs[i]), float(lows[i]),
                    float(closes[i]),
                    float(vols[i]) if i < len(vols) else 0.0,
                    float(amts[i]) if i < len(amts) else 0.0,
                )

            if len(times) < window:
                break
            end_sec = min(all_rows.keys()) - 1
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
        """MEXC futures ticker'dan son fiyat."""
        inst = _normalize_symbol(symbol)
        try:
            r = self.session.get(
                f"{self.base_url}{_MEXC_TICKER_PATH}",
                params={"symbol": inst}, timeout=self.timeout,
            )
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            logging.error(f"MEXC ticker hatasi: {e}")
            return None
        if not payload.get("success"):
            return None
        data = payload.get("data", {})
        # Endpoint hem tek symbol dict hem multi list dondurebiliyor
        if isinstance(data, list):
            data = data[0] if data else {}
        price = data.get("lastPrice") or data.get("fairPrice")
        return float(price) if price else None
