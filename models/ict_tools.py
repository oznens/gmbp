from functools import wraps
import pandas as pd
import numpy as np
from pandas import DataFrame, Series
from datetime import datetime, time
from typing import Dict, Optional, List, Union, Any
import pytz
import logging
from pytz import timezone

def inputvalidator(input_="ohlc"):
    def dfcheck(func):
        @wraps(func)
        def wrap(*args, **kwargs):
            args = list(args)
            # DataFrame argument'i bul; argumanlarda DataFrame yoksa
            # (orn. is_in_killzone() gibi parametresiz/scalar metodlar)
            # decorator'u no-op olarak gec.
            df_idx = next(
                (idx for idx, a in enumerate(args) if isinstance(a, pd.DataFrame)),
                None,
            )
            if df_idx is None:
                return func(*args, **kwargs)
            args[df_idx] = args[df_idx].rename(columns={c: c.lower() for c in args[df_idx].columns})
            inputs = {
                "o": "open",
                "h": "high",
                "l": "low",
                "c": kwargs.get("column", "close").lower(),
                "v": "volume",
            }
            if inputs["c"] != "close":
                kwargs["column"] = inputs["c"]
            for l in input_:
                if inputs[l] not in args[df_idx].columns:
                    raise LookupError(
                        'Must have a dataframe column named "{0}"'.format(inputs[l])
                    )
            return func(*args, **kwargs)
        return wrap
    return dfcheck

def apply(decorator):
    def decorate(cls):
        for attr in cls.__dict__:
            if callable(getattr(cls, attr)):
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls
    return decorate

