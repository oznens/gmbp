from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import time
import os
from pybit.unified_trading import HTTP

class DataFetcher:
    def __init__(self, api_key: str = None, api_secret: str = None, demo: bool = True):
        """
        Veri çekme sınıfı
        """
        try:
            self.client = HTTP(
                api_key=api_key,
                api_secret=api_secret,
                demo=demo  # testnet yerine demo kullanılıyor
            )
            
            # Bağlantıyı test et
            response = self.client.get_wallet_balance(accountType="UNIFIED")
            if response and "result" in response:
                balance = response["result"]["list"][0]["totalEquity"]
                logging.info("✅ Bybit API bağlantısı başarılı")
                logging.info(f"💰 Bakiye: {balance} USDT")
            else:
                raise Exception("Bakiye bilgisi alınamadı")
                
        except Exception as e:
            logging.error(f"❌ API Bağlantı Hatası: {str(e)}")
            self.client = None
            raise

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> Optional[pd.DataFrame]:
        """OHLCV verilerini çek"""
        try:
            # Sembolü düzenle (Perpetual için)
            if "/" in symbol:
                symbol = f"{symbol}:USDT"  # BTC/USDT:USDT formatına dönüştür
            
            # Şu anki zamanı al (milisaniye cinsinden)
            end_time = int(time.time() * 1000)
            
            # Timeframe'e göre başlangıç zamanını hesapla (dakika cinsinden süreyi kullanıyoruz)
            tf_minutes = {
                "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
                "1h": 60, "2h": 120, "4h": 240, 
                "1d": 1440, "1w": 10080, "1M": 43200
            }
            minutes = tf_minutes.get(timeframe, 1)
            
            # Daha fazla veri için başlangıç zamanını genişlet
            start_time = end_time - (limit * minutes * 60 * 1000 * 2)  # 2 katı süre
            
            # Timeframe'i Bybit'in beklentisine göre dönüştür
            interval = self._convert_timeframe(timeframe)
            
            all_data = []
            remaining_limit = limit
            current_end = end_time
            
            while remaining_limit > 0:
                # Kline verilerini çekmek için v5 API'sini kullanıyoruz
                response = self.client.get_kline(
                    category="linear",
                    symbol=symbol,
                    interval=interval,
                    start=start_time,
                    end=current_end,
                    limit=min(200, remaining_limit)  # Bybit limiti
                )
                
                # Cevabı kontrol et
                if not response or "result" not in response or "list" not in response["result"]:
                    return None
                
                data = response["result"]["list"]
                if not data:
                    break
                    
                all_data.extend(data)
                remaining_limit -= len(data)
                
                if len(data) < 200:  # Son sayfa
                    break
                    
                # Bir sonraki sayfa için son mumun zamanını kullan
                current_end = int(data[-1][0])  # timestamp ilk sütunda
                time.sleep(0.1)  # Rate limit için bekle
            
            if not all_data:
                return None
            
            # DataFrame oluştur
            df = pd.DataFrame(
                all_data,
                columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"]
            )
            
            # Önce tüm sütunları sayısal değerlere çevir
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            
            # Timestamp'i datetime'a çevir
            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(np.int64), unit="ms")
            df.set_index("timestamp", inplace=True)
            
            # Tarihe göre sırala (eskiden yeniye)
            df.sort_index(inplace=True)
            
            # Duplike kayıtları temizle
            df = df[~df.index.duplicated(keep='first')]
            
            if len(df) < limit * 0.7:  # En az %70 veri olmalı
                return None
            
            return df
            
        except Exception as e:
            logging.error(f"❌ Veri çekme hatası ({symbol} {timeframe})")
            return None

    def _convert_timeframe(self, timeframe: str) -> str:
        """
        Timeframe'i Bybit formatına dönüştür
        """
        tf_map = {
            "1m": "1",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "2h": "120",
            "4h": "240",
            "1d": "D",
            "1w": "W",
            "1M": "M"
        }
        return tf_map.get(timeframe, "60")

    def fetch_orderbook(self, symbol: str, limit: int = 100) -> Optional[Dict]:
        """Future emir defteri verilerini çek"""
        try:
            if not self.client:
                raise Exception("Exchange bağlantısı yok")
                
            # Sembolü düzenle
            if not symbol.endswith("USDT"):
                symbol = f"{symbol}USDT"  # BTCUSDT formatı
                
            # Emir defterini çek
            response = self.client.get_orderbook(
                category="linear",
                symbol=symbol,
                limit=limit
            )
            
            if not response or "result" not in response:
                raise Exception(f"Emir defteri alınamadı: {symbol}")
                
            orderbook = response["result"]
            
            return {
                "bids": [[float(price), float(qty)] for price, qty in orderbook["b"]],
                "asks": [[float(price), float(qty)] for price, qty in orderbook["a"]],
                "timestamp": pd.Timestamp.now(),
                "datetime": pd.Timestamp.now().isoformat(),
                "symbol": symbol
            }
            
        except Exception as e:
            logging.error(f"❌ Future emir defteri çekme hatası: {e}")
            logging.error(f"Detay: {str(e)}")
            return None
            
    def fetch_trades(self, symbol: str, limit: int = 100) -> Optional[List[Dict]]:
        """Future son işlemleri çek"""
        try:
            if not self.client:
                raise Exception("Exchange bağlantısı yok")
                
            # Sembolü düzenle
            if not symbol.endswith("USDT"):
                symbol = f"{symbol}USDT"
                
            response = self.client.get_public_trade_history(
                category="linear",
                symbol=symbol,
                limit=limit
            )
            
            if not response or "result" not in response or not response["result"]["list"]:
                raise Exception(f"İşlem verisi alınamadı: {symbol}")
                
            trades = response["result"]["list"]
            
            return [{
                "symbol": symbol,
                "id": trade.get("id", ""),
                "price": float(trade["price"]),
                "amount": float(trade["size"]),
                "cost": float(trade["price"]) * float(trade["size"]),
                "side": trade["side"].lower(),
                "timestamp": pd.Timestamp(int(trade["time"])),
                "datetime": pd.Timestamp(int(trade["time"])).isoformat(),
                "type": "market" if trade.get("type") == "Market" else "limit"
            } for trade in trades]
            
        except Exception as e:
            logging.error(f"❌ Future işlem verisi çekme hatası: {e}")
            logging.error(f"Detay: {str(e)}")
            return None
            
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Future anlık fiyat bilgisi çek"""
        try:
            if self.client is None:
                raise Exception("Exchange bağlantısı yok")
                
            if not symbol.endswith("USDT"):
                symbol = f"{symbol}USDT"
                
            response = self.client.get_tickers(
                category="linear",
                symbol=symbol
            )
            
            if not response or "result" not in response or not response["result"]["list"]:
                raise Exception(f"Ticker verisi alınamadı: {symbol}")
                
            ticker = response["result"]["list"][0]
            
            return {
                "symbol": symbol,
                "bid": float(ticker["bid1Price"]),
                "ask": float(ticker["ask1Price"]),
                "last": float(ticker["lastPrice"]),
                "high": float(ticker["highPrice24h"]),
                "low": float(ticker["lowPrice24h"]),
                "volume": float(ticker["volume24h"]),
                "quoteVolume": float(ticker["turnover24h"]),
                "openInterest": float(ticker.get("openInterest", 0)),
                "fundingRate": float(ticker.get("fundingRate", 0)),
                "nextFundingTime": ticker.get("nextFundingTime", None),
                "timestamp": pd.Timestamp.now(),
                "datetime": pd.Timestamp.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"❌ Future ticker çekme hatası: {e}")
            logging.error(f"Detay: {str(e)}")
            return None