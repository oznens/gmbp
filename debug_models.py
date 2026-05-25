"""Debug helper: hangi model neden sinyal vermiyor?

Sliding window halinde her model uzerinde detect cagir, dondurulen
sinyalleri ve loglanan hatalari topla. Cikti her model icin:
  - kac kez cagrildi
  - kac kez exception atti
  - kac kez None dondu
  - hata mesajlarinin top breakdown'i
"""
from __future__ import annotations

import argparse
import io
import logging
import sys
from collections import Counter
from contextlib import redirect_stderr

from utils.okx_fetcher import OKXFetcher
from models.ict_models import (
    PO3Model, BOSFVGModel, CHOCHOBModel, OTEModel,
    SILVERBULLETModel, LONDONREVERSALModel, NYREVERSALModel,
    TURTLESOUPModel, JUDASSWINGModel, SBSModel,
    INDUCEMENTModel, BREADBUTTERModel, MMXMModel, TGIFModel,
    IMBALANCEPLAYModel, SMTDivergenceModel, BPRModel,
)

MODELS = {
    "po3": PO3Model, "bos_fvg": BOSFVGModel, "choch_ob": CHOCHOBModel,
    "ote": OTEModel, "silver_bullet": SILVERBULLETModel,
    "london_reversal": LONDONREVERSALModel, "ny_reversal": NYREVERSALModel,
    "turtle_soup": TURTLESOUPModel, "judas_swing": JUDASSWINGModel,
    "sbs": SBSModel, "inducement": INDUCEMENTModel,
    "bread_butter": BREADBUTTERModel, "mmxm": MMXMModel, "tgif": TGIFModel,
    "imbalance": IMBALANCEPLAYModel, "smt_divergence": SMTDivergenceModel,
    "bpr": BPRModel,
}


class CaptureHandler(logging.Handler):
    """Tum log mesajlarini bir buffer'a topla, sonradan ayristir."""
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--tf", default="1h")
    p.add_argument("--limit", type=int, default=1500)
    p.add_argument("--window", type=int, default=200)
    p.add_argument("--step", type=int, default=10, help="Her N. bar'da test et")
    args = p.parse_args(argv)

    print(f"Veri cekiliyor: {args.symbol} {args.tf} limit={args.limit}...")
    df = OKXFetcher().fetch_ohlcv(args.symbol, args.tf, limit=args.limit)
    if df is None:
        print("Veri alinamadi.")
        return 1
    print(f"  {len(df)} mum, {df.index[0]} -> {df.index[-1]}")
    print(f"Sliding test: window={args.window}, step={args.step}")
    print(f"Toplam pencere: ~{(len(df) - args.window) // args.step}")
    print()

    # Kok logger'a capture handler ekle, baska handler'lari sustur
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    cap = CaptureHandler()
    root.addHandler(cap)
    root.setLevel(logging.DEBUG)

    results: dict[str, dict] = {
        n: {"calls": 0, "exc": 0, "none": 0, "sig": 0, "msgs": Counter()}
        for n in MODELS
    }

    for i in range(args.window, len(df), args.step):
        win = df.iloc[i - args.window:i].copy()
        for name, cls in MODELS.items():
            r = results[name]
            r["calls"] += 1
            cap.records.clear()
            try:
                model = cls()
                sig = model.detect(win)
            except Exception as e:
                r["exc"] += 1
                r["msgs"][f"EXC: {type(e).__name__}: {str(e)[:60]}"] += 1
                continue
            for rec in cap.records:
                if rec.levelno >= logging.WARNING:
                    msg = rec.getMessage()
                    # Stack/dump'lari kisa tut
                    msg = msg.split("\n")[0][:80]
                    r["msgs"][msg] += 1
            if sig is None:
                r["none"] += 1
            else:
                r["sig"] += 1

    # Rapor
    print(f"{'model':<18s}{'calls':>7s}{'sig':>6s}{'none':>6s}{'exc':>5s}  top hata")
    print("-" * 100)
    for name in sorted(results, key=lambda n: -results[n]["sig"]):
        r = results[name]
        top = r["msgs"].most_common(1)
        top_str = ""
        if top:
            msg, cnt = top[0]
            top_str = f"[{cnt}x] {msg}"
        print(f"{name:<18s}{r['calls']:>7d}{r['sig']:>6d}{r['none']:>6d}{r['exc']:>5d}  {top_str}")
    print()
    print("Detayli hata breakdown'i:")
    for name in sorted(results):
        r = results[name]
        if r["sig"] > 0 or not r["msgs"]:
            continue
        print(f"\n  [{name}]  (sig=0)")
        for msg, cnt in r["msgs"].most_common(3):
            print(f"    {cnt:>4d}x  {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
