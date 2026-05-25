"""Standalone backtest runner.

Bybit yerine OKX'in public endpoint'inden OHLCV ceker, ardindan models/ict_models
icindeki butun ICT modellerini coklu timeframe'de calistirir, bulunan sinyalleri
ozetler. Hicbir API key gerektirmez.

Kullanim:
    .venv/bin/python backtest_okx.py
    .venv/bin/python backtest_okx.py --symbol ETHUSDT --limit 500
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from utils.okx_fetcher import OKXFetcher
from models.ict_models import (
    PO3Model, BOSFVGModel, CHOCHOBModel, OTEModel,
    SILVERBULLETModel, LONDONREVERSALModel, NYREVERSALModel,
    TURTLESOUPModel, JUDASSWINGModel, SBSModel,
    INDUCEMENTModel, BREADBUTTERModel, MMXMModel, TGIFModel,
    IMBALANCEPLAYModel, SMTDivergenceModel, BPRModel,
)

TIMEFRAMES = [("4h", "HTF"), ("1h", "MTF"), ("15m", "LTF"), ("5m", "STF")]

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


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def fetch_all(fetcher: OKXFetcher, symbol: str, limit: int) -> dict[str, Any]:
    out = {}
    for tf, label in TIMEFRAMES:
        logging.info(f"  -> {label} ({tf}) cekiliyor...")
        df = fetcher.fetch_ohlcv(symbol, tf, limit=limit)
        if df is None or df.empty:
            logging.warning(f"  !! {label} verisi alinamadi")
            continue
        out[tf] = df
        logging.info(f"     {len(df)} mum | {df.index[0]} -> {df.index[-1]}")
    return out


def run_models(data_by_tf: dict, models: dict) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for name, cls in models.items():
        try:
            model = cls()
        except Exception as e:
            logging.warning(f"[{name}] instantiate hatasi: {e}")
            continue
        # min_data_length cogu modelde 20 olsa da, model.detect() icindeki
        # _validate_data default 100 mum bekliyor. Bu yuzden tum veriyi verelim.
        per_tf = {}
        for tf, df in data_by_tf.items():
            if len(df) < 100:
                continue
            try:
                signal = model.detect(df.copy())
            except Exception as e:
                logging.debug(f"[{name}/{tf}] detect hatasi: {e}")
                continue
            if signal:
                per_tf[tf] = signal
        if per_tf:
            results[name] = per_tf
    return results


def print_summary(symbol: str, signals: dict) -> None:
    print()
    print("=" * 60)
    print(f"  Backtest sonuc - {symbol}")
    print("=" * 60)
    if not signals:
        print("  Hicbir modelde sinyal bulunamadi.")
        return
    for model_name in sorted(signals):
        per_tf = signals[model_name]
        tf_list = ", ".join(sorted(per_tf.keys()))
        print(f"  [+] {model_name:<18s} sinyal -> {tf_list}")
    print()
    print(f"  Toplam {len(signals)}/{len(MODELS)} modelde sinyal bulundu.")
    print()


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--limit", type=int, default=300, help="Her TF icin mum sayisi")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    setup_logging(args.verbose)
    logging.info(f"OKX'ten {args.symbol} verisi cekiliyor (limit={args.limit})...")
    fetcher = OKXFetcher()
    data = fetch_all(fetcher, args.symbol, args.limit)
    if not data:
        logging.error("Veri cekilemedi, cikiliyor.")
        return 1
    logging.info(f"Modeller calistiriliyor ({len(MODELS)} model)...")
    signals = run_models(data, MODELS)
    print_summary(args.symbol, signals)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
