"""Minimal Telegram notification helper.

Sessiz tasarim: token/chat_id yoksa veya istek basarisizsa
sadece debug log atar -- trading loop'unu hic durdurmaz.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests


_TIMEOUT = 5


def send(message: str, token: Optional[str] = None,
         chat_id: Optional[str] = None) -> bool:
    """Telegram'a mesaj gonder. Token/chat_id yoksa sessizce skip."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, data={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }, timeout=_TIMEOUT)
        if not r.ok:
            logging.debug(f"Telegram non-ok: {r.status_code} {r.text[:120]}")
        return r.ok
    except Exception as e:
        logging.debug(f"Telegram exception: {e}")
        return False
