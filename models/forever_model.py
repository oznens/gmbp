"""
Forever Model [Pro+] (Sniper) — toodegrees'in modelinin tam implementasyonu.

Orijinal 3 adımlı sıralı onay sistemi:
  1. IRL  (Internal Range Liquidity) → Fair Value Gap (3-mum imbalance)
  2. SMT  (Smart Money Technique)     → korelasyonlu iki varlık arası diverjans
  3. CISD (Change in State of Delivery)→ önceki yönlü mumu yutan güçlü kapanış +
                                          kısa vadeli likidite süpürmesi
  + ERL  (External Range Liquidity)  → swing high/low (süpürülecek havuz)
  + CE   (Consequent Encroachment)   → FVG'nin %50 orta noktası = limit giriş

Sıralama (LONG örneği):
  a) ERL süpürme: fiyat bir swing low'un altına wick atar (likidite avı)
  b) CISD: güçlü bullish mum önceki bearish mumun gövdesini yutar + kısa vadeli
           low'u süpürür → delivery yön değiştirdi
  c) Bu deplasman bir FVG (IRL) bırakır
  d) SMT: aynı anda eş varlık daha yüksek dip yaptı (süpürülmedi) → diverjans
  e) Giriş: FVG'nin CE'sine (%50) LİMİT emir (geri çekilme beklenir)
  f) SL: süpürülen wick'in altı;  TP: RR katı (varsayılan 2.5R)

SHORT: tam ayna görüntüsü.

Model `detect(df, pair_df)` arayüzüyle çalışır. pair_df, eş korelasyonlu
varlığın AYNI zaman indeksine hizalanmış OHLCV'sidir. SMT için zorunludur;
REQUIRE_SMT=False ile SMT atlanabilir (saf sniper moduna düşer).
"""
from __future__ import annotations
from typing import Optional, Dict
import numpy as np
import pandas as pd


