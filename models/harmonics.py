"""
Harmonik patern tespiti: Gartley, Bat, Butterfly, Crab, Shark, Cypher
ZigZag pivotları üzerinden XABCD noktaları bulunur, Fibonacci oranları kontrol edilir.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class HarmonicSignal:
    pattern: str
    direction: str        # "bullish" / "bearish"
    X: float; A: float; B: float; C: float; D: float
    d_index: int
    prz_low: float
    prz_high: float
    score: float


# AB/XA, BC/AB, CD/BC, AD/XA
PATTERN_RATIOS = {
    "Gartley":   {"AB_XA": (0.618, 0.06), "BC_AB": (0.618, 0.27), "CD_BC": (1.418, 0.35), "AD_XA": (0.786, 0.06)},
    "Bat":       {"AB_XA": (0.450, 0.06), "BC_AB": (0.618, 0.27), "CD_BC": (1.918, 0.70), "AD_XA": (0.886, 0.05)},
    "Butterfly": {"AB_XA": (0.786, 0.05), "BC_AB": (0.618, 0.27), "CD_BC": (1.918, 0.70), "AD_XA": (1.270, 0.15)},
    "Crab":      {"AB_XA": (0.500, 0.12), "BC_AB": (0.618, 0.27), "CD_BC": (2.800, 0.85), "AD_XA": (1.618, 0.10)},
    "Shark":     {"AB_XA": (0.700, 0.30), "BC_AB": (1.270, 0.35), "CD_BC": (1.700, 0.55), "AD_XA": (0.930, 0.07)},
    "Cypher":    {"AB_XA": (0.500, 0.12), "BC_AB": (1.272, 0.14), "CD_BC": (0.786, 0.10), "AD_XA": (0.786, 0.05)},
}


def zigzag_pivots(df: pd.DataFrame, depth: int = 5) -> list:
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    pivots = []
    for i in range(depth, n - depth):
        if highs[i] == max(highs[i - depth:i + depth + 1]):
            pivots.append((i, highs[i], "H"))
        elif lows[i] == min(lows[i - depth:i + depth + 1]):
            pivots.append((i, lows[i], "L"))

    cleaned = []
    for p in pivots:
        if cleaned and cleaned[-1][2] == p[2]:
            if (p[2] == "H" and p[1] >= cleaned[-1][1]) or (p[2] == "L" and p[1] <= cleaned[-1][1]):
                cleaned[-1] = p
        else:
            cleaned.append(p)

    if cleaned:
        last_idx, _, last_type = cleaned[-1]
        tail = df.iloc[last_idx + 1:]
        if len(tail) >= 2:
            if last_type == "H":
                i = int(tail["low"].idxmin())
                cleaned.append((i, lows[i], "L"))
            else:
                i = int(tail["high"].idxmax())
                cleaned.append((i, highs[i], "H"))
    return cleaned


def _ratio_ok(value: float, ideal: float, tol: float) -> bool:
    return abs(value - ideal) <= tol


def _score(ratios: dict, spec: dict) -> float:
    scores = []
    for key, (ideal, tol) in spec.items():
        diff = abs(ratios[key] - ideal)
        scores.append(max(0.0, 1.0 - diff / tol))
    return float(np.mean(scores))


def detect_harmonics(df: pd.DataFrame, depth: int = 5, min_score: float = 0.5) -> list:
    pivots = zigzag_pivots(df, depth)
    if len(pivots) < 5:
        return []

    signals = []
    for end in range(len(pivots) - 1, max(3, len(pivots) - 4), -1):
        if end < 4:
            break
        X, A, B, C, D = pivots[end - 4:end + 1]
        types = "".join(p[2] for p in (X, A, B, C, D))
        if types == "LHLHL":
            direction = "bullish"
        elif types == "HLHLH":
            direction = "bearish"
        else:
            continue

        xa = abs(A[1] - X[1])
        ab = abs(B[1] - A[1])
        bc = abs(C[1] - B[1])
        cd = abs(D[1] - C[1])
        ad = abs(D[1] - A[1])
        if min(xa, ab, bc) == 0:
            continue

        ratios = {"AB_XA": ab / xa, "BC_AB": bc / ab, "CD_BC": cd / bc, "AD_XA": ad / xa}

        for name, spec in PATTERN_RATIOS.items():
            if all(_ratio_ok(ratios[k], *spec[k]) for k in spec):
                s = _score(ratios, spec)
                if s < min_score:
                    continue
                prz_center = D[1]
                prz_width = xa * 0.015
                signals.append(HarmonicSignal(
                    pattern=name, direction=direction,
                    X=X[1], A=A[1], B=B[1], C=C[1], D=D[1],
                    d_index=D[0],
                    prz_low=prz_center - prz_width,
                    prz_high=prz_center + prz_width,
                    score=round(s, 3),
                ))
    signals.sort(key=lambda s: (s.d_index, s.score), reverse=True)
    return signals
