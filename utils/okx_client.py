"""OKX REST client (paper / demo trading).

Sadece bizim ihtiyacimiz olan endpoint'leri implemente eder:
  - balance: USDT (paper) bakiyemiz
  - positions: acik pozisyonlar (instId bazli)
  - place_order: market order ac, attached TP/SL ile
  - cancel_orders / close_position: hard reset
Demo modda `x-simulated-trading: 1` header'i ile OKX paper-trading
endpoint'leri kullanilir. Mainnet API key'i yanlislikla calistirilirsa
fiilen para harcayabilirsiniz — demo=True ile baslayin.

OKX docs: https://www.okx.com/docs-v5/en/#overview-demo-trading-services
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, List, Optional

import requests


_BASE_URL = "https://www.okx.com"


class OKXError(RuntimeError):
    """OKX'ten code != '0' donduren cevaplari sarar."""


class OKXClient:
    def __init__(self, api_key: str, api_secret: str, passphrase: str,
                 demo: bool = True, timeout: int = 15) -> None:
        if not (api_key and api_secret and passphrase):
            raise ValueError("OKX api_key/api_secret/passphrase gerekli")
        self.api_key = api_key
        self.api_secret = api_secret.encode()
        self.passphrase = passphrase
        self.demo = demo
        self.timeout = timeout
        self.session = requests.Session()

    # ---------- low-level ----------

    def _ts(self) -> str:
        # ISO8601 with milliseconds, UTC; OKX strict format
        now = dt.datetime.now(dt.timezone.utc)
        return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

    def _sign(self, ts: str, method: str, path: str, body: str) -> str:
        msg = f"{ts}{method}{path}{body}".encode()
        digest = hmac.new(self.api_secret, msg, hashlib.sha256).digest()
        return base64.b64encode(digest).decode()

    def _request(self, method: str, path: str, params: Optional[Dict] = None,
                 body: Optional[Dict] = None) -> Dict[str, Any]:
        method = method.upper()
        body_str = json.dumps(body, separators=(",", ":")) if body else ""
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            path_with_qs = f"{path}?{qs}"
        else:
            path_with_qs = path
        ts = self._ts()
        sign = self._sign(ts, method, path_with_qs, body_str)
        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }
        if self.demo:
            headers["x-simulated-trading"] = "1"
        url = f"{_BASE_URL}{path_with_qs}"
        try:
            r = self.session.request(method, url, headers=headers,
                                     data=body_str if body_str else None,
                                     timeout=self.timeout)
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            raise OKXError(f"HTTP/network error: {e}") from e
        if payload.get("code") not in ("0", 0):
            raise OKXError(f"OKX API error: {payload}")
        return payload

    # ---------- high-level ----------

    def get_balance(self, ccy: str = "USDT") -> float:
        """Hesap bakiyesini (USDT) al."""
        payload = self._request("GET", "/api/v5/account/balance", params={"ccy": ccy})
        for entry in payload.get("data", []):
            for det in entry.get("details", []):
                if det.get("ccy") == ccy:
                    return float(det.get("eq", 0) or 0)
        return 0.0

    def get_positions(self, inst_type: str = "SWAP") -> List[Dict]:
        """Acik swap (perpetual) pozisyonlarini al."""
        payload = self._request("GET", "/api/v5/account/positions",
                                params={"instType": inst_type})
        out = []
        for p in payload.get("data", []):
            if float(p.get("pos", 0) or 0) == 0:
                continue
            out.append({
                "instId": p.get("instId"),
                "side": "LONG" if float(p.get("pos", 0)) > 0 else "SHORT",
                "size": abs(float(p.get("pos", 0))),
                "avg_px": float(p.get("avgPx") or 0),
                "u_pnl": float(p.get("upl") or 0),
                "lev": float(p.get("lev") or 1),
                "mgn_mode": p.get("mgnMode"),
            })
        return out

    def get_instrument(self, inst_id: str, inst_type: str = "SWAP") -> Optional[Dict]:
        """Sembol meta verisi (lot size, tick size vs.)."""
        payload = self._request("GET", "/api/v5/public/instruments",
                                params={"instType": inst_type, "instId": inst_id})
        data = payload.get("data") or []
        return data[0] if data else None

    def get_mark_price(self, inst_id: str, inst_type: str = "SWAP") -> Optional[float]:
        payload = self._request("GET", "/api/v5/public/mark-price",
                                params={"instType": inst_type, "instId": inst_id})
        data = payload.get("data") or []
        if not data:
            return None
        return float(data[0].get("markPx") or 0)

    def place_order(self, inst_id: str, side: str, size: float,
                    sl_price: float, tp_price: float,
                    td_mode: str = "isolated", inst_type: str = "SWAP",
                    pos_side: Optional[str] = None) -> Dict:
        """Market order ac, attached TP/SL ile.

        side: 'buy' (LONG) veya 'sell' (SHORT)
        size: contract count (kontrat sayisi, sembolun lotSz multipl'i)
        sl_price / tp_price: trigger seviyesi
        td_mode: 'isolated' (default; her trade icin ayri margin) veya 'cross'.
                Hesap leverage ayarlari ile uyumlu olmali -- demo OKX'in default
                cross leverage'i 3x oldugu icin isolated 10x daha sermaye-verimli.
        pos_side: 'long' / 'short' (hedge modunda); net modunda None
        """
        body = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side,
            "ordType": "market",
            "sz": str(size),
            "attachAlgoOrds": [{
                "tpTriggerPx": str(tp_price),
                "tpOrdPx": "-1",  # market
                "slTriggerPx": str(sl_price),
                "slOrdPx": "-1",  # market
            }],
        }
        if pos_side:
            body["posSide"] = pos_side
        payload = self._request("POST", "/api/v5/trade/order", body=body)
        data = (payload.get("data") or [{}])[0]
        if data.get("sCode") not in ("0", 0):
            raise OKXError(f"Order rejected: {data}")
        return {"ord_id": data.get("ordId"), "cl_ord_id": data.get("clOrdId"),
                "ts": data.get("ts")}

    def close_position(self, inst_id: str, pos_side: Optional[str] = None,
                       mgn_mode: str = "cross") -> Dict:
        """Acik pozisyonu market'ten kapat."""
        body = {"instId": inst_id, "mgnMode": mgn_mode}
        if pos_side:
            body["posSide"] = pos_side
        payload = self._request("POST", "/api/v5/trade/close-position", body=body)
        return (payload.get("data") or [{}])[0]

    def get_account_config(self) -> Dict:
        """Hesap konfigurasyonunu al (posMode, vs.)."""
        payload = self._request("GET", "/api/v5/account/config")
        return (payload.get("data") or [{}])[0]

    def set_leverage(self, inst_id: str, lever: int = 10,
                     mgn_mode: str = "isolated") -> bool:
        """Instrument icin kaldirac ayarla. Basarisizsa False doner (sessiz)."""
        try:
            self._request("POST", "/api/v5/account/set-leverage", body={
                "instId": inst_id, "lever": str(lever), "mgnMode": mgn_mode,
            })
            return True
        except OKXError as e:
            logging.warning(f"set_leverage {inst_id} lever={lever}: {e}")
            return False

    def get_positions_history(self, inst_id: Optional[str] = None,
                              limit: int = 100) -> List[Dict]:
        """Kapanmis pozisyon gecmisi (son 3 ay).

        Returns: her giris icin {instId, side, avg_open_px, avg_close_px,
                                  realized_pnl, open_ts, close_ts}
        """
        params = {"instType": "SWAP", "limit": str(limit)}
        if inst_id:
            params["instId"] = inst_id
        payload = self._request("GET", "/api/v5/account/positions-history",
                                params=params)
        out = []
        for p in payload.get("data", []):
            try:
                out.append({
                    "instId": p.get("instId"),
                    "side": "LONG" if p.get("direction") == "long" else "SHORT",
                    "avg_open_px": float(p.get("openAvgPx") or 0),
                    "avg_close_px": float(p.get("closeAvgPx") or 0),
                    "realized_pnl": float(p.get("realizedPnl") or 0),
                    "open_ts": int(p.get("cTime") or 0),  # ms
                    "close_ts": int(p.get("uTime") or 0),  # ms
                    "pnl_ratio": float(p.get("pnlRatio") or 0),
                })
            except Exception:
                continue
        return out
