"""15m veri indir (Forever Model'in doğal TF'i). data/*_15M_1Y.csv."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.mexc_fetcher import MEXCFetcher

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "AVAXUSDT",
           "ADAUSDT", "LTCUSDT", "LINKUSDT", "ARBUSDT",
           "XRPUSDT", "DOGEUSDT", "OPUSDT"]
DATA_DIR = Path("data")
BARS = 26000  # ~270 gün 15m

f = MEXCFetcher()
for sym in SYMBOLS:
    csv = DATA_DIR / f"{sym}_15M_1Y.csv"
    if csv.exists():
        print(f"{sym} 15M: zaten var"); continue
    print(f"{sym} 15M indiriliyor...", end="", flush=True)
    df = f.fetch_ohlcv(sym, "15m", limit=BARS)
    if df is None or len(df) < 1000:
        print(" HATA"); continue
    df.columns = [c.lower() for c in df.columns]
    df.to_csv(csv)
    print(f" {len(df)} bar")
    time.sleep(0.3)
print("Bitti.")