class ForeverModel:
    name = "forever"

    # ── Parametreler ─────────────────────────────────────────────────────────
    SWEEP_PERIOD: int = 30      # ERL swing seviyesi için geriye bakış
    DISP_MULT: float = 0.9      # CISD deplasman gövdesi / ort. gövde eşiği
    SL_BUFFER: float = 0.0015   # süpürülen wick dışı ek tampon (%0.15)
    RR: float = 2.5             # take-profit risk katı
    SMT_LOOKBACK: int = 20      # SMT diverjansı için pivot karşılaştırma penceresi
    REQUIRE_SMT: bool = True    # SMT zorunlu mu (eksiksiz model = True)
    REQUIRE_FVG: bool = True    # IRL/FVG zorunlu mu
    MIN_BARS: int = 60
    MAX_DISP_AGE: int = 3       # deplasman en fazla bu kadar bar önce olabilir
    TP_MODE: str = "erl"        # "erl" = karşı ERL hedefi (gerçek model) | "rr" = sabit RR
    ERL_LOOKBACK: int = 40      # ERL (karşı swing) için geriye bakış

    # ── Yardımcı: SMT diverjansı ─────────────────────────────────────────────
    @staticmethod
    def _smt_divergence(prim_low, prim_high, pair_low, pair_high,
                        direction: str, sweep_idx: int, lookback: int) -> bool:
        """Eş varlıkla diverjans var mı?

        bullish: primary daha düşük dip (süpürdü) yaparken pair daha yüksek dip
                 (süpürmedi) → primary dibi sahte → LONG lehine.
        bearish: primary daha yüksek tepe yaparken pair daha düşük tepe.
        """
        lo = max(0, sweep_idx - lookback)
        if sweep_idx - lo < 4:
            return False
        if direction == "bullish":
            # önceki referans dip (sweep bölgesinden önce)
            split = lo + (sweep_idx - lo) // 2
            prior_idx  = lo + int(np.argmin(prim_low[lo:split]))
            recent_idx = split + int(np.argmin(prim_low[split:sweep_idx + 1]))
            prim_lower_low = prim_low[recent_idx] < prim_low[prior_idx]
            pair_higher_low = pair_low[recent_idx] > pair_low[prior_idx]
            return bool(prim_lower_low and pair_higher_low)
        else:
            split = lo + (sweep_idx - lo) // 2
            prior_idx  = lo + int(np.argmax(prim_high[lo:split]))
            recent_idx = split + int(np.argmax(prim_high[split:sweep_idx + 1]))
            prim_higher_high = prim_high[recent_idx] > prim_high[prior_idx]
            pair_lower_high = pair_high[recent_idx] < pair_high[prior_idx]
            return bool(prim_higher_high and pair_lower_high)

    # ── Ana tespit ───────────────────────────────────────────────────────────
    def detect(self, df: pd.DataFrame,
               pair_df: Optional[pd.DataFrame] = None) -> Optional[Dict]:
        if len(df) < self.MIN_BARS:
            return None

        df = df.reset_index(drop=True)
        o = df["open"].values
        h = df["high"].values
        l = df["low"].values
        c = df["close"].values

        # Eş varlık hizalı dizileri (SMT için)
        if pair_df is not None and len(pair_df) == len(df):
            pdf = pair_df.reset_index(drop=True)
            p_low  = pdf["low"].values
            p_high = pdf["high"].values
        else:
            p_low = p_high = None

        i = len(df) - 1
        avg_body = float(np.mean(np.abs(c[i - 20:i] - o[i - 20:i])))
        if avg_body == 0:
            return None

        # ── LONG akışı ───────────────────────────────────────────────────────
        sig = self._detect_long(o, h, l, c, i, avg_body, p_low, p_high)
        if sig:
            return sig
        # ── SHORT akışı ──────────────────────────────────────────────────────
        return self._detect_short(o, h, l, c, i, avg_body, p_low, p_high)

    def _detect_long(self, o, h, l, c, i, avg_body, p_low, p_high):
        # Deplasman/CISD mumunu d ∈ [i-MAX_DISP_AGE, i-1] içinde ara
        for d in range(i - self.MAX_DISP_AGE, i):
            if d < 2 or d + 1 > i:
                continue

            # ERL swing low (deplasmandan önceki pencere)
            sw_start = max(0, d - self.SWEEP_PERIOD)
            if d - sw_start < 5:
                continue
            swing_low = float(np.min(l[sw_start:d]))

            # (a) ERL süpürme: d veya d-1 wick swing low altına indi
            sweep_idx = None
            for s in (d, d - 1):
                if l[s] < swing_low:
                    sweep_idx = s
                    break
            if sweep_idx is None:
                continue

            # (c)+(CISD) deplasman: güçlü bullish + önceki mumun gövdesini yut
            body = c[d] - o[d]
            if body < avg_body * self.DISP_MULT:
                continue
            cisd = c[d] > o[d] and c[d] > o[d - 1]   # engulfing kapanış
            if not cisd:
                continue

            # (c) FVG/IRL: bullish gap  high[d-1] < low[d+1]
            fvg_low, fvg_high = h[d - 1], l[d + 1]
            has_fvg = fvg_high > fvg_low
            if self.REQUIRE_FVG and not has_fvg:
                continue
            if not has_fvg:   # FVG yoksa deplasman gövdesini bölge al
                fvg_low, fvg_high = o[d], c[d]

            # CE (%50) = limit giriş
            ce = (fvg_low + fvg_high) / 2.0

            # (d) SMT diverjansı
            if self.REQUIRE_SMT:
                if p_low is None:
                    continue
                if not self._smt_divergence(l, h, p_low, p_high, "bullish",
                                            sweep_idx, self.SMT_LOOKBACK):
                    continue

            sl   = l[sweep_idx] * (1 - self.SL_BUFFER)
            entry = ce
            risk = entry - sl
            if risk <= 0 or risk / entry > 0.06:
                continue
            # TP: sabit RR ya da karşı ERL (üstteki swing high) hedefi
            tp = entry + risk * self.RR
            if self.TP_MODE == "erl":
                erl_start = max(0, d - self.ERL_LOOKBACK)
                erl = float(np.max(h[erl_start:d]))
                if erl > entry and (erl - entry) / risk >= 1.5:
                    tp = erl
            return {"direction": "LONG", "entry": round(entry, 6),
                    "stop": round(sl, 6), "tp": round(tp, 6),
                    "fvg": (round(fvg_low, 6), round(fvg_high, 6)),
                    "smt": self.REQUIRE_SMT}
        return None

    def _detect_short(self, o, h, l, c, i, avg_body, p_low, p_high):
        for d in range(i - self.MAX_DISP_AGE, i):
            if d < 2 or d + 1 > i:
                continue

            sw_start = max(0, d - self.SWEEP_PERIOD)
            if d - sw_start < 5:
                continue
            swing_high = float(np.max(h[sw_start:d]))

            sweep_idx = None
            for s in (d, d - 1):
                if h[s] > swing_high:
                    sweep_idx = s
                    break
            if sweep_idx is None:
                continue

            body = o[d] - c[d]
            if body < avg_body * self.DISP_MULT:
                continue
            cisd = c[d] < o[d] and c[d] < o[d - 1]
            if not cisd:
                continue

            # bearish FVG: low[d-1] > high[d+1]
            fvg_high, fvg_low = l[d - 1], h[d + 1]
            has_fvg = fvg_high > fvg_low
            if self.REQUIRE_FVG and not has_fvg:
                continue
            if not has_fvg:
                fvg_high, fvg_low = o[d], c[d]

            ce = (fvg_low + fvg_high) / 2.0

            if self.REQUIRE_SMT:
                if p_high is None:
                    continue
                if not self._smt_divergence(l, h, p_low, p_high, "bearish",
                                            sweep_idx, self.SMT_LOOKBACK):
                    continue

            sl   = h[sweep_idx] * (1 + self.SL_BUFFER)
            entry = ce
            risk = sl - entry
            if risk <= 0 or risk / entry > 0.06:
                continue
            tp = entry - risk * self.RR
            if self.TP_MODE == "erl":
                erl_start = max(0, d - self.ERL_LOOKBACK)
                erl = float(np.min(l[erl_start:d]))
                if erl < entry and (entry - erl) / risk >= 1.5:
                    tp = erl
            return {"direction": "SHORT", "entry": round(entry, 6),
                    "stop": round(sl, 6), "tp": round(tp, 6),
                    "fvg": (round(fvg_low, 6), round(fvg_high, 6)),
                    "smt": self.REQUIRE_SMT}
        return None
