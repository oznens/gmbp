"""MEXC public spot market data fetcher.

OKXFetcher ile ayni interface (fetch_ohlcv) -- paper_trade dry-run icin
ikinci bir veri kaynagi olarak kullanilir. Auth gerektirmez.

NOT: MEXC futures (contract.mexc.com) endpoint'i Cloudflare ile bircok
sunucu IP'sini blokluyor. Spot endpoint (api.mexc.com) acik, kullanilan
sembol cifti SPOT pazarindan ceker -- futures'a kiyasla %0.05-0.1 basis
olabilir, signal seviyeleri icin yeterli."""
from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
import pandas as pd
import requests

_MEXC_BASE_URL = "https://api.mexc.com"
_MEXC_KLINE_PATH = "/api/v3/klines"
_MEXC_TICKER_PATH = "/api/v3/ticker/price"

# Trader timeframe -> MEXC interval (spot)
_TF_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "60m", "4h": "4h",
    "1d": "1d", "1w": "1W", "1M": "1M",
}

_TF_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800,
}


def _normalize_symbol(symbol: str) -> str:
    """BTC-USDT / BTC_USDT -> BTCUSDT (MEXC spot format)."""
    return symbol.upper().replace("/", "").replace(":USDT", "").replace("-", "").replace("_", "")


class MEXCFetcher:
    """OHLCV-only MEXC spot client. Auth gerektirmez."""

    def __init__(self, base_url: str = _MEXC_BASE_URL, timeout: int = 10):
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
        """MEXC spot'tan OHLCV cek, eskiden yeniye sirali DataFrame dondur.

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
        # MEXC spot kline tek istekte max 1000 mum doner
        max_per_req = 1000
        end_ms = int(time.time() * 1000)
        all_rows: dict[int, tuple] = {}

        while len(all_rows) < limit:
            need = limit - len(all_rows)
            window = min(need, max_per_req)
            params = {
                "symbol": inst,
                "interval": interval,
                "limit": window,
                "endTime": end_ms,
            }
            try:
                r = self.session.get(self.base_url + _MEXC_KLINE_PATH,
                                     params=params, timeout=self.timeout)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                logging.error(f"MEXC fetch hatasi: {e}")
                return None

            if not isinstance(data, list) or not data:
                break

            for row in data:
                # row format: [openTime, open, high, low, close, volume, closeTime, quoteVol, ...]
                ts = int(row[0])
                if ts in all_rows:
                    continue
                all_rows[ts] = (
                    float(row[1]), float(row[2]), float(row[3]),
                    float(row[4]), float(row[5]),
                    float(row[7]) if len(row) > 7 else 0.0,
                )

            if len(data) < window:
                break
            end_ms = min(all_rows.keys()) - 1
            time.sleep(0.1)

        if not all_rows:
            return None

        sorted_ts = sorted(all_rows.keys())
        df = pd.DataFrame(
            [all_rows[t] for t in sorted_ts],
            columns=["open", "high", "low", "close", "volume", "turnover"],
            index=pd.to_datetime(np.array(sorted_ts, dtype=np.int64), unit="ms"),
        )
        df.index.name = "timestamp"
        return df.tail(limit)

    def get_mark_price(self, symbol: str) -> Optional[float]:
        """MEXC spot ticker'dan son fiyat."""
        inst = _normalize_symbol(symbol)
        try:
            r = self.session.get(self.base_url + _MEXC_TICKER_PATH,
                                 params={"symbol": inst}, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logging.error(f"MEXC ticker hatasi: {e}")
            return None
        price = data.get("price")
        return float(price) if price else None