@apply(inputvalidator(input_="ohlc"))
class smc:
    """Smart Money Concepts (SMC) analiz araçları"""
    __version__ = "0.0.21"

    @classmethod
    def _validate_ohlc(cls, ohlc: pd.DataFrame, min_length: int = 20) -> bool:
        """OHLC veri doğrulama"""
        try:
            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ Geçersiz veri tipi: DataFrame değil")
                return False
                
            if ohlc is None or ohlc.empty:
                logging.error("❌ Veri yok veya boş")
                return False
                
            if len(ohlc) < min_length:
                logging.error(f"❌ Yetersiz veri uzunluğu: {len(ohlc)} < {min_length}")
                return False
                
            required_columns = ["high", "low", "open", "close"]
            if not all(col in ohlc.columns for col in required_columns):
                logging.error("❌ Gerekli sütunlar eksik")
                return False
                
            if ohlc[required_columns].isnull().values.any():
                logging.error("❌ Veride eksik değerler var")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"❌ Veri doğrulama hatası: {e}")
            return False
            
    @classmethod
    def _safe_get_dict_item(cls, data: Dict, key: str, default=None) -> Any:
        """Dictionary elemanlarına güvenli erişim"""
        try:
            if not isinstance(data, dict):
                return default
            return data.get(key, default)
        except Exception:
            return default
            
    @classmethod
    def _safe_get_float(cls, value: Any, default: float = None) -> Optional[float]:
        """Float değere güvenli dönüşüm"""
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def fvg(cls, ohlc: pd.DataFrame, join_consecutive: bool = False) -> Dict:
        """Fair Value Gap tespit fonksiyonu"""
        try:
            # Varsayılan dönüş değeri
            default_return = {
                "type": None,
                "direction": None,
                "price": None,
                "size": 0.0,
                "top": None,
                "bottom": None,
                "timestamp": None
            }

            # Temel kontroller
            if not isinstance(ohlc, pd.DataFrame):
                logging.debug("❌ FVG için geçersiz veri tipi")
                return default_return
                
            if len(ohlc) < 3:  # Minimum 3 mum yeterli
                logging.debug("❌ FVG için yetersiz veri uzunluğu")
                return default_return
                
            if ohlc.empty:
                logging.debug("❌ FVG için boş veri")
                return default_return
                
            try:
                # Son 3 mumu al
                last_candles = ohlc.tail(3)
                if len(last_candles) < 3:
                    logging.debug("❌ FVG için yetersiz mum sayısı")
                    return default_return
                    
                # OHLC değerlerini güvenli şekilde al
                try:
                    c1 = last_candles.iloc[0]
                    c2 = last_candles.iloc[1]
                    c3 = last_candles.iloc[2]
                    
                    c1_low = float(c1["low"])
                    c1_high = float(c1["high"])
                    c3_low = float(c3["low"])
                    c3_high = float(c3["high"])
                except (ValueError, TypeError, IndexError):
                    logging.debug("❌ FVG OHLC değerleri alınamadı")
                    return default_return
                
                # Bullish FVG
                if c1_low > c3_high:
                    fvg_price = (c1_low + c3_high) / 2
                    fvg_size = c1_low - c3_high
                    return {
                        "type": "BULLISH",
                        "direction": 1,
                        "price": float(fvg_price),
                        "size": float(fvg_size),
                        "top": float(c1_low),
                        "bottom": float(c3_high),
                        "timestamp": ohlc.index[-1]
                    }
                    
                # Bearish FVG
                if c1_high < c3_low:
                    fvg_price = (c1_high + c3_low) / 2
                    fvg_size = c3_low - c1_high
                    return {
                        "type": "BEARISH",
                        "direction": -1,
                        "price": float(fvg_price),
                        "size": float(fvg_size),
                        "top": float(c3_low),
                        "bottom": float(c1_high),
                        "timestamp": ohlc.index[-1]
                    }
                    
                # FVG bulunamadıysa son kapanış fiyatını kullan
                try:
                    default_return["price"] = float(c3["close"])
                    default_return["timestamp"] = ohlc.index[-1]
                except (ValueError, TypeError, KeyError):
                    pass
                    
                return default_return
                
            except Exception as e:
                logging.debug(f"❌ FVG hesaplama hatası: {e}")
                return default_return
                
        except Exception as e:
            logging.debug(f"❌ FVG tespit hatası: {e}")
            return default_return

    @classmethod
    def swing_highs_lows(cls, ohlc: pd.DataFrame, swing_length: int = 10) -> Dict:
        """Swing Highs ve Lows tespit fonksiyonu"""
        try:
            # Varsayılan dönüş değeri
            default_return = {"HighLow": [], "Level": []}

            # Temel kontroller
            if not isinstance(ohlc, pd.DataFrame):
                logging.debug("❌ Swing için geçersiz veri tipi")
                return default_return
                
            if len(ohlc) < 3:  # Minimum 3 mum yeterli
                logging.debug("❌ Swing için yetersiz veri uzunluğu")
                return default_return
                
            if ohlc.empty:
                logging.debug("❌ Swing için boş veri")
                return default_return

            try:
                # DataFrame'i resetle
                data_reset = ohlc.reset_index(drop=True)
                swings = {"HighLow": [], "Level": []}
                
                # Son swing_length kadar mumu al
                recent_data = data_reset.tail(swing_length)
                
                # İlk ve son mum hariç kontrol et
                for i in range(1, len(recent_data)-1):
                    try:
                        # Güvenli veri erişimi
                        current_row = recent_data.iloc[i]
                        prev_row = recent_data.iloc[i-1]
                        next_row = recent_data.iloc[i+1]
                        
                        # OHLC değerlerini güvenli şekilde al
                        try:
                            current_high = float(current_row["high"])
                            current_low = float(current_row["low"])
                            prev_high = float(prev_row["high"])
                            prev_low = float(prev_row["low"])
                            next_high = float(next_row["high"])
                            next_low = float(next_row["low"])
                        except (ValueError, TypeError):
                            continue
                        
                        # NaN kontrolü
                        if (pd.isna(current_high) or pd.isna(prev_high) or pd.isna(next_high) or
                            pd.isna(current_low) or pd.isna(prev_low) or pd.isna(next_low)):
                            continue
                        
                        # Swing High
                        if current_high > prev_high and current_high > next_high:
                            swings["HighLow"].append(1)
                            swings["Level"].append(current_high)
                            continue
                            
                        # Swing Low
                        if current_low < prev_low and current_low < next_low:
                            swings["HighLow"].append(-1)
                            swings["Level"].append(current_low)
                            continue
                            
                    except (IndexError, KeyError) as e:
                        logging.debug(f"❌ Swing veri erişim hatası: {e}")
                        continue
                    except Exception as e:
                        logging.debug(f"❌ Swing hesaplama hatası: {e}")
                        continue

                # En az 2 swing noktası yoksa varsayılan değeri döndür
                if len(swings["HighLow"]) < 2 or len(swings["Level"]) < 2:
                    # Son 3 mumdan yapay swing noktaları oluştur
                    try:
                        last_3 = recent_data.tail(3)
                        if len(last_3) == 3:
                            if float(last_3.iloc[-1]["close"]) > float(last_3.iloc[-2]["close"]):
                                swings["HighLow"].extend([1, 1])
                                swings["Level"].extend([
                                    float(last_3.iloc[-2]["high"]),
                                    float(last_3.iloc[-1]["high"])
                                ])
                            else:
                                swings["HighLow"].extend([-1, -1])
                                swings["Level"].extend([
                                    float(last_3.iloc[-2]["low"]),
                                    float(last_3.iloc[-1]["low"])
                                ])
                    except Exception:
                        pass

                return swings
                
            except Exception as e:
                logging.debug(f"❌ Swing hesaplama hatası: {e}")
                return default_return
                
        except Exception as e:
            logging.debug(f"❌ Swing tespit hatası: {e}")
            return default_return

    @classmethod
    def bos_choch(cls, ohlc: pd.DataFrame, swing_highs_lows: Optional[Dict] = None) -> Dict:
        """BOS ve CHoCH tespiti"""
        try:
            # Varsayılan dönüş değeri
            default_return = {
                "bos": {"type": None, "direction": None, "price": None, "timestamp": None},
                "choch": {"type": None, "direction": None, "price": None, "timestamp": None}
            }

            # Veri doğrulama
            if not cls._validate_ohlc(ohlc, min_length=10):  # 20'den 10'a düşürüldü
                logging.debug("❌ BOS/CHoCH için yetersiz veri")
                return default_return
            
            # Swing noktaları yoksa hesapla
            if swing_highs_lows is None:
                swing_highs_lows = cls.swing_highs_lows(ohlc, swing_length=10)  # 20'den 10'a düşürüldü
            
            # Swing noktaları kontrolü
            if not swing_highs_lows or not isinstance(swing_highs_lows, dict):
                logging.debug("❌ BOS/CHoCH için swing noktaları bulunamadı")
                return default_return
            
            # En az 2 swing noktası olmalı (3'ten 2'ye düşürüldü)
            if len(swing_highs_lows.get("HighLow", [])) < 2:
                logging.debug("❌ BOS/CHoCH için yetersiz swing noktası")
                return default_return
            
            # Son swing noktalarını al
            last_swings = swing_highs_lows["HighLow"][-3:] if len(swing_highs_lows["HighLow"]) >= 3 else swing_highs_lows["HighLow"]
            last_levels = swing_highs_lows["Level"][-3:] if len(swing_highs_lows["Level"]) >= 3 else swing_highs_lows["Level"]
            
            # BOS tespiti
            bos = {"type": None, "direction": None, "price": None, "timestamp": None}
            if len(last_swings) >= 2:  # En az 2 swing noktası varsa
                if all(x == 1 for x in last_swings[-2:]):  # Son 2 swing yüksek
                    bos = {
                        "type": "BOS",
                        "direction": 1,
                        "price": max(last_levels[-2:]),
                        "timestamp": ohlc.index[-1]
                    }
                elif all(x == -1 for x in last_swings[-2:]):  # Son 2 swing düşük
                    bos = {
                        "type": "BOS",
                        "direction": -1,
                        "price": min(last_levels[-2:]),
                        "timestamp": ohlc.index[-1]
                    }
            
            # CHoCH tespiti
            choch = {"type": None, "direction": None, "price": None, "timestamp": None}
            if len(last_swings) >= 2:  # En az 2 swing noktası varsa
                if last_swings[-1] == 1 and last_swings[-2] == -1:  # Bullish CHoCH
                    choch = {
                        "type": "CHoCH",
                        "direction": 1,
                        "price": last_levels[-1],
                        "timestamp": ohlc.index[-1]
                    }
                elif last_swings[-1] == -1 and last_swings[-2] == 1:  # Bearish CHoCH
                    choch = {
                        "type": "CHoCH",
                        "direction": -1,
                        "price": last_levels[-1],
                        "timestamp": ohlc.index[-1]
                    }
            
            return {"bos": bos, "choch": choch}
            
        except Exception as e:
            logging.debug(f"❌ BOS/CHoCH tespit hatası: {e}")
            return default_return

    @classmethod
    def ob(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Order Block tespit fonksiyonu"""
        try:
            # Varsayılan dönüş değeri
            default_return = {
                "type": None,
                "direction": None,
                "price": None,
                "sl_level": None,
                "timestamp": None
            }

            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ OB için geçersiz veri tipi")
                return default_return
                
            if len(ohlc) < 3:  # Minimum 3 mum yeterli
                logging.error("❌ OB için yetersiz veri uzunluğu")
                return default_return
                
            if ohlc.empty:
                logging.error("❌ OB için boş veri")
                return default_return
                
            # Son 3 mumu al
            last_3 = ohlc.tail(3).copy()
            
            try:
                # Son mumun yönünü belirle
                last_candle = last_3.iloc[-1]
                prev_candle = last_3.iloc[-2]
                first_candle = last_3.iloc[0]
                
                # Bullish OB
                if (float(last_candle["close"]) > float(last_candle["open"]) and  # Yeşil mum
                    float(prev_candle["low"]) < float(first_candle["low"])):  # Önceki düşük kırıldı
                    return {
                        "type": "BULLISH_OB",
                        "direction": 1,
                        "price": float(last_candle["low"]),
                        "sl_level": float(last_candle["low"]) * 0.995,  # %0.5 altı
                        "timestamp": ohlc.index[-1]
                    }
                # Bearish OB    
                elif (float(last_candle["close"]) < float(last_candle["open"]) and  # Kırmızı mum
                      float(prev_candle["high"]) > float(first_candle["high"])):  # Önceki yüksek kırıldı
                    return {
                        "type": "BEARISH_OB",
                        "direction": -1,
                        "price": float(last_candle["high"]),
                        "sl_level": float(last_candle["high"]) * 1.005,  # %0.5 üstü
                        "timestamp": ohlc.index[-1]
                    }
                    
                # OB bulunamadıysa son kapanış fiyatını kullan
                default_return["price"] = float(last_candle["close"])
                default_return["timestamp"] = ohlc.index[-1]
                return default_return
                
            except (IndexError, ValueError) as e:
                logging.error(f"❌ OB hesaplama hatası: {e}")
                return default_return
                
        except Exception as e:
            logging.error(f"❌ OB tespit hatası: {e}")
            return default_return

    @classmethod
    def is_ob_tested(cls, ob: Dict) -> bool:
        """Order Block test edildi mi kontrolü"""
        try:
            if not isinstance(ob, dict) or "price" not in ob:
                logging.error("❌ Geçersiz OB verisi")
                return False
                
            try:
                # Fiyat OB seviyesine yakın mı?
                current_price = float(ob.get("current_price", 0))
                ob_price = float(ob["price"])
                
                return abs(current_price - ob_price) / ob_price < 0.001  # %0.1 tolerans
                
            except (TypeError, ValueError) as e:
                logging.error(f"❌ OB test hesaplama hatası: {e}")
                return False
                
        except Exception as e:
            logging.error(f"❌ OB test kontrolü hatası: {e}")
            return False
            
    @classmethod
    def confirm_momentum(cls, ohlc: pd.DataFrame) -> bool:
        """Momentum teyidi"""
        try:
            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ Momentum için geçersiz veri tipi")
                return False
                
            if len(ohlc) < 14:
                logging.error("❌ Momentum için yetersiz veri uzunluğu")
                return False
                
            try:
                # RSI hesapla
                delta = ohlc["close"].astype(float).diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                # Son RSI değeri
                last_rsi = float(rsi.iloc[-1])
                
                # Aşırı alım/satım bölgelerinde değilse momentum var
                return 30 < last_rsi < 70
                
            except Exception as e:
                logging.error(f"❌ RSI hesaplama hatası: {e}")
                return False
                
        except Exception as e:
            logging.error(f"❌ Momentum teyidi hatası: {e}")
            return False
            
    @classmethod
    def is_in_killzone(cls) -> bool:
        """Killzone saati kontrolü"""
        try:
            now = datetime.now(pytz.timezone('US/Eastern'))
            current_time = now.time()
            
            # London Session: 02:00-05:00 EST
            # NY Session: 07:00-10:00 EST
            london_start = time(2, 0)
            london_end = time(5, 0)
            ny_start = time(7, 0)
            ny_end = time(10, 0)
            
            return ((london_start <= current_time <= london_end) or
                    (ny_start <= current_time <= ny_end))
                    
        except Exception as e:
            logging.error(f"❌ Killzone kontrolü hatası: {e}")
            return False
            
    @classmethod
    def is_in_london_session(cls) -> bool:
        """Londra seansında mı kontrolü"""
        try:
            now = datetime.now(pytz.timezone('US/Eastern'))
            current_time = now.time()
            
            # London Session: 02:00-11:00 EST
            london_start = time(2, 0)
            london_end = time(11, 0)
            
            return london_start <= current_time <= london_end
            
        except Exception as e:
            logging.error(f"❌ Londra seansı kontrolü hatası: {e}")
            return False
            
    @classmethod
    def is_in_ny_killzone(cls) -> bool:
        """NY Killzone'da mı kontrolü"""
        try:
            now = datetime.now(pytz.timezone('US/Eastern'))
            current_time = now.time()
            
            # NY Killzone: 07:00-10:00 EST
            ny_start = time(7, 0)
            ny_end = time(10, 0)
            
            return ny_start <= current_time <= ny_end
            
        except Exception as e:
            logging.error(f"❌ NY Killzone kontrolü hatası: {e}")
            return False

    @classmethod
    def retracements(cls, ohlc: DataFrame, swing_highs_lows: DataFrame) -> Series:
        """
        Retracement
        Swing high veya low'dan yapılan geri çekilmenin yüzdesini hesaplar.
        ...
        """
        # Fonksiyon içeriğini ihtiyaca göre doldurun.
        return pd.Series()  # Örneğin geçici boş seri döndürür

    @classmethod
    def detect_bos(cls, ohlc: pd.DataFrame) -> Dict:
        """BOS tespit fonksiyonu"""
        try:
            # Varsayılan dönüş değeri
            default_return = {
                "direction": None,
                "price": None,
                "timestamp": None,
                "type": None
            }

            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ BOS için geçersiz veri tipi")
                return default_return
                
            if len(ohlc) < 3:  # Minimum 3 mum yeterli
                logging.error("❌ BOS için yetersiz veri uzunluğu")
                return default_return
                
            if ohlc.empty:
                logging.error("❌ BOS için boş veri")
                return default_return
                
            # Son 3 mumu al
            recent_data = ohlc.tail(3).copy()
            
            try:
                # Son mumların verilerini al
                last_candle = recent_data.iloc[-1]
                prev_candle = recent_data.iloc[-2]
                first_candle = recent_data.iloc[0]
                
                last_close = float(last_candle["close"])
                last_high = float(last_candle["high"])
                last_low = float(last_candle["low"])
                prev_high = float(prev_candle["high"])
                prev_low = float(prev_candle["low"])
                first_high = float(first_candle["high"])
                first_low = float(first_candle["low"])
                
                # Bullish BOS
                if last_low > prev_high and prev_low > first_high:
                    return {
                        "direction": 1,
                        "price": last_low,
                        "timestamp": recent_data.index[-1],
                        "type": "BULLISH_BOS"
                    }
                    
                # Bearish BOS
                elif last_high < prev_low and prev_high < first_low:
                    return {
                        "direction": -1,
                        "price": last_high,
                        "timestamp": recent_data.index[-1],
                        "type": "BEARISH_BOS"
                    }
                    
                # BOS bulunamadıysa varsayılan değerleri döndür
                default_return["price"] = last_close  # Son kapanış fiyatını kullan
                default_return["timestamp"] = recent_data.index[-1]
                return default_return
                
            except (IndexError, ValueError) as e:
                logging.error(f"❌ BOS hesaplama hatası: {e}")
                return default_return
                
        except Exception as e:
            logging.error(f"❌ BOS tespit hatası: {e}")
            return default_return

    @classmethod
    def detect_liquidity_sweep(cls, ohlc: pd.DataFrame, levels: Optional[Dict] = None) -> Dict:
        """Likidite süpürme tespit fonksiyonu"""
        try:
            # Temel veri doğrulama
            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ Likidite sweep için geçersiz veri tipi")
                return {
                    "type": None,
                    "price": None,
                    "timestamp": None,
                    "direction": None,
                    "strength": 0.0
                }
                
            if len(ohlc) < 3:  # En az 3 mum gerekli
                logging.error("❌ Likidite sweep için yetersiz veri uzunluğu")
                return {
                    "type": None,
                    "price": None,
                    "timestamp": ohlc.index[-1] if not ohlc.empty else None,
                    "direction": None,
                    "strength": 0.0
                }
                
            # Son mum verilerini al
            try:
                last_high = float(ohlc["high"].iloc[-1])
                last_low = float(ohlc["low"].iloc[-1])
                last_close = float(ohlc["close"].iloc[-1])
                last_timestamp = ohlc.index[-1]
            except (IndexError, ValueError) as e:
                logging.error(f"❌ Son mum verisi alınamadı: {e}")
                return {
                    "type": None,
                    "price": None,
                    "timestamp": None,
                    "direction": None,
                    "strength": 0.0
                }
                
            # Eğer levels verilmemişse, önceki gün seviyelerini kullan
            if levels is None:
                prev_day = ohlc[ohlc.index.date < ohlc.index[-1].date()].tail(1)
                if not prev_day.empty:
                    levels = {
                        "high": float(prev_day["high"].iloc[0]),
                        "low": float(prev_day["low"].iloc[0])
                    }
                else:
                    # Önceki gün verisi yoksa swing noktalarını kullan
                    swings = cls.swing_highs_lows(ohlc)
                    if swings and swings["HighLow"] and swings["Level"]:
                        levels = {
                            "high": max(swings["Level"]),
                            "low": min(swings["Level"])
                        }
            
            # Likidite seviyelerini kontrol et
            if levels and isinstance(levels, dict):
                high_level = levels.get("high")
                low_level = levels.get("low")
                
                if high_level is not None and last_high > float(high_level):
                    return {
                        "type": "HIGH_SWEEP",
                        "price": float(high_level),
                        "timestamp": last_timestamp,
                        "direction": -1,
                        "strength": (last_high - float(high_level)) / float(high_level)
                    }
                    
                elif low_level is not None and last_low < float(low_level):
                    return {
                        "type": "LOW_SWEEP",
                        "price": float(low_level),
                        "timestamp": last_timestamp,
                        "direction": 1,
                        "strength": (float(low_level) - last_low) / float(low_level)
                    }
            
            # Eğer sweep bulunamadıysa varsayılan değerleri döndür
            return {
                "type": None,
                "price": last_close,  # Son kapanış fiyatını kullan
                "timestamp": last_timestamp,
                "direction": None,
                "strength": 0.0
            }
            
        except Exception as e:
            logging.error(f"❌ Likidite sweep tespit hatası: {e}")
            return {
                "type": None,
                "price": None,
                "timestamp": None,
                "direction": None,
                "strength": 0.0
            }

    @classmethod
    def detect_choch(cls, ohlc: pd.DataFrame) -> Dict:
        """CHoCH tespit fonksiyonu"""
        try:
            # Varsayılan dönüş değeri
            default_return = {
                "direction": None,
                "level": None,
                "timestamp": None,
                "type": None
            }

            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ CHoCH için geçersiz veri tipi")
                return default_return
                
            if len(ohlc) < 4:  # Minimum 4 mum yeterli
                logging.error("❌ CHoCH için yetersiz veri uzunluğu")
                return default_return
                
            if ohlc.empty:
                logging.error("❌ CHoCH için boş veri")
                return default_return
                
            # Son 4 mumu al
            recent_data = ohlc.tail(4).copy()
            
            try:
                # Son mumların verilerini al
                last_candle = recent_data.iloc[-1]
                prev_candle = recent_data.iloc[-2]
                third_candle = recent_data.iloc[-3]
                fourth_candle = recent_data.iloc[-4]
                
                last_close = float(last_candle["close"])
                last_high = float(last_candle["high"])
                last_low = float(last_candle["low"])
                
                # Bullish CHoCH
                if (last_low > float(prev_candle["high"]) and
                    float(prev_candle["high"]) < float(third_candle["low"]) and
                    float(third_candle["low"]) > float(fourth_candle["high"])):
                    return {
                        "direction": 1,
                        "level": last_low,
                        "timestamp": recent_data.index[-1],
                        "type": "BULLISH_CHOCH"
                    }
                    
                # Bearish CHoCH
                elif (last_high < float(prev_candle["low"]) and
                      float(prev_candle["low"]) > float(third_candle["high"]) and
                      float(third_candle["high"]) < float(fourth_candle["low"])):
                    return {
                        "direction": -1,
                        "level": last_high,
                        "timestamp": recent_data.index[-1],
                        "type": "BEARISH_CHOCH"
                    }
                    
                # CHoCH bulunamadıysa varsayılan değerleri döndür
                default_return["level"] = last_close
                default_return["timestamp"] = recent_data.index[-1]
                return default_return
                
            except (IndexError, ValueError) as e:
                logging.error(f"❌ CHoCH hesaplama hatası: {e}")
                return default_return
                
        except Exception as e:
            logging.error(f"❌ CHoCH tespit hatası: {e}")
            return default_return

    @classmethod
    def detect_fvg(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Fair Value Gap tespit fonksiyonu"""
        try:
            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ FVG için geçersiz veri tipi")
                return None
                
            if len(ohlc) < 3:  # Minimum 3 mum yeterli
                logging.error("❌ FVG için yetersiz veri uzunluğu")
                return None
                
            if ohlc.empty:
                logging.error("❌ FVG için boş veri")
                return None
                
            try:
                # Son üç mumu al
                last_candles = ohlc.tail(3)
                if len(last_candles) < 3:
                    logging.error("❌ FVG için yetersiz mum sayısı")
                    return None
                    
                # FVG hesapla
                c1 = last_candles.iloc[0]
                c2 = last_candles.iloc[1]
                c3 = last_candles.iloc[2]
                
                # Bullish FVG
                if float(c1["low"]) > float(c3["high"]):
                    fvg_price = (float(c1["low"]) + float(c3["high"])) / 2
                    fvg_size = float(c1["low"]) - float(c3["high"])
                    return {
                        "type": "BULLISH",
                        "direction": 1,
                        "price": float(fvg_price),
                        "size": float(fvg_size),
                        "top": float(c1["low"]),
                        "bottom": float(c3["high"]),
                        "timestamp": ohlc.index[-1]
                    }
                    
                # Bearish FVG
                if float(c1["high"]) < float(c3["low"]):
                    fvg_price = (float(c1["high"]) + float(c3["low"])) / 2
                    fvg_size = float(c3["low"]) - float(c1["high"])
                    return {
                        "type": "BEARISH",
                        "direction": -1,
                        "price": float(fvg_price),
                        "size": float(fvg_size),
                        "top": float(c3["low"]),
                        "bottom": float(c1["high"]),
                        "timestamp": ohlc.index[-1]
                    }
                    
                # Eğer FVG bulunamazsa varsayılan değerleri döndür
                return {
                    "type": None,
                    "direction": None,
                    "price": float(c3["close"]),
                    "size": 0.0,
                    "top": None,
                    "bottom": None,
                    "timestamp": ohlc.index[-1]
                }
                
            except (IndexError, ValueError) as e:
                logging.error(f"❌ FVG hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ FVG tespit hatası: {e}")
            return None

    @classmethod
    def detect_asia_range(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Asia Range tespiti"""
        try:
            if len(ohlc) < 20:
                logging.error("❌ Asia Range için yetersiz veri")
                return None
                
            # Asia seansı verileri (21:00-06:00 EST)
            asia_data = ohlc[ohlc.index.hour.isin(range(21, 24)) | ohlc.index.hour.isin(range(0, 6))].copy()
            
            if len(asia_data) < 2:
                logging.error("❌ Asia seansı verisi yetersiz")
                return None
                
            try:
                high = float(asia_data["high"].max())
                low = float(asia_data["low"].min())
                range_size = high - low
                
                return {
                    "high": high,
                    "low": low,
                    "range_size": range_size,
                    "is_valid": range_size > 0,
                    "liquidity": {"high": high, "low": low},
                    "timestamp": ohlc.index[-1]
                }
            except Exception as e:
                logging.error(f"❌ Asia Range hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Asia Range tespit hatası: {e}")
            return None
            
    @classmethod
    def is_in_london_open(cls) -> bool:
        """Londra açılış kontrolü (02:00-03:00 EST)"""
        try:
            now = datetime.now(pytz.timezone('US/Eastern'))
            current_time = now.time()
            
            return time(2, 0) <= current_time <= time(3, 0)
            
        except Exception as e:
            logging.error(f"❌ Londra açılış kontrolü hatası: {e}")
            return False
            
    @classmethod
    def is_in_silver_bullet_time(cls) -> bool:
        """Silver Bullet saati kontrolü"""
        try:
            now = datetime.now(pytz.timezone('US/Eastern'))
            current_hour = now.hour
            current_minute = now.minute
            
            # 3AM-4AM, 10AM-11AM, and 2PM-3PM New York time
            silver_bullet_times = [
                (3, 4),   # 3AM-4AM
                (10, 11), # 10AM-11AM
                (14, 15)  # 2PM-3PM
            ]
            
            for start_hour, end_hour in silver_bullet_times:
                if start_hour <= current_hour < end_hour:
                    return True
                    
            return False
            
        except Exception as e:
            logging.error(f"❌ Silver Bullet saat kontrolü hatası: {e}")
            return False
            
    @classmethod
    def detect_london_session_trend(cls, ohlc: pd.DataFrame) -> Dict:
        """Londra seansı trend tespiti"""
        try:
            # Varsayılan dönüş değeri
            default_return = {
                "direction": None,
                "open": None,
                "close": None,
                "high": None,
                "low": None,
                "liquidity": {"high": None, "low": None},
                "timestamp": None
            }

            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ Londra seansı için geçersiz veri tipi")
                return default_return
                
            if len(ohlc) < 3:  # Minimum 3 mum yeterli
                logging.error("❌ Londra seansı için yetersiz veri uzunluğu")
                return default_return
                
            if ohlc.empty:
                logging.error("❌ Londra seansı için boş veri")
                return default_return
                
            try:
                # Son kapanış fiyatı
                last_candle = ohlc.iloc[-1]
                
                # Varsayılan değerleri doldur
                default_return["open"] = float(last_candle["open"])
                default_return["close"] = float(last_candle["close"])
                default_return["high"] = float(last_candle["high"])
                default_return["low"] = float(last_candle["low"])
                default_return["timestamp"] = ohlc.index[-1]
                default_return["liquidity"]["high"] = float(last_candle["high"])
                default_return["liquidity"]["low"] = float(last_candle["low"])
                default_return["direction"] = 1 if float(last_candle["close"]) > float(last_candle["open"]) else -1
                
                # Londra seansı verileri (02:00-05:00 EST)
                london_data = ohlc[ohlc.index.hour.isin(range(2, 5))].copy()
                
                if len(london_data) >= 2:
                    # Trend yönü
                    direction = 1 if float(london_data["close"].iloc[-1]) > float(london_data["open"].iloc[0]) else -1
                    
                    return {
                        "direction": direction,
                        "open": float(london_data["open"].iloc[0]),
                        "close": float(london_data["close"].iloc[-1]),
                        "high": float(london_data["high"].max()),
                        "low": float(london_data["low"].min()),
                        "liquidity": {
                            "high": float(london_data["high"].max()),
                            "low": float(london_data["low"].min())
                        },
                        "timestamp": ohlc.index[-1]
                    }
                    
                return default_return
                
            except (IndexError, ValueError) as e:
                logging.error(f"❌ Londra trend hesaplama hatası: {e}")
                return default_return
                
        except Exception as e:
            logging.error(f"❌ Londra trend tespit hatası: {e}")
            return default_return

    @classmethod
    def detect_silver_bullet(cls, ohlc: pd.DataFrame) -> Dict:
        """Silver Bullet pattern tespiti"""
        try:
            # Varsayılan dönüş değeri
            default_return = {
                "type": None,
                "direction": None,
                "entry": None,
                "stop": None,
                "timestamp": None
            }

            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ Silver Bullet için geçersiz veri tipi")
                return default_return
                
            if len(ohlc) < 3:  # Minimum 3 mum yeterli
                logging.error("❌ Silver Bullet için yetersiz veri uzunluğu")
                return default_return
                
            if ohlc.empty:
                logging.error("❌ Silver Bullet için boş veri")
                return default_return
                
            try:
                # Son kapanış fiyatı
                last_candle = ohlc.iloc[-1]
                
                # Varsayılan değerleri doldur
                default_return["entry"] = float(last_candle["close"])
                default_return["timestamp"] = ohlc.index[-1]
                
                # Son 3 mumu al
                recent_data = ohlc.tail(3).copy()
                
                if len(recent_data) < 3:
                    return default_return
                    
                # Son mumların verilerini al
                last_candle = recent_data.iloc[-1]
                prev_candle = recent_data.iloc[-2]
                first_candle = recent_data.iloc[0]
                
                # Bullish Silver Bullet
                if (float(last_candle["low"]) > float(prev_candle["high"]) and
                    float(prev_candle["low"]) > float(first_candle["high"])):
                    return {
                        "type": "BULLISH_SILVER_BULLET",
                        "direction": 1,
                        "entry": float(last_candle["close"]),
                        "stop": float(first_candle["low"]),
                        "timestamp": recent_data.index[-1]
                    }
                    
                # Bearish Silver Bullet
                elif (float(last_candle["high"]) < float(prev_candle["low"]) and
                      float(prev_candle["high"]) < float(first_candle["low"])):
                    return {
                        "type": "BEARISH_SILVER_BULLET",
                        "direction": -1,
                        "entry": float(last_candle["close"]),
                        "stop": float(first_candle["high"]),
                        "timestamp": recent_data.index[-1]
                    }
                    
                return default_return
                
            except (IndexError, ValueError) as e:
                logging.error(f"❌ Silver Bullet hesaplama hatası: {e}")
                return default_return
                
        except Exception as e:
            logging.error(f"❌ Silver Bullet tespit hatası: {e}")
            return default_return

    @classmethod
    def is_friday(cls) -> bool:
        """Cuma günü kontrolü"""
        try:
            now = datetime.now(pytz.timezone('US/Eastern'))
            return now.weekday() == 4  # 4 = Cuma
            
        except Exception as e:
            logging.error(f"❌ Cuma günü kontrolü hatası: {e}")
            return False

    @staticmethod
    def detect_support_resistance(ohlc: pd.DataFrame) -> Optional[Dict]:
        """Destek/Direnç seviyesi tespiti"""
        try:
            if len(ohlc) < 20:
                return None
                
            # Son 20 mumun pivot noktaları
            pivots = []
            for i in range(1, len(ohlc)-1):
                # Pivot High
                if (float(ohlc["high"].iloc[i]) > float(ohlc["high"].iloc[i-1]) and 
                    float(ohlc["high"].iloc[i]) > float(ohlc["high"].iloc[i+1])):
                    pivots.append({
                        "type": "RESISTANCE",
                        "price": float(ohlc["high"].iloc[i]),
                        "strength": 1.0,
                        "timestamp": ohlc.index[i]
                    })
                # Pivot Low    
                elif (float(ohlc["low"].iloc[i]) < float(ohlc["low"].iloc[i-1]) and
                      float(ohlc["low"].iloc[i]) < float(ohlc["low"].iloc[i+1])):
                    pivots.append({
                        "type": "SUPPORT",
                        "price": float(ohlc["low"].iloc[i]),
                        "strength": 1.0,
                        "timestamp": ohlc.index[i]
                    })
                    
            if not pivots:
                return None
                
            # En güçlü seviyeyi bul
            strongest = max(pivots, key=lambda x: x["strength"])
            
            return strongest
            
        except Exception as e:
            logging.error(f"❌ Destek/Direnç tespit hatası: {e}")
            return None
            
    @staticmethod
    def has_accumulated_liquidity(ohlc: pd.DataFrame, sr_level: Dict) -> bool:
        """Likidite birikimi kontrolü"""
        try:
            if not sr_level or "price" not in sr_level:
                return False
                
            # Son 5 mumda likidite birikimi var mı?
            last_5 = ohlc.tail(5)
            sr_price = float(sr_level["price"])
            
            if sr_level["type"] == "RESISTANCE":
                touches = sum(1 for high in last_5["high"].astype(float) if abs(high - sr_price) / sr_price < 0.001)
                return touches >= 2
            else:  # SUPPORT
                touches = sum(1 for low in last_5["low"].astype(float) if abs(low - sr_price) / sr_price < 0.001)
                return touches >= 2
                
        except Exception as e:
            logging.error(f"❌ Likidite birikimi kontrolü hatası: {e}")
            return False
            
    @staticmethod
    def detect_current_trend(ohlc: pd.DataFrame) -> Optional[Dict]:
        """Mevcut trend tespiti"""
        try:
            if len(ohlc) < 20:
                return None
                
            # 20 periyot SMA
            sma = ohlc["close"].astype(float).rolling(window=20).mean()
            
            # Son kapanış
            last_close = float(ohlc["close"].iloc[-1])
            last_sma = float(sma.iloc[-1])
            
            # Trend yönü
            if last_close > last_sma:
                return {
                    "direction": 1,
                    "strength": float((last_close - last_sma) / last_sma),
                    "sma": last_sma,
                    "timestamp": ohlc.index[-1]
                }
            else:
                return {
                    "direction": -1,
                    "strength": float((last_sma - last_close) / last_sma),
                    "sma": last_sma,
                    "timestamp": ohlc.index[-1]
                }
                
        except Exception as e:
            logging.error(f"❌ Trend tespit hatası: {e}")
            return None

    @staticmethod
    def detect_inducement_levels(ohlc: pd.DataFrame) -> Optional[Dict]:
        """Yeni likidite seviyeleri tespiti"""
        try:
            if len(ohlc) < 10:
                return None
                
            levels = []
            
            # Son 10 mumda oluşan yeni yüksek/düşükler
            for i in range(1, len(ohlc)-1):
                # Yeni yüksek
                if float(ohlc["high"].iloc[i]) > float(ohlc["high"].iloc[i-1:i].max()):
                    levels.append({
                        "type": "HIGH",
                        "price": float(ohlc["high"].iloc[i]),
                        "strength": 1.0,
                        "timestamp": ohlc.index[i]
                    })
                # Yeni düşük    
                elif float(ohlc["low"].iloc[i]) < float(ohlc["low"].iloc[i-1:i].min()):
                    levels.append({
                        "type": "LOW",
                        "price": float(ohlc["low"].iloc[i]),
                        "strength": 1.0,
                        "timestamp": ohlc.index[i]
                    })
                    
            if not levels:
                return None
                
            return {"levels": levels, "timestamp": ohlc.index[-1]}
            
        except Exception as e:
            logging.error(f"❌ İndükleme seviyeleri tespit hatası: {e}")
            return None
            
    @staticmethod
    def detect_accumulation_phase(ohlc: pd.DataFrame) -> Optional[Dict]:
        """Likidite toplama fazı tespiti"""
        try:
            if len(ohlc) < 20:
                return None
                
            # Son 20 mumun range'i
            high = float(ohlc["high"].max())
            low = float(ohlc["low"].min())
            range_size = high - low
            
            # Range içindeki mumlar
            candles_in_range = ohlc[(ohlc["high"].astype(float) <= high) & (ohlc["low"].astype(float) >= low)]
            
            # Range geçerli mi?
            is_valid = len(candles_in_range) >= 10 and range_size > 0
            
            if not is_valid:
                return None
            
            return {
                "high": high,
                "low": low,
                "range_size": range_size,
                "levels": [
                    {"price": high, "type": "HIGH"},
                    {"price": low, "type": "LOW"}
                ],
                "timestamp": ohlc.index[-1]
            }
            
        except Exception as e:
            logging.error(f"❌ Akümülasyon fazı tespit hatası: {e}")
            return None
            
    @staticmethod
    def get_weekly_levels(ohlc: pd.DataFrame) -> Dict:
        """Haftalık önemli seviyeleri hesaplar:
        Verilen OHLC verisini weekly olarak resample edip, en az 2 tam hafta varsa önceki haftanın seviyelerini döndürür.
        """
        try:
            default_return = {
                "high": None,
                "low": None,
                "open": None,
                "close": None,
                "timestamp": None
            }
            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ Haftalık seviyeler için geçersiz veri tipi")
                return default_return
            if ohlc.empty:
                logging.error("❌ Haftalık seviyeler için boş veri")
                return default_return

            # OHLC verisini haftalık olarak yeniden örnekleyelim
            weekly = ohlc.resample("W").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last"
            })

            if weekly.empty:
                logging.error("❌ Haftalık resample sonucu boş")
                return default_return

            # Eğer haftalık veride en az 2 tam hafta varsa, önceki haftanın seviyelerini kullanalım
            if len(weekly) >= 2:
                prev_week = weekly.iloc[-2]
                return {
                    "high": float(prev_week["high"]),
                    "low": float(prev_week["low"]),
                    "open": float(prev_week["open"]),
                    "close": float(prev_week["close"]),
                    "timestamp": prev_week.name
                }
            else:
                # Eğer yeterli hafta yoksa, mevcut haftanın verilerini döndür
                latest_week = weekly.iloc[-1]
                return {
                    "high": float(latest_week["high"]),
                    "low": float(latest_week["low"]),
                    "open": float(latest_week["open"]),
                    "close": float(latest_week["close"]),
                    "timestamp": latest_week.name
                }
        except Exception as e:
            logging.error(f"❌ Haftalık seviye tespit hatası: {e}")
            return default_return

    @staticmethod
    def get_strongest_sr_level(ohlc: pd.DataFrame) -> Optional[float]:
        """En güçlü destek/direnç seviyesi"""
        try:
            sr_level = smc.detect_support_resistance(ohlc)
            if not sr_level:
                return None
                
            return float(sr_level["price"])
            
        except Exception as e:
            logging.error(f"❌ En güçlü S/R tespit hatası: {e}")
            return None
            
    @staticmethod
    def get_trend_target(ohlc: pd.DataFrame, direction: int) -> Optional[float]:
        """Trend hedef seviyesi"""
        try:
            if len(ohlc) < 20:
                return None
                
            # Son kapanış
            last_close = float(ohlc["close"].iloc[-1])
            
            if direction == 1:  # LONG
                # Yukarıdaki en yakın swing high
                highs = ohlc["high"][ohlc["high"].astype(float) > last_close]
                if len(highs) > 0:
                    return float(highs.min())
            else:  # SHORT
                # Aşağıdaki en yakın swing low
                lows = ohlc["low"][ohlc["low"].astype(float) < last_close]
                if len(lows) > 0:
                    return float(lows.max())
                    
            return None
            
        except Exception as e:
            logging.error(f"❌ Trend hedefi tespit hatası: {e}")
            return None

    @staticmethod
    def get_previous_day_levels(ohlc: pd.DataFrame) -> Optional[Dict]:
        """Önceki günün yüksek/düşük seviyelerini tespit et"""
        try:
            # Önceki günün verilerini al
            prev_day = ohlc[ohlc.index.date < ohlc.index[-1].date()].tail(1)
            if len(prev_day) == 0:
                return None
                
            prev_high = float(prev_day["high"].iloc[0])
            prev_low = float(prev_day["low"].iloc[0])
                
            return {
                "high": prev_high,
                "low": prev_low,
                "levels": [
                    {"price": prev_high, "type": "HIGH"},
                    {"price": prev_low, "type": "LOW"}
                ],
                "timestamp": ohlc.index[-1]
            }
            
        except Exception as e:
            logging.error(f"❌ Önceki gün seviyeleri tespit hatası: {e}")
            return None

    @classmethod
    def detect_london_session_liquidity(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Londra seansı likidite seviyelerini tespit et"""
        try:
            # Londra seansı verileri (02:00-05:00 EST)
            london_data = ohlc[ohlc.index.hour.isin(range(2, 5))].copy()
            
            if len(london_data) < 2:
                logging.error("❌ Londra seansı verisi yetersiz")
                return None
                
            try:
                high = float(london_data["high"].max())
                low = float(london_data["low"].min())
                close = float(london_data["close"].iloc[-1])
                
                return {
                    "high": high,
                    "low": low,
                    "level": close,
                    "type": "HIGH" if close > high * 0.5 + low * 0.5 else "LOW",
                    "levels": [
                        {"price": high, "type": "HIGH"},
                        {"price": low, "type": "LOW"}
                    ],
                    "timestamp": ohlc.index[-1]
                }
            except Exception as e:
                logging.error(f"❌ Londra likidite hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Londra likidite tespit hatası: {e}")
            return None
            
    @classmethod
    def get_ny_close_target(cls, ohlc: pd.DataFrame) -> Optional[float]:
        """NY kapanış hedefini tespit et"""
        try:
            # NY kapanış saati verileri (14:00-16:00 EST)
            close_data = ohlc[ohlc.index.hour.isin(range(14, 16))].copy()
            
            if len(close_data) < 2:
                logging.error("❌ NY kapanış verisi yetersiz")
                return None
                
            try:
                # Kapanış hedefi (VWAP kullanılabilir)
                typical_price = (close_data["high"].astype(float) + close_data["low"].astype(float) + close_data["close"].astype(float)) / 3
                volume = close_data["volume"].astype(float) if "volume" in close_data.columns else pd.Series(1, index=close_data.index)
                vwap = float((typical_price * volume).sum() / volume.sum())
                
                return vwap
            except Exception as e:
                logging.error(f"❌ NY kapanış hedefi hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ NY kapanış hedefi tespit hatası: {e}")
            return None
            
    @classmethod
    def detect_judas_swing(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Judas Swing tespiti"""
        try:
            if len(ohlc) < 4:
                logging.error("❌ Judas Swing için yetersiz veri")
                return None
                
            # Son 4 mum
            last_4 = ohlc.tail(4).copy()
            
            if len(last_4) < 4:
                logging.error("❌ Judas Swing için yetersiz mum sayısı")
                return None
                
            try:
                # Yukarı yönlü Judas Swing
                if (float(last_4["high"].iloc[-2]) > float(last_4["high"].iloc[-3]) and
                    float(last_4["close"].iloc[-1]) < float(last_4["low"].iloc[-2])):
                    return {
                        "type": "BULLISH_JUDAS",
                        "direction": 1,
                        "price": float(last_4["high"].iloc[-2]),
                        "entry": float(last_4["close"].iloc[-1]),
                        "timestamp": ohlc.index[-1]
                    }
                # Aşağı yönlü Judas Swing    
                elif (float(last_4["low"].iloc[-2]) < float(last_4["low"].iloc[-3]) and
                      float(last_4["close"].iloc[-1]) > float(last_4["high"].iloc[-2])):
                    return {
                        "type": "BEARISH_JUDAS",
                        "direction": -1,
                        "price": float(last_4["low"].iloc[-2]),
                        "entry": float(last_4["close"].iloc[-1]),
                        "timestamp": ohlc.index[-1]
                    }
                    
                return None
                
            except Exception as e:
                logging.error(f"❌ Judas Swing hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Judas Swing tespit hatası: {e}")
            return None

    @classmethod
    def detect_fake_breakout(cls, ohlc: pd.DataFrame, asia_range: Optional[Dict] = None) -> Optional[Dict]:
        """Sahte kırılım tespiti"""
        try:
            if not isinstance(ohlc, pd.DataFrame) or len(ohlc) < 20:
                logging.error("❌ Sahte kırılım için geçersiz veri")
                return None
                
            if asia_range is None:
                asia_range = cls.detect_asia_range(ohlc)
                
            if not isinstance(asia_range, dict) or "high" not in asia_range or "low" not in asia_range:
                logging.error("❌ Geçersiz Asia Range verisi")
                return None
                
            try:
                # Son kapanış
                last_close = float(ohlc["close"].iloc[-1])
                last_high = float(ohlc["high"].iloc[-1])
                last_low = float(ohlc["low"].iloc[-1])
                
                # Range kırılımı ve geri dönüş kontrolü
                if (last_high > float(asia_range["high"]) and last_close < float(asia_range["high"])):
                    return {
                        "type": "FAKE_BREAKOUT_HIGH",
                        "direction": -1,
                        "price": float(asia_range["high"]),
                        "extreme": last_high,
                        "timestamp": ohlc.index[-1]
                    }
                elif (last_low < float(asia_range["low"]) and last_close > float(asia_range["low"])):
                    return {
                        "type": "FAKE_BREAKOUT_LOW",
                        "direction": 1,
                        "price": float(asia_range["low"]),
                        "extreme": last_low,
                        "timestamp": ohlc.index[-1]
                    }
                    
                return None
                
            except Exception as e:
                logging.error(f"❌ Sahte kırılım hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Sahte kırılım tespit hatası: {e}")
            return None

    @classmethod
    def get_previous_day_liquidity(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Önceki günün likidite seviyelerini tespit et"""
        try:
            # Önceki günün verilerini al
            prev_day = ohlc[ohlc.index.date < ohlc.index[-1].date()].tail(1)
            if len(prev_day) == 0:
                logging.error("❌ Önceki gün verisi bulunamadı")
                return None
                
            try:
                prev_high = float(prev_day["high"].iloc[0])
                prev_low = float(prev_day["low"].iloc[0])
                prev_close = float(prev_day["close"].iloc[0])
                
                return {
                    "high": prev_high,
                    "low": prev_low,
                    "close": prev_close,
                    "levels": [
                        {"price": prev_high, "type": "HIGH"},
                        {"price": prev_low, "type": "LOW"}
                    ],
                    "timestamp": ohlc.index[-1]
                }
                
            except Exception as e:
                logging.error(f"❌ Önceki gün likidite hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Önceki gün likidite tespit hatası: {e}")
            return None

    @classmethod
    def get_intraday_liquidity_level(cls, ohlc: pd.DataFrame) -> Optional[float]:
        """Gün içi likidite seviyesini tespit et"""
        try:
            if len(ohlc) < 20:
                logging.error("❌ Gün içi likidite için yetersiz veri")
                return None
                
            try:
                # VWAP hesapla
                typical_price = (ohlc["high"].astype(float) + ohlc["low"].astype(float) + ohlc["close"].astype(float)) / 3
                volume = ohlc["volume"].astype(float) if "volume" in ohlc.columns else pd.Series(1, index=ohlc.index)
                vwap = float((typical_price * volume).sum() / volume.sum())
                
                # Son kapanış
                last_close = float(ohlc["close"].iloc[-1])
                
                # VWAP'a göre likidite seviyesi
                if last_close > vwap:
                    return float(ohlc["high"].max())  # Yukarı likidite
                else:
                    return float(ohlc["low"].min())  # Aşağı likidite
                    
            except Exception as e:
                logging.error(f"❌ Gün içi likidite hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Gün içi likidite tespit hatası: {e}")
            return None

    @classmethod
    def get_ny_session_target(cls, ohlc: pd.DataFrame) -> Optional[float]:
        """NY seansı hedef seviyesini tespit et"""
        try:
            # NY seansı verileri (07:00-16:00 EST)
            ny_data = ohlc[ohlc.index.hour.isin(range(7, 16))].copy()
            
            if len(ny_data) < 2:
                logging.error("❌ NY seansı verisi yetersiz")
                return None
                
            try:
                # Son kapanış
                last_close = float(ohlc["close"].iloc[-1])
                
                # NY seansı yüksek/düşük
                ny_high = float(ny_data["high"].max())
                ny_low = float(ny_data["low"].min())
                
                # Hedef seviye
                if last_close > (ny_high + ny_low) / 2:
                    return ny_high  # Yukarı hedef
                else:
                    return ny_low  # Aşağı hedef
                    
            except Exception as e:
                logging.error(f"❌ NY hedef hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ NY hedef tespit hatası: {e}")
            return None

    @classmethod
    def is_in_ny_open(cls) -> bool:
        """NY açılış kontrolü (07:00-08:00 EST)"""
        try:
            now = datetime.now(pytz.timezone('US/Eastern'))
            current_time = now.time()
            
            return time(7, 0) <= current_time <= time(8, 0)
            
        except Exception as e:
            logging.error(f"❌ NY açılış kontrolü hatası: {e}")
            return False

    @classmethod
    def check_correlation_divergence(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """BTC-ETH korelasyon uyumsuzluğu kontrolü"""
        try:
            if len(ohlc) < 20:
                logging.error("❌ Korelasyon için yetersiz veri")
                return None
                
            try:
                # Son 20 periyot için korelasyon
                returns = ohlc["close"].astype(float).pct_change()
                correlation = returns.rolling(window=20).corr(returns)
                
                # Son korelasyon değeri
                last_corr = float(correlation.iloc[-1])
                
                return {
                    "is_divergent": abs(last_corr) < 0.5,  # Korelasyon zayıfsa uyumsuzluk var
                    "correlation": last_corr,
                    "timestamp": ohlc.index[-1]
                }
                
            except Exception as e:
                logging.error(f"❌ Korelasyon hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Korelasyon kontrolü hatası: {e}")
            return None

    @classmethod
    def detect_htf_imbalance(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Yüksek zaman diliminde dengesizlik tespiti"""
        try:
            if len(ohlc) < 100:
                logging.error("❌ HTF dengesizlik için yetersiz veri")
                return None
                
            try:
                # 4H veriye dönüştür
                htf_data = ohlc.resample("4H").agg({
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last"
                })
                
                if len(htf_data) < 3:
                    logging.error("❌ HTF verisi yetersiz")
                    return None
                    
                # Son 3 mum
                last_3 = htf_data.tail(3)
                
                # Dengesizlik kontrolü
                if float(last_3["low"].iloc[-1]) > float(last_3["high"].iloc[-2]):
                    return {
                        "type": "BULLISH_IMBALANCE",
                        "direction": 1,
                        "price": float(last_3["low"].iloc[-1]),
                        "extreme": float(last_3["high"].iloc[-2]),
                        "timestamp": ohlc.index[-1]
                    }
                elif float(last_3["high"].iloc[-1]) < float(last_3["low"].iloc[-2]):
                    return {
                        "type": "BEARISH_IMBALANCE",
                        "direction": -1,
                        "price": float(last_3["high"].iloc[-1]),
                        "extreme": float(last_3["low"].iloc[-2]),
                        "timestamp": ohlc.index[-1]
                    }
                    
                return None
                
            except Exception as e:
                logging.error(f"❌ HTF dengesizlik hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ HTF dengesizlik tespit hatası: {e}")
            return None

    @classmethod
    def is_filling_imbalance(cls, ohlc: pd.DataFrame, imbalance: Dict) -> bool:
        """Dengesizlik dolduruluyor mu kontrolü"""
        try:
            if not isinstance(imbalance, dict) or "price" not in imbalance:
                logging.error("❌ Geçersiz dengesizlik verisi")
                return False
                
            try:
                # Son kapanış
                last_close = float(ohlc["close"].iloc[-1])
                imbalance_price = float(imbalance["price"])
                
                # Fiyat dengesizlik seviyesine yakın mı?
                return abs(last_close - imbalance_price) / imbalance_price < 0.001  # %0.1 tolerans
                
            except Exception as e:
                logging.error(f"❌ Dengesizlik doldurma hesaplama hatası: {e}")
                return False
                
        except Exception as e:
            logging.error(f"❌ Dengesizlik doldurma kontrolü hatası: {e}")
            return False

    @classmethod
    def is_returning_to_ob_fvg(cls, ohlc: pd.DataFrame, level: Dict) -> bool:
        """OB/FVG'ye dönüş kontrolü"""
        try:
            if not isinstance(level, dict) or "price" not in level:
                logging.error("❌ Geçersiz seviye verisi")
                return False
                
            try:
                # Son kapanış
                last_close = float(ohlc["close"].iloc[-1])
                level_price = float(level["price"])
                
                # Fiyat seviyeye yakın mı?
                return abs(last_close - level_price) / level_price < 0.001  # %0.1 tolerans
                
            except Exception as e:
                logging.error(f"❌ OB/FVG dönüş hesaplama hatası: {e}")
                return False
                
        except Exception as e:
            logging.error(f"❌ OB/FVG dönüş kontrolü hatası: {e}")
            return False

    @classmethod
    def detect_bpr(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """BPR (Balanced Price Range) tespiti"""
        try:
            if len(ohlc) < 20:
                logging.error("❌ BPR için yetersiz veri")
                return None
                
            try:
                # Son 20 mumun range'i
                high = float(ohlc["high"].max())
                low = float(ohlc["low"].min())
                range_size = high - low
                
                # Range içindeki mumlar
                candles_in_range = ohlc[(ohlc["high"].astype(float) <= high) & 
                                      (ohlc["low"].astype(float) >= low)]
                
                # Range geçerli mi?
                is_valid = len(candles_in_range) >= 10 and range_size > 0
                
                if not is_valid:
                    return None
                    
                return {
                    "high": high,
                    "low": low,
                    "range_size": range_size,
                    "is_valid": True,
                    "timestamp": ohlc.index[-1]
                }
                
            except Exception as e:
                logging.error(f"❌ BPR hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ BPR tespit hatası: {e}")
            return None

    @classmethod
    def check_balance_duration(cls, ohlc: pd.DataFrame, bpr: Dict) -> bool:
        """BPR denge süresi kontrolü"""
        try:
            if not isinstance(bpr, dict) or "high" not in bpr or "low" not in bpr:
                logging.error("❌ Geçersiz BPR verisi")
                return False
                
            try:
                # Range içindeki mumlar
                candles_in_range = ohlc[(ohlc["high"].astype(float) <= float(bpr["high"])) & 
                                      (ohlc["low"].astype(float) >= float(bpr["low"]))]
                
                # En az 10 mum range içinde olmalı
                return len(candles_in_range) >= 10
                
            except Exception as e:
                logging.error(f"❌ BPR süre hesaplama hatası: {e}")
                return False
                
        except Exception as e:
            logging.error(f"❌ BPR süre kontrolü hatası: {e}")
            return False
            
    @classmethod
    def detect_key_levels(cls, ohlc: pd.DataFrame) -> Dict:
        """Önemli fiyat seviyelerini tespit eder"""
        try:
            # Varsayılan dönüş değeri
            default_return = {
                "price": None,
                "strength": None,
                "type": None,
                "timestamp": None
            }

            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ Önemli seviyeler için geçersiz veri tipi")
                return default_return
                
            if len(ohlc) < 3:  # Minimum 3 mum yeterli
                logging.error("❌ Önemli seviyeler için yetersiz veri uzunluğu")
                return default_return
                
            if ohlc.empty:
                logging.error("❌ Önemli seviyeler için boş veri")
                return default_return
                
            try:
                # Son kapanış fiyatı
                last_close = float(ohlc["close"].iloc[-1])
                
                # Pivot noktaları
                highs = ohlc["high"].astype(float)
                lows = ohlc["low"].astype(float)
                
                # En yakın destek/direnç seviyesi
                if len(highs) >= 3 and len(lows) >= 3:
                    resistance = float(highs.nlargest(3).iloc[-1])
                    support = float(lows.nsmallest(3).iloc[-1])
                    
                    # Fiyata en yakın seviyeyi bul
                    if abs(last_close - resistance) < abs(last_close - support):
                        return {
                            "price": resistance,
                            "strength": 1.0,
                            "type": "RESISTANCE",
                            "timestamp": ohlc.index[-1]
                        }
                    else:
                        return {
                            "price": support,
                            "strength": 1.0,
                            "type": "SUPPORT",
                            "timestamp": ohlc.index[-1]
                        }
                        
                # Varsayılan değerleri döndür
                default_return["price"] = last_close
                default_return["timestamp"] = ohlc.index[-1]
                return default_return
                
            except (IndexError, ValueError) as e:
                logging.error(f"❌ Önemli seviye hesaplama hatası: {e}")
                return default_return
                
        except Exception as e:
            logging.error(f"❌ Önemli seviye tespit hatası: {e}")
            return default_return

    @classmethod
    def detect_mmxm_pattern(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """MMXM pattern tespiti"""
        try:
            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ MMXM için geçersiz veri tipi")
                return None
                
            if len(ohlc) < 4:
                logging.error("❌ MMXM için yetersiz veri uzunluğu")
                return None
                
            # Son 4 mumu al
            recent_data = ohlc.tail(4)
            
            # MMXM pattern kontrolü
            if recent_data.iloc[0]["high"] > recent_data.iloc[1]["high"] and \
               recent_data.iloc[1]["high"] < recent_data.iloc[2]["high"] and \
               recent_data.iloc[2]["high"] > recent_data.iloc[3]["high"]:
                return {
                    "type": "BEARISH_MMXM",
                    "direction": -1,
                    "price": float(recent_data.iloc[3]["high"]),
                    "timestamp": recent_data.index[-1]
                }
                
            if recent_data.iloc[0]["low"] < recent_data.iloc[1]["low"] and \
               recent_data.iloc[1]["low"] > recent_data.iloc[2]["low"] and \
               recent_data.iloc[2]["low"] < recent_data.iloc[3]["low"]:
                return {
                    "type": "BULLISH_MMXM",
                    "direction": 1,
                    "price": float(recent_data.iloc[3]["low"]),
                    "timestamp": recent_data.index[-1]
                }
                
            return None
            
        except Exception as e:
            logging.error(f"❌ MMXM tespit hatası: {e}")
            return None
            
    @classmethod
    def get_weekly_levels(cls, ohlc: pd.DataFrame) -> Dict:
        """Haftalık önemli seviyeleri hesaplar:
        Verilen OHLC verisini weekly olarak resample edip, en az 2 tam hafta varsa önceki haftanın seviyelerini döndürür.
        """
        try:
            default_return = {
                "high": None,
                "low": None,
                "open": None,
                "close": None,
                "timestamp": None
            }
            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ Haftalık seviyeler için geçersiz veri tipi")
                return default_return
            if ohlc.empty:
                logging.error("❌ Haftalık seviyeler için boş veri")
                return default_return

            # OHLC verisini haftalık olarak yeniden örnekleyelim
            weekly = ohlc.resample("W").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last"
            })

            if weekly.empty:
                logging.error("❌ Haftalık resample sonucu boş")
                return default_return

            # Eğer haftalık veride en az 2 tam hafta varsa, önceki haftanın seviyelerini kullanalım
            if len(weekly) >= 2:
                prev_week = weekly.iloc[-2]
                return {
                    "high": float(prev_week["high"]),
                    "low": float(prev_week["low"]),
                    "open": float(prev_week["open"]),
                    "close": float(prev_week["close"]),
                    "timestamp": prev_week.name
                }
            else:
                # Eğer yeterli hafta yoksa, mevcut haftanın verilerini döndür
                latest_week = weekly.iloc[-1]
                return {
                    "high": float(latest_week["high"]),
                    "low": float(latest_week["low"]),
                    "open": float(latest_week["open"]),
                    "close": float(latest_week["close"]),
                    "timestamp": latest_week.name
                }
        except Exception as e:
            logging.error(f"❌ Haftalık seviye tespit hatası: {e}")
            return default_return

    @classmethod
    def detect_london_sweep(cls, ohlc: pd.DataFrame) -> Dict:
        """Londra seansı likidite süpürme tespiti"""
        try:
            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ Londra seansı için geçersiz veri tipi")
                return {}
                
            if len(ohlc) < 20:
                logging.error("❌ Londra seansı için yetersiz veri uzunluğu")
                return {}
                
            if ohlc.empty:
                logging.error("❌ Londra seansı için boş veri")
                return {}
                
            # Londra seansı saatleri (EST)
            london_start_hour = 2
            london_end_hour = 6
            
            # Londra seansı verilerini filtrele
            london_session = ohlc.between_time(f"{london_start_hour:02d}:00", f"{london_end_hour:02d}:00", include_start=True, include_end=False)
            
            if len(london_session) < 2:
                logging.error("❌ Londra seansı için yetersiz veri")
                return {}
                
            # Son mum verilerini al
            try:
                last_close = float(london_session["close"].iloc[-1])
                london_high = float(london_session["high"].max())
                london_low = float(london_session["low"].min())
            except (IndexError, ValueError) as e:
                logging.error(f"❌ Londra seansı verileri alınamadı: {e}")
                return {}
                
            # Londra seansı yüksek ve düşük sweep kontrolü
            if last_close > london_high:
                return {
                    "type": "LONDON_HIGH_SWEEP",
                    "price": london_high,
                    "timestamp": london_session.index[-1]
                }
            elif last_close < london_low:
                return {
                    "type": "LONDON_LOW_SWEEP",
                    "price": london_low,
                    "timestamp": london_session.index[-1]
                }
            else:
                return {}
                
        except Exception as e:
            logging.error(f"❌ Londra seansı sweep tespit hatası: {e}")
            return {}

    @classmethod
    def detect_liquidity_buildup(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Likidite birikimi tespiti"""
        try:
            if len(ohlc) < 20:
                logging.error("❌ Likidite birikimi için yetersiz veri")
                return None
                
            try:
                # Son 5 mumda yüksek/düşük kontrolü
                last_5 = ohlc.tail(5)
                
                high_touches = sum(1 for i in range(1, len(last_5)) 
                                 if abs(last_5["high"].iloc[i] - last_5["high"].iloc[i-1]) / last_5["high"].iloc[i-1] < 0.001)
                                 
                low_touches = sum(1 for i in range(1, len(last_5))
                                if abs(last_5["low"].iloc[i] - last_5["low"].iloc[i-1]) / last_5["low"].iloc[i-1] < 0.001)
                                
                if high_touches >= 2:
                    return {
                        "side": "HIGH",
                        "volume": float(last_5["volume"].sum()) if "volume" in last_5.columns else 1.0,
                        "timestamp": ohlc.index[-1]
                    }
                elif low_touches >= 2:
                    return {
                        "side": "LOW",
                        "volume": float(last_5["volume"].sum()) if "volume" in last_5.columns else 1.0,
                        "timestamp": ohlc.index[-1]
                    }
                    
                return None
                
            except Exception as e:
                logging.error(f"❌ Likidite birikimi hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Likidite birikimi tespit hatası: {e}")
            return None
            
    @classmethod
    def detect_trap_pattern(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Tuzak pattern tespiti"""
        try:
            if len(ohlc) < 20:
                logging.error("❌ Tuzak pattern için yetersiz veri")
                return None
                
            try:
                # Son 3 mumu al
                last_3 = ohlc.tail(3)
                
                if len(last_3) < 3:
                    return None
                    
                # Bullish Trap
                if (float(last_3["low"].iloc[-2]) < float(last_3["low"].iloc[-3]) and  # Düşük kırıldı
                    float(last_3["close"].iloc[-1]) > float(last_3["high"].iloc[-2])):  # Yukarı dönüş
                    return {
                        "type": "BULLISH_TRAP",
                        "price": float(last_3["low"].iloc[-2]),
                        "timestamp": ohlc.index[-1]
                    }
                    
                # Bearish Trap
                elif (float(last_3["high"].iloc[-2]) > float(last_3["high"].iloc[-3]) and  # Yüksek kırıldı
                      float(last_3["close"].iloc[-1]) < float(last_3["low"].iloc[-2])):  # Aşağı dönüş
                    return {
                        "type": "BEARISH_TRAP",
                        "price": float(last_3["high"].iloc[-2]),
                        "timestamp": ohlc.index[-1]
                    }
                    
                return None
                
            except Exception as e:
                logging.error(f"❌ Tuzak pattern hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Tuzak pattern tespit hatası: {e}")
            return None

    @classmethod
    def get_daily_levels(cls, ohlc: pd.DataFrame) -> Dict:
        """Günlük önemli seviyeleri hesaplar"""
        try:
            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ Günlük seviyeler için geçersiz veri tipi")
                return {}
                
            if len(ohlc) < 20:
                logging.error("❌ Günlük seviyeler için yetersiz veri uzunluğu")
                return {}
                
            if ohlc.empty:
                logging.error("❌ Günlük seviyeler için boş veri")
                return {}
                
            # Günlük verileri al
            daily_data = ohlc.resample("D").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last"
            })
            
            if len(daily_data) < 2:
                logging.error("❌ Günlük seviyeler için yetersiz günlük veri")
                return {}
                
            # Son günün verilerini al
            last_day = daily_data.iloc[-1]
            
            return {
                "high": float(last_day["high"]),
                "low": float(last_day["low"]),
                "open": float(last_day["open"]),
                "close": float(last_day["close"]),
                "timestamp": last_day.name
            }
            
        except Exception as e:
            logging.error(f"❌ Günlük seviye hesaplama hatası: {e}")
            return {}

    @classmethod
    def detect_ob(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Order Block tespit fonksiyonu"""
        try:
            # Varsayılan dönüş değeri
            default_return = {
                "type": None,
                "direction": None,
                "price": None,
                "sl_level": None,
                "timestamp": None
            }

            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ OB için geçersiz veri tipi")
                return default_return
                
            if len(ohlc) < 3:  # Minimum 3 mum yeterli
                logging.error("❌ OB için yetersiz veri uzunluğu")
                return default_return
                
            if ohlc.empty:
                logging.error("❌ OB için boş veri")
                return default_return
                
            # Son 3 mumu al
            last_3 = ohlc.tail(3).copy()
            
            try:
                # Son mumun yönünü belirle
                last_candle = last_3.iloc[-1]
                prev_candle = last_3.iloc[-2]
                first_candle = last_3.iloc[0]
                
                # Bullish OB
                if (float(last_candle["close"]) > float(last_candle["open"]) and  # Yeşil mum
                    float(prev_candle["low"]) < float(first_candle["low"])):  # Önceki düşük kırıldı
                    return {
                        "type": "BULLISH_OB",
                        "direction": 1,
                        "price": float(last_candle["low"]),
                        "sl_level": float(last_candle["low"]) * 0.995,  # %0.5 altı
                        "timestamp": ohlc.index[-1]
                    }
                # Bearish OB    
                elif (float(last_candle["close"]) < float(last_candle["open"]) and  # Kırmızı mum
                      float(prev_candle["high"]) > float(first_candle["high"])):  # Önceki yüksek kırıldı
                    return {
                        "type": "BEARISH_OB",
                        "direction": -1,
                        "price": float(last_candle["high"]),
                        "sl_level": float(last_candle["high"]) * 1.005,  # %0.5 üstü
                        "timestamp": ohlc.index[-1]
                    }
                    
                # OB bulunamadıysa son kapanış fiyatını kullan
                default_return["price"] = float(last_candle["close"])
                default_return["timestamp"] = ohlc.index[-1]
                return default_return
                
            except (IndexError, ValueError) as e:
                logging.error(f"❌ OB hesaplama hatası: {e}")
                return default_return
                
        except Exception as e:
            logging.error(f"❌ OB tespit hatası: {e}")
            return default_return

    @classmethod
    def detect_fvg(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Fair Value Gap tespit fonksiyonu"""
        try:
            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ FVG için geçersiz veri tipi")
                return None
                
            if len(ohlc) < 3:  # Minimum 3 mum yeterli
                logging.error("❌ FVG için yetersiz veri uzunluğu")
                return None
                
            if ohlc.empty:
                logging.error("❌ FVG için boş veri")
                return None
                
            try:
                # Son üç mumu al
                last_candles = ohlc.tail(3)
                if len(last_candles) < 3:
                    logging.error("❌ FVG için yetersiz mum sayısı")
                    return None
                    
                # FVG hesapla
                c1 = last_candles.iloc[0]
                c2 = last_candles.iloc[1]
                c3 = last_candles.iloc[2]
                
                # Bullish FVG
                if float(c1["low"]) > float(c3["high"]):
                    fvg_price = (float(c1["low"]) + float(c3["high"])) / 2
                    fvg_size = float(c1["low"]) - float(c3["high"])
                    return {
                        "type": "BULLISH",
                        "direction": 1,
                        "price": float(fvg_price),
                        "size": float(fvg_size),
                        "top": float(c1["low"]),
                        "bottom": float(c3["high"]),
                        "timestamp": ohlc.index[-1]
                    }
                    
                # Bearish FVG
                if float(c1["high"]) < float(c3["low"]):
                    fvg_price = (float(c1["high"]) + float(c3["low"])) / 2
                    fvg_size = float(c3["low"]) - float(c1["high"])
                    return {
                        "type": "BEARISH",
                        "direction": -1,
                        "price": float(fvg_price),
                        "size": float(fvg_size),
                        "top": float(c3["low"]),
                        "bottom": float(c1["high"]),
                        "timestamp": ohlc.index[-1]
                    }
                    
                # Eğer FVG bulunamazsa varsayılan değerleri döndür
                return {
                    "type": None,
                    "direction": None,
                    "price": float(c3["close"]),
                    "size": 0.0,
                    "top": None,
                    "bottom": None,
                    "timestamp": ohlc.index[-1]
                }
                
            except (IndexError, ValueError) as e:
                logging.error(f"❌ FVG hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.error(f"❌ FVG tespit hatası: {e}")
            return None

    @classmethod
    def detect_divergence(cls, ohlc: pd.DataFrame) -> Optional[Dict]:
        """SMT Divergence tespiti"""
        try:
            if not isinstance(ohlc, pd.DataFrame):
                logging.error("❌ Divergence için geçersiz veri tipi")
                return None
                
            if len(ohlc) < 20:
                logging.error("❌ Divergence için yetersiz veri")
                return None
                
            try:
                # RSI hesapla
                delta = ohlc["close"].astype(float).diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                # Son 5 mumu al (3'ten 5'e çıkarıldı)
                last_candles = ohlc.tail(5)
                if len(last_candles) < 5:
                    return None
                    
                # Fiyat ve RSI yönlerini karşılaştır
                price_high = float(last_candles["high"].max())
                price_low = float(last_candles["low"].min())
                price_close = float(last_candles["close"].iloc[-1])
                
                rsi_values = rsi.tail(5)
                rsi_high = float(rsi_values.max())
                rsi_low = float(rsi_values.min())
                rsi_last = float(rsi_values.iloc[-1])
                
                # Bullish Divergence
                if price_low < price_close and rsi_low > rsi_last:
                    return {
                        "type": "BULLISH",
                        "strength": abs(rsi_last - rsi_low) / 100,
                        "price": price_close,
                        "timestamp": ohlc.index[-1]
                    }
                    
                # Bearish Divergence
                elif price_high > price_close and rsi_high < rsi_last:
                    return {
                        "type": "BEARISH",
                        "strength": abs(rsi_last - rsi_high) / 100,
                        "price": price_close,
                        "timestamp": ohlc.index[-1]
                    }
                    
                return None
                
            except Exception as e:
                logging.debug(f"❌ Divergence hesaplama hatası: {e}")
                return None
                
        except Exception as e:
            logging.debug(f"❌ Divergence tespit hatası: {e}")
            return None