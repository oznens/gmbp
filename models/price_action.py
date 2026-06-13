"""
Price action onayları: Engulfing, Pin bar, Liquidity sweep
Harmonik PRZ bölgesine fiyat geldiğinde bu onaylardan en az biri aranır.
"""
import pandas as pd
from dataclasses import dataclass, field


@dataclass
class PASignal:
    confirmations: list = field(default_factory=list)
    direction: str = ""

    @property
    def confirmed(self) -> bool:
        return len(self.confirmations) > 0


def is_bullish_engulfing(prev, cur) -> bool:
    return (prev["close"] < prev["open"]
            and cur["close"] > cur["open"]
            and cur["close"] >= prev["open"]
            and cur["open"] <= prev["close"])


def is_bearish_engulfing(prev, cur) -> bool:
    return (prev["close"] > prev["open"]
            and cur["close"] < cur["open"]
            and cur["close"] <= prev["open"]
            and cur["open"] >= prev["close"])


def is_bullish_pin(cur, wick_ratio: float = 2.0) -> bool:
    body = abs(cur["close"] - cur["open"])
    lower_wick = min(cur["open"], cur["close"]) - cur["low"]
    upper_wick = cur["high"] - max(cur["open"], cur["close"])
    return body > 0 and lower_wick >= wick_ratio * body and lower_wick > upper_wick


def is_bearish_pin(cur, wick_ratio: float = 2.0) -> bool:
    body = abs(cur["close"] - cur["open"])
    upper_wick = cur["high"] - max(cur["open"], cur["close"])
    lower_wick = min(cur["open"], cur["close"]) - cur["low"]
    return body > 0 and upper_wick >= wick_ratio * body and upper_wick > lower_wick


def swept_key_level(df: pd.DataFrame, direction: str, lookback: int = 20) -> bool:
    cur = df.iloc[-1]
    window = df.iloc[-(lookback + 1):-1]
    if direction == "bullish":
        key_low = window["low"].min()
        return cur["low"] < key_low and cur["close"] > key_low
    else:
        key_high = window["high"].max()
        return cur["high"] > key_high and cur["close"] < key_high


def confirm(df: pd.DataFrame, direction: str) -> PASignal:
    sig = PASignal(direction=direction)
    if len(df) < 25:
        return sig
    prev, cur = df.iloc[-2], df.iloc[-1]

    if direction == "bullish":
        if is_bullish_engulfing(prev, cur):
            sig.confirmations.append("engulfing")
        if is_bullish_pin(cur):
            sig.confirmations.append("pin_bar")
        if swept_key_level(df, "bullish"):
            sig.confirmations.append("liquidity_sweep")
    else:
        if is_bearish_engulfing(prev, cur):
            sig.confirmations.append("engulfing")
        if is_bearish_pin(cur):
            sig.confirmations.append("pin_bar")
        if swept_key_level(df, "bearish"):
            sig.confirmations.append("liquidity_sweep")
    return sig
