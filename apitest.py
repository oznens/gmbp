from pybit.unified_trading import HTTP

API_KEY = "J08mKPfD38SXrlKTe8"
API_SECRET = "Ip0Q8vZbHquYgGXjiXzQbwTopzUmEuUXsDAU"

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