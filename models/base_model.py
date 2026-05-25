from typing import Dict, Optional, Any
import pandas as pd
from datetime import datetime, time
import pytz
import logging
from abc import ABC, abstractmethod

class ICTModel(ABC):
    """
    ICT Model taban sınıfı.
    Tüm ICT modelleri bu abstract sınıftan türetilmelidir.
    """

    def __init__(self, parameters: dict = None):
        self.parameters = parameters if parameters is not None else {}

    @abstractmethod
    def detect(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """
        Verilen OHLC veri üzerinde ICT modeline özgü tespit işlemlerini gerçekleştirir.
        
        Parametreler:
            ohlc (pd.DataFrame): Mum verilerini içeren DataFrame.
            
        Dönüş:
            pd.DataFrame: Algoritma sinyalleri ve hesaplamaların çıktısı.
        """
        raise NotImplementedError("Bu metot alt sınıflar tarafından implement edilmelidir.")

class BaseModel:
    def __init__(self):
        """Model temel sınıfı"""
        self.config = {
            # Hacim eşikleri
            "volume_threshold": 1.5,      # Normal modeller için hacim eşiği
            "volume_threshold_sb": 1.8,   # Silver Bullet için hacim eşiği
            
            # Momentum ve tepki eşikleri
            "momentum_threshold": 0.8,    # Momentum oranı eşiği
            "reaction_threshold": 0.7,    # Tepki oranı eşiği
            
            # Validasyon parametreleri
            "min_volume": 100,           # Minimum hacim
            "min_volatility": 0.001,     # Minimum volatilite
            "min_liquidity": 1000,       # Minimum likidite
            
            # Zaman dilimleri
            "london_start": 8,           # London seansı başlangıcı (UTC)
            "ny_start": 13,              # NY seansı başlangıcı (UTC)
            "asia_start": 0,             # Asya seansı başlangıcı (UTC)
            
            # Diğer parametreler
            "lookback_period": 20,       # Geriye dönük bakılacak mum sayısı
            "min_setup_quality": 0.7     # Minimum setup kalitesi
        }
        
        # Seans saatleri (UTC)
        self.sessions = {
            "sydney": {
                "start": time(21, 0),  # 21:00 UTC
                "end": time(6, 0)      # 06:00 UTC
            },
            "tokyo": {
                "start": time(0, 0),   # 00:00 UTC
                "end": time(9, 0)      # 09:00 UTC
            },
            "london": {
                "start": time(8, 0),   # 08:00 UTC
                "end": time(16, 0)     # 16:00 UTC
            },
            "new_york": {
                "start": time(13, 0),  # 13:00 UTC
                "end": time(22, 0)     # 22:00 UTC
            }
        }
        
    def is_session_active(self, session: str) -> bool:
        """Seans aktiflik kontrolü"""
        current_hour = pd.Timestamp.now().hour
        
        if session == "london":
            return current_hour >= self.config["london_start"] and current_hour < self.config["ny_start"]
        elif session == "new_york":
            return current_hour >= self.config["ny_start"] and current_hour < self.config["asia_start"] + 24
        elif session == "asia":
            return current_hour >= self.config["asia_start"] and current_hour < self.config["london_start"]
            
        return False
        
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI hesapla"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        return 100 - (100 / (1 + rs))
        
    @staticmethod
    def normalize_price(price: float, decimals: int = 8) -> float:
        """Fiyatı normalize et"""
        return round(float(price), decimals)
        
    def validate_setup(self, data: pd.DataFrame, model_type: str) -> Dict[str, Any]:
        """Setup validasyonu yap"""
        try:
            if data is None or len(data) < self.config["lookback_period"]:
                return {
                    "valid": False, 
                    "reason": "Yetersiz veri",
                    "bos": False,
                    "liquidity": 0,
                    "momentum": False
                }
                
            # Hacim kontrolü
            volume_mean = data["Volume"].mean() if "Volume" in data.columns else 0
            if volume_mean < self.config["min_volume"]:
                return {
                    "valid": False, 
                    "reason": "Düşük hacim",
                    "bos": False,
                    "liquidity": volume_mean,
                    "momentum": False
                }
                
            # Volatilite kontrolü
            volatility = (data["High"] - data["Low"]).mean() / data["Close"].mean()
            if volatility < self.config["min_volatility"]:
                return {
                    "valid": False, 
                    "reason": "Düşük volatilite",
                    "bos": False,
                    "liquidity": volume_mean * data["Close"].mean(),
                    "momentum": False
                }
                
            # BOS kontrolü
            bos_confirmed = self._check_bos(data)
            
            # Momentum kontrolü
            momentum_confirmed = self._check_momentum(data)
            
            # Likidite kontrolü
            liquidity = volume_mean * data["Close"].mean()
            
            return {
                "valid": True,
                "liquidity": liquidity,
                "volatility": volatility,
                "volume": volume_mean,
                "model_type": model_type,
                "bos": bos_confirmed,
                "momentum": momentum_confirmed
            }
            
        except Exception as e:
            logging.error(f"❌ Validasyon hatası: {e}")
            return {
                "valid": False, 
                "reason": str(e),
                "bos": False,
                "liquidity": 0,
                "momentum": False
            }
            
    def _check_liquidity_sweep(self, data: pd.DataFrame) -> bool:
        """Likidite süpürmesi kontrolü"""
        try:
            if len(data) < 5:
                return False
                
            # Son 5 mumu kontrol et
            for i in range(-5, 0):
                # Yukarı süpürme
                if (data['High'].iloc[i] > data['High'].iloc[i-1:i].max() and
                    data['Close'].iloc[i] < data['High'].iloc[i-1:i].max()):
                    return True
                    
                # Aşağı süpürme
                elif (data['Low'].iloc[i] < data['Low'].iloc[i-1:i].min() and
                      data['Close'].iloc[i] > data['Low'].iloc[i-1:i].min()):
                    return True
                    
            return False
            
        except Exception as e:
            logging.error(f"❌ Likidite kontrolü hatası: {e}")
            return False
            
    def _check_bos(self, data: pd.DataFrame) -> bool:
        """Break of Structure kontrolü"""
        try:
            if len(data) < 4:
                return False
                
            # Son 4 mumu kontrol et
            # Bullish BOS
            if (data['Low'].iloc[-2] > data['High'].iloc[-3] and
                data['Low'].iloc[-1] > data['High'].iloc[-2]):
                return True
                
            # Bearish BOS
            elif (data['High'].iloc[-2] < data['Low'].iloc[-3] and
                  data['High'].iloc[-1] < data['Low'].iloc[-2]):
                return True
                
            return False
            
        except Exception as e:
            logging.error(f"❌ BOS kontrolü hatası: {e}")
            return False
            
    def _check_momentum(self, data: pd.DataFrame) -> bool:
        """Momentum kontrolü"""
        try:
            if len(data) < 5:
                return False
                
            # RSI hesapla
            rsi = self.calculate_rsi(data['Close'])
            
            # Son RSI değeri
            last_rsi = rsi.iloc[-1]
            
            # Aşırı alım/satım bölgelerinde değilse momentum var
            return 30 < last_rsi < 70
            
        except Exception as e:
            logging.error(f"❌ Momentum kontrolü hatası: {e}")
            return False 