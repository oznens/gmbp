import os
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")

if not API_KEY or not API_SECRET:
    raise SystemExit("BYBIT_API_KEY / BYBIT_API_SECRET .env dosyasinda tanimli degil.")

client = HTTP(
    api_key=API_KEY,
    api_secret=API_SECRET,
    demo=True  # Bybit Live DEMO kullanıyorsanız demo=True
)

try:
    response = client.get_wallet_balance(accountType="UNIFIED")
    print("✅ API Bağlantı Başarılı! Hesap Bakiyesi:", response)
except Exception as e:
    print("❌ API Bağlantı Hatası:", str(e))