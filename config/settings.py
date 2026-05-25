import os
from dotenv import load_dotenv

load_dotenv()

# Exchange ayarları (anahtarlar .env dosyasindan okunur)
exchange = {
    "name": os.getenv("EXCHANGE_NAME", "okx"),
    "api_key": os.getenv("OKX_API_KEY") or os.getenv("BYBIT_API_KEY", ""),
    "api_secret": os.getenv("OKX_API_SECRET") or os.getenv("BYBIT_API_SECRET", ""),
    "passphrase": os.getenv("OKX_PASSPHRASE", ""),
    "demo": os.getenv("EXCHANGE_DEMO", "true").lower() == "true",
    "base_url": os.getenv("EXCHANGE_BASE_URL", "https://www.okx.com")
}

# İşlem sembolleri
symbols = [
    "BTCUSDT",  # Normal format
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "DOGEUSDT",
    "XRPUSDT",
    "LINKUSDT",
    "AVAXUSDT"
]

timeframes = {
    "htf": "4h",    # Higher Timeframe
    "mtf": "1h",    # Medium Timeframe
    "ltf": "15m",   # Lower Timeframe
    "stf": "5m",    # Scalp Timeframe
    "scalp": "1m"   # Ultra Scalp
}

# Tarama ayarları
scan_settings = {
    "interval": 60,          # Tarama aralığı (saniye)
    "data_limit": 140,       # Her taramada çekilecek mum sayısı
    "retry_delay": 5,         # Hata durumunda bekleme süresi
    "max_retries": 5          # Maksimum yeniden deneme sayısı
}

# Risk yönetimi
risk_management = {
    "risk_per_trade": 1.0,          # Her trade için risk (%)
    "max_risk_per_day": 5.0,        # Günlük maksimum risk (%)
    "max_open_trades": 3,           # Aynı anda açık olabilecek maksimum trade sayısı
    "min_setup_quality": 0.5,        # Minimum setup kalitesi (0-1 arası)
    "min_risk_reward_ratio": 1.5,    # Minimum risk/ödül oranı
    "max_drawdown": 10.0,           # Maksimum drawdown (%)
    "position_sizing": {
        "min_position": 10,         # USDT cinsinden minimum pozisyon büyüklüğü
        "max_position": 1000        # USDT cinsinden maksimum pozisyon büyüklüğü
    }
}

# Take Profit seviyeleri
take_profit = {
    "tp1": {
        "ratio": 1.5,      # Risk'in 1.5 katı
        "size": 0.3        # Pozisyonun %30'u
    },
    "tp2": {
        "ratio": 2.0,      # Risk'in 2.0 katı
        "size": 0.3        # Pozisyonun %30'u
    },
    "tp3": {
        "ratio": 3.0,      # Risk'in 3.0 katı
        "size": 0.4        # Pozisyonun %40'ı
    }
}

# Model parametreleri
model_params = {
    "silver_bullet": {
        "min_volume_ratio": 1.5,    # Minimum hacim artış oranı
        "min_candle_size": 0.002,   # Minimum mum büyüklüğü (%)
        "max_stop_distance": 0.01   # Maksimum stop mesafesi (%)
    },
    "turtle_soup": {
        "lookback_period": 20,      # Geriye dönük bakılacak mum sayısı
        "breakout_threshold": 0.003  # Kırılım eşiği (%)
    },
    "london_open": {
        "session_start": "08:00",   # London seansı başlangıcı (UTC)
        "session_end": "16:00",     # London seansı bitişi (UTC)
        "pre_session_candles": 3    # Seans öncesi incelenecek mum sayısı
    },
    "ny_reversal": {
        "session_start": "13:00",   # NY seansı başlangıcı (UTC)
        "session_end": "21:00",     # NY seansı bitişi (UTC)
        "min_reversal_size": 0.005  # Minimum dönüş büyüklüğü (%)
    },
    "judas_swing": {
        "swing_threshold": 0.002,   # Swing noktası eşiği (%)
        "min_volume_surge": 1.8     # Minimum hacim artışı
    },
    "po3": {
        "zone_threshold": 0.001,    # Bölge eşiği (%)
        "optimal_ratio": 0.7        # Optimal tepki oranı
    }
}

# Likidite parametreleri
liquidity_params = {
    "void": {
        "min_size": 0.002,         # Minimum boşluk büyüklüğü (%)
        "max_age": 20              # Maksimum yaş (mum sayısı)
    },
    "pool": {
        "density_threshold": 0.8,   # Yoğunluk eşiği
        "min_test_count": 3        # Minimum test sayısı
    },
    "sweep": {
        "volume_threshold": 1.5,    # Hacim eşiği
        "max_rejection": 0.003      # Maksimum ret mesafesi (%)
    }
}

# Hacim analizi parametreleri
volume_params = {
    "profile": {
        "window": 20,              # Analiz penceresi
        "std_multiplier": 2.0      # Standart sapma çarpanı
    },
    "climax": {
        "surge_threshold": 2.0,    # Hacim artış eşiği
        "price_range": 0.005       # Fiyat aralığı (%)
    },
    "delta": {
        "window": 20,              # Delta hesaplama penceresi
        "threshold": 0.7           # Delta eşiği
    }
}

# Logging ayarları
logging = {
    "level": "INFO",
    "file": "logs/trading.log",
    "format": "%(asctime)s - %(levelname)s - %(message)s",
    "max_size": 10 * 1024 * 1024,  # 10 MB
    "backup_count": 5             # Yedek log dosyası sayısı
}

# Dosya yolları
paths = {
    "trade_history": "data/trade_history.json",
    "backtest_results": "data/backtest_results.csv",
    "signals": "data/signals",
    "backtest_data": "data/backtest/",
    "models": "models/",
    "tools": "tools/",
    "utils": "utils/",
    "weekly_levels": "utils/weekly_levels.json"  # Haftalık seviyeler dosyası
}

# Telegram bildirimleri (opsiyonel)
telegram = {
    "enabled": False,
    "bot_token": "",
    "chat_id": "",
    "notifications": {
        "trade_open": True,
        "trade_close": True,
        "error": True,
        "daily_summary": True
    }
}