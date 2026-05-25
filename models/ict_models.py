from typing import Dict, Optional, Any, List
import pandas as pd
import numpy as np  # TA-Lib yerine pandas_ta kullanabiliriz
import talib as ta
import logging

from models.base_model import ICTModel
from models.ict_tools import smc

class ICTModel:
    """Temel ICT Model sınıfı"""
    def __init__(self):
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(self.name)
        
    def _validate_data(self, ohlc: pd.DataFrame, min_length: int = 100) -> bool:
        """Kapsamlı veri doğrulama"""
        try:
            if ohlc is None:
                self.logger.error("❌ Veri yok (None)")
                return False
                
            if not isinstance(ohlc, pd.DataFrame):
                self.logger.error("❌ Geçersiz veri tipi")
                return False
                
            if ohlc.empty:
                self.logger.error("❌ Veri boş")
                return False
                
            if len(ohlc) < min_length:
                self.logger.error(f"❌ Yetersiz veri uzunluğu ({len(ohlc)} < {min_length})")
                return False
                
            required_columns = ["high", "low", "open", "close"]
            missing_columns = [col for col in required_columns if col not in ohlc.columns]
            if missing_columns:
                self.logger.error(f"❌ Eksik sütunlar: {missing_columns}")
                return False
                
            if ohlc[required_columns].isnull().values.any():
                self.logger.error("❌ Veride eksik değerler var")
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"❌ Veri doğrulama hatası: {e}")
            return False
            
    def _safe_get_list_item(self, lst: List, index: int, default=None) -> Any:
        """Liste elemanlarına güvenli erişim"""
        try:
            if not isinstance(lst, list):
                return default
            if not lst:
                return default
            if index < 0 or index >= len(lst):
                return default
            return lst[index]
        except Exception:
            return default
            
    def _safe_get_dict_item(self, data: Dict, key: str, default=None) -> Any:
        """Dictionary elemanlarına güvenli erişim"""
        try:
            if not isinstance(data, dict):
                return default
            return data.get(key, default)
        except Exception:
            return default
            
    def _safe_get_dataframe_value(self, df: pd.DataFrame, index: int, column: str, default=None) -> Any:
        """DataFrame değerlerine güvenli erişim"""
        try:
            if not isinstance(df, pd.DataFrame):
                return default
            if df.empty:
                return default
            if index < 0 or index >= len(df):
                return default
            if column not in df.columns:
                return default
            value = df.iloc[index][column]
            return value if pd.notna(value) else default
        except Exception:
            return default
            
    def _safe_get_dict(self, data: Any, required_keys: List[str] = None) -> Optional[Dict]:
        """Dictionary güvenli erişim"""
        try:
            if data is None:
                return None
                
            if not isinstance(data, dict):
                return None
                
            if required_keys and not all(key in data for key in required_keys):
                return None
                
            return data
        except Exception:
            return None
            
    def _safe_get_price(self, data: Dict, key: str) -> Optional[float]:
        """Fiyat değeri güvenli erişim"""
        try:
            if not isinstance(data, dict):
                return None
                
            value = data.get(key)
            if value is None:
                return None
                
            return float(value)
        except (TypeError, ValueError):
            return None
            
    def _validate_setup_data(self, setup_data: Dict[str, Any], required_fields: List[str]) -> bool:
        """Setup verisi doğrulama"""
        try:
            if not isinstance(setup_data, dict):
                self.logger.error("❌ Setup verisi dictionary değil")
                return False
                
            missing_fields = [field for field in required_fields if field not in setup_data]
            if missing_fields:
                self.logger.error(f"❌ Eksik alanlar: {missing_fields}")
                return False
                
            for field in required_fields:
                if setup_data[field] is None:
                    self.logger.error(f"❌ {field} alanı None")
                    return False
                    
            return True
        except Exception as e:
            self.logger.error(f"❌ Setup verisi doğrulama hatası: {e}")
            return False

class BaseModel:
    def __init__(self):
        self.liquidity_levels = {"HIGH": [], "LOW": []}
        self.min_data_length = 20  # 50'den 20'ye düşürüldü

    def _validate_dataframe(self, data: pd.DataFrame, min_length: int = 3) -> bool:
        """DataFrame doğrulama yardımcı fonksiyonu"""
        try:
            if not isinstance(data, pd.DataFrame):
                logging.error("❌ Geçersiz veri tipi: DataFrame değil")
                return False
            
            if data is None or data.empty:
                logging.error("❌ Veri yok veya boş")
                return False
                
            if len(data) < min_length:
                logging.error(f"❌ Yetersiz veri uzunluğu: {len(data)} < {min_length}")
                return False
                
            required_columns = ["high", "low", "open", "close"]
            if not all(col in data.columns for col in required_columns):
                logging.error("❌ Gerekli sütunlar eksik")
                return False
                
            if data[required_columns].isnull().values.any():
                logging.error("❌ Veride eksik değerler var")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"❌ Veri doğrulama hatası: {e}")
            return False

    def _safe_get(self, data: Dict, key: str, default=None):
        """Dictionary'den güvenli veri alma yardımcı fonksiyonu"""
        try:
            if not isinstance(data, dict):
                return default
            return data.get(key, default)
        except Exception:
            return default

    def swing_highs_lows(self, data: pd.DataFrame) -> Dict:
        try:
            swings = {"HighLow": [], "Level": []}
            
            # Minimum veri uzunluğunu 3'e düşürdük
            if not self._validate_dataframe(data, min_length=3):
                return swings
                
            data_reset = data.reset_index(drop=True)
            
            # İlk ve son mum hesaplamaya dahil edilmiyor
            for i in range(1, len(data_reset)-1):
                try:
                    current_high = float(data_reset.loc[i, "high"])
                    prev_high = float(data_reset.loc[i-1, "high"])
                    next_high = float(data_reset.loc[i+1, "high"])
                    current_low = float(data_reset.loc[i, "low"])
                    prev_low = float(data_reset.loc[i-1, "low"])
                    next_low = float(data_reset.loc[i+1, "low"])
                    
                    if pd.isna(current_high) or pd.isna(prev_high) or pd.isna(next_high) or \
                       pd.isna(current_low) or pd.isna(prev_low) or pd.isna(next_low):
                        continue
                    
                    if (current_high > prev_high and current_high > next_high):
                        swings["HighLow"].append(1)
                        swings["Level"].append(current_high)
                    elif (current_low < prev_low and current_low < next_low):
                        swings["HighLow"].append(-1)
                        swings["Level"].append(current_low)
                        
                except (KeyError, IndexError) as e:
                    logging.error(f"❌ Veri erişim hatası: {e}")
                    continue
                except Exception as e:
                    logging.error(f"❌ Swing hesaplama hatası: {e}")
                    continue
                    
            return swings
            
        except Exception as e:
            logging.error(f"❌ Swing highs/lows tespit hatası: {e}")
            return {"HighLow": [], "Level": []}

    def detect_liquidity_sweep(self, data: pd.DataFrame) -> Optional[Dict]:
        try:
            if not self._validate_dataframe(data, min_length=20):
                return None

            sweeps = []
            
            try:
                last_high = float(data["high"].iloc[-1])
                last_low = float(data["low"].iloc[-1])
                last_timestamp = data.index[-1]
            except (IndexError, ValueError) as e:
                logging.error(f"Son mum verisi alınamadı: {e}")
                return None

            for level_type, levels in self.liquidity_levels.items():
                if not isinstance(levels, list):
                    continue
                    
                for level in levels:
                    if not isinstance(level, dict) or "price" not in level:
                        continue
                    
                    try:
                        price = float(level["price"])
                    except (TypeError, ValueError):
                        continue
                        
                    if level_type == "HIGH" and last_high > price:
                        sweeps.append({
                            "type": "HIGH_SWEEP",
                            "price": price,
                            "timestamp": last_timestamp,
                            "strength": self._safe_get(level, "strength", 1.0)
                        })
                    elif level_type == "LOW" and last_low < price:
                        sweeps.append({
                            "type": "LOW_SWEEP",
                            "price": price,
                            "timestamp": last_timestamp,
                            "strength": self._safe_get(level, "strength", 1.0)
                        })
                        
            return sweeps if sweeps else None
            
        except Exception as e:
            logging.error(f"❌ Liquidity sweep tespit hatası: {e}")
            return None
            
    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        try:
            if not self._validate_dataframe(ohlc, min_length=100):
                return None

            try:
                recent_data = ohlc.tail(20).copy()
            except Exception as e:
                logging.error(f"Son veri alma hatası: {e}")
                return None

            swings = smc.swing_highs_lows(recent_data)
            if not isinstance(swings, dict) or "HighLow" not in swings or "Level" not in swings:
                logging.error("❌ Geçersiz swing verisi")
                return None
                
            if not swings["HighLow"] or not swings["Level"]:
                logging.error("❌ Swing noktası bulunamadı")
                return None
                
            self.liquidity_levels = {"HIGH": [], "LOW": []}
            
            try:
                for i in range(len(swings["HighLow"])):
                    if i >= len(swings["Level"]):
                        break
                        
                    try:
                        price = float(swings["Level"][i])
                    except (TypeError, ValueError):
                        continue
                        
                    if swings["HighLow"][i] == 1:
                        self.liquidity_levels["HIGH"].append({
                            "price": price,
                            "strength": 1.0
                        })
                    elif swings["HighLow"][i] == -1:
                        self.liquidity_levels["LOW"].append({
                            "price": price,
                            "strength": 1.0
                        })
            except Exception as e:
                logging.error(f"Swing verisi işleme hatası: {e}")
                return None

            sweep = self.detect_liquidity_sweep(recent_data)
            if sweep is None:
                return None

            market_structure = smc.bos_choch(ohlc, swings)
            if market_structure is None:
                return None

            return {
                "sweep": sweep,
                "market_structure": market_structure,
                "swings": swings
            }
            
        except Exception as e:
            logging.error(f"❌ {self.__class__.__name__} detect hatası: {e}")
            return None

class BOSFVGModel(ICTModel):
    """
    BOS-FVG Modeli:
    BOS (Break of Structure) sonrası trend yönünde devam eden işlemler.
    Fiyat, BOS sonrası oluşan FVG'ye (Fair Value Gap) geri çekilir ve trende devam eder.
    """
    def __init__(self):
        super().__init__()
        self.min_data_length = 20

    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """BOS-FVG setup'ını tespit eder"""
        try:
            # Temel veri doğrulama
            if not self._validate_data(ohlc, min_length=100):
                self.logger.error("❌ Veri doğrulama başarısız")
                return None

            # Son verileri güvenli şekilde al
            try:
                if len(ohlc) < 20:
                    self.logger.error("❌ Yetersiz veri uzunluğu")
                    return None
                recent_data = ohlc.tail(20).copy()
                if recent_data.empty:
                    self.logger.error("❌ Son veri alınamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Son veri alma hatası: {e}")
                return None

            # Momentum teyidi
            if not smc.confirm_momentum(recent_data):
                self.logger.debug("Momentum teyidi başarısız")
                return None
                
            # Killzone kontrolü
            if not smc.is_in_killzone():
                self.logger.debug("Killzone'da değil")
                return None

            # Likidite süpürme kontrolü
            try:
                liquidity_sweep = smc.detect_liquidity_sweep(recent_data)
                if not isinstance(liquidity_sweep, dict):
                    return None
                    
                sweep_price = self._safe_get_dict_item(liquidity_sweep, "price")
                sweep_timestamp = self._safe_get_dict_item(liquidity_sweep, "timestamp")
                
                if sweep_price is None or sweep_timestamp is None:
                    self.logger.error("❌ Likidite sweep verisi eksik")
                    return None
                    
                try:
                    sweep_price = float(sweep_price)
                except (TypeError, ValueError):
                    self.logger.error("❌ Sweep fiyatı sayıya dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Likidite sweep hatası: {e}")
                return None

            # BOS kontrolü
            try:
                bos = smc.detect_bos(recent_data)
                if not isinstance(bos, dict):
                    return None
                    
                bos_direction = self._safe_get_dict_item(bos, "direction")
                bos_price = self._safe_get_dict_item(bos, "price")
                
                if bos_direction is None or bos_price is None:
                    self.logger.error("❌ BOS verisi eksik")
                    return None
                    
                try:
                    bos_price = float(bos_price)
                    bos_direction = int(bos_direction)
                except (TypeError, ValueError):
                    self.logger.error("❌ BOS değerleri dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ BOS hatası: {e}")
                return None

            # FVG kontrolü
            try:
                fvg = smc.detect_fvg(recent_data)
                if not isinstance(fvg, dict):
                    return None
                    
                fvg_price = self._safe_get_dict_item(fvg, "price")
                fvg_size = self._safe_get_dict_item(fvg, "size")
                
                if fvg_price is None or fvg_size is None:
                    self.logger.error("❌ FVG verisi eksik")
                    return None
                    
                try:
                    fvg_price = float(fvg_price)
                    fvg_size = float(fvg_size)
                except (TypeError, ValueError):
                    self.logger.error("❌ FVG değerleri dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ FVG hatası: {e}")
                return None

            # Setup kalitesi hesaplama
            try:
                # Son 3 mumu al
                last_candles = recent_data.tail(3)
                
                # Hareket büyüklüğü
                move_size = abs(float(last_candles.iloc[-1]["close"]) - float(last_candles.iloc[-2]["close"]))
                avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                avg_move = float(avg_range.mean())
                
                # Hacim teyidi
                volume_quality = 1.0
                if "volume" in recent_data.columns:
                    curr_volume = float(last_candles.iloc[-1]["volume"])
                    avg_volume = float(recent_data["volume"].mean())
                    volume_quality = min(curr_volume / avg_volume, 1.0)
                    
                # FVG kalitesi
                fvg_quality = min(abs(fvg_size) / avg_move, 1.0)
                    
                # Toplam kalite
                setup_quality = min((move_size / avg_move) * volume_quality * fvg_quality, 1.0)
                
            except Exception as e:
                self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                setup_quality = 0.5  # Varsayılan değer

            # TP hesaplama
            try:
                tp = smc.get_trend_target(recent_data, bos_direction)
                if tp is None:
                    self.logger.error("❌ TP hesaplanamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ TP hesaplama hatası: {e}")
                return None

            # Setup verisi oluştur
            return {
                "type": "BOS_FVG",
                "direction": "LONG" if bos_direction == 1 else "SHORT",
                "entry": fvg_price,
                "stop": sweep_price,
                "tp": float(tp),
                "setup_quality": setup_quality,
                "liquidity_sweep": liquidity_sweep,
                "bos": bos,
                "fvg": fvg,
                "timestamp": recent_data.index[-1],
                "timeframe": "current",
                "status": "ACTIVE"
            }

        except Exception as e:
            self.logger.error(f"❌ BOS-FVG tespit hatası: {e}")
            return None

class CHOCHOBModel(ICTModel):
    def __init__(self):
        super().__init__()
        self.min_data_length = 20

    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """CHoCH-OB setup'ını tespit eder"""
        try:
            # Temel veri doğrulama
            if not self._validate_data(ohlc, min_length=100):
                self.logger.error("❌ Veri doğrulama başarısız")
                return None

            # Son verileri güvenli şekilde al
            try:
                if len(ohlc) < 20:
                    self.logger.error("❌ Yetersiz veri uzunluğu")
                    return None
                recent_data = ohlc.tail(20).copy()
                if recent_data.empty:
                    self.logger.error("❌ Son veri alınamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Son veri alma hatası: {e}")
                return None

            # Momentum teyidi
            if not smc.confirm_momentum(recent_data):
                self.logger.debug("Momentum teyidi başarısız")
                return None
                
            # Killzone kontrolü
            if not smc.is_in_killzone():
                self.logger.debug("Killzone'da değil")
                return None

            # CHoCH kontrolü
            try:
                choch = smc.detect_choch(recent_data)
                if not isinstance(choch, dict):
                    return None
                    
                choch_direction = self._safe_get_dict_item(choch, "direction")
                choch_level = self._safe_get_dict_item(choch, "level")
                
                if choch_direction is None or choch_level is None:
                    self.logger.error("❌ CHoCH verisi eksik")
                    return None
                    
                try:
                    choch_level = float(choch_level)
                    choch_direction = int(choch_direction)
                except (TypeError, ValueError):
                    self.logger.error("❌ CHoCH değerleri dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ CHoCH hatası: {e}")
                return None

            # OB kontrolü
            try:
                ob = smc.detect_ob(recent_data)
                if not isinstance(ob, dict):
                    return None
                    
                ob_price = self._safe_get_dict_item(ob, "price")
                ob_sl_level = self._safe_get_dict_item(ob, "sl_level")
                
                if ob_price is None or ob_sl_level is None:
                    self.logger.error("❌ OB verisi eksik")
                    return None
                    
                try:
                    ob_price = float(ob_price)
                    ob_sl_level = float(ob_sl_level)
                except (TypeError, ValueError):
                    self.logger.error("❌ OB değerleri dönüştürülemedi")
                    return None
                    
                # OB test kontrolü
                if not smc.is_ob_tested(ob):
                    self.logger.debug("OB henüz test edilmedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ OB hatası: {e}")
                return None

            # Setup kalitesi hesaplama
            try:
                # Son 3 mumu al
                last_candles = recent_data.tail(3)
                
                # Hareket büyüklüğü
                move_size = abs(float(last_candles.iloc[-1]["close"]) - float(last_candles.iloc[-2]["close"]))
                avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                avg_move = float(avg_range.mean())
                
                # Hacim teyidi
                volume_quality = 1.0
                if "volume" in recent_data.columns:
                    curr_volume = float(last_candles.iloc[-1]["volume"])
                    avg_volume = float(recent_data["volume"].mean())
                    volume_quality = min(curr_volume / avg_volume, 1.0)
                    
                # CHoCH kalitesi
                choch_quality = min(abs(float(last_candles.iloc[-1]["close"]) - choch_level) / avg_move, 1.0)
                    
                # Toplam kalite
                setup_quality = min((move_size / avg_move) * volume_quality * choch_quality, 1.0)
                
            except Exception as e:
                self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                setup_quality = 0.5  # Varsayılan değer

            # TP hesaplama
            try:
                tp = smc.get_trend_target(recent_data, choch_direction)
                if tp is None:
                    self.logger.error("❌ TP hesaplanamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ TP hesaplama hatası: {e}")
                return None

            # Setup verisi oluştur
            return {
                "type": "CHOCH_OB",
                "direction": "LONG" if choch_direction == 1 else "SHORT",
                "entry": ob_price,
                "stop": ob_sl_level,
                "tp": float(tp),
                "setup_quality": setup_quality,
                "choch": choch,
                "ob": ob,
                "timestamp": recent_data.index[-1],
                "timeframe": "current",
                "status": "ACTIVE"
            }

        except Exception as e:
            self.logger.error(f"❌ CHoCH-OB tespit hatası: {e}")
            return None

class OTEModel(ICTModel):
    """
    OTE (Optimal Trade Entry) - Fibonacci Bazlı Giriş
    OTE, fiyatın %61.8 - %79 Fibonacci seviyesine geri çekilip trend yönünde devam etmesine dayanır.
    """
    def __init__(self):
        super().__init__()
        self.min_data_length = 20

    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """OTE setup'ını tespit eder"""
        try:
            # Temel veri doğrulama
            if not self._validate_data(ohlc, min_length=100):
                self.logger.error("❌ Veri doğrulama başarısız")
                return None
                
            # Son verileri güvenli şekilde al
            try:
                if len(ohlc) < 20:
                    self.logger.error("❌ Yetersiz veri uzunluğu")
                    return None
                recent_data = ohlc.tail(20).copy()
                if recent_data.empty:
                    self.logger.error("❌ Son veri alınamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Son veri alma hatası: {e}")
                return None

            # Momentum teyidi
            if not smc.confirm_momentum(recent_data):
                self.logger.debug("Momentum teyidi başarısız")
                return None
                
            # Killzone kontrolü
            if not smc.is_in_killzone():
                self.logger.debug("Killzone'da değil")
                return None

            # Likidite süpürme kontrolü
            try:
                liquidity_sweep = smc.detect_liquidity_sweep(recent_data)
                if not isinstance(liquidity_sweep, dict):
                    return None
                    
                sweep_price = self._safe_get_dict_item(liquidity_sweep, "price")
                sweep_timestamp = self._safe_get_dict_item(liquidity_sweep, "timestamp")
                
                if sweep_price is None or sweep_timestamp is None:
                    self.logger.error("❌ Likidite sweep verisi eksik")
                    return None
                    
                try:
                    sweep_price = float(sweep_price)
                except (TypeError, ValueError):
                    self.logger.error("❌ Sweep fiyatı sayıya dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Likidite sweep hatası: {e}")
                return None
                
            # BOS kontrolü
            try:
                bos = smc.detect_bos(recent_data)
                if not isinstance(bos, dict):
                    return None
                    
                bos_direction = self._safe_get_dict_item(bos, "direction")
                bos_price = self._safe_get_dict_item(bos, "price")
                
                if bos_direction is None or bos_price is None:
                    self.logger.error("❌ BOS verisi eksik")
                    return None
                    
                try:
                    bos_price = float(bos_price)
                    bos_direction = int(bos_direction)
                except (TypeError, ValueError):
                    self.logger.error("❌ BOS değerleri dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ BOS hatası: {e}")
                return None
                
            # Fibonacci geri çekilme kontrolü
            try:
                # Son yüksek/düşük
                if bos_direction == 1:  # Yukarı trend
                    high = float(recent_data["high"].max())
                    low = float(recent_data["low"].min())
                else:  # Aşağı trend
                    high = float(recent_data["low"].max())
                    low = float(recent_data["high"].min())
                    
                # Fibonacci seviyeleri
                range_size = high - low
                fib_618 = low + (range_size * 0.618)
                fib_79 = low + (range_size * 0.79)
                
                # Son kapanış
                last_close = float(recent_data["close"].iloc[-1])
                
                # Fib bölgesinde mi?
                if not (fib_618 <= last_close <= fib_79):
                    self.logger.debug("Fiyat Fibonacci bölgesinde değil")
                    return None
                    
            except Exception as e:
                self.logger.error(f"❌ Fibonacci hesaplama hatası: {e}")
                return None

            # Setup kalitesi hesaplama
            try:
                # Son 3 mumu al
                last_candles = recent_data.tail(3)
                
                # Hareket büyüklüğü
                move_size = abs(float(last_candles.iloc[-1]["close"]) - float(last_candles.iloc[-2]["close"]))
                avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                avg_move = float(avg_range.mean())
                
                # Hacim teyidi
                volume_quality = 1.0
                if "volume" in recent_data.columns:
                    curr_volume = float(last_candles.iloc[-1]["volume"])
                    avg_volume = float(recent_data["volume"].mean())
                    volume_quality = min(curr_volume / avg_volume, 1.0)
                    
                # Fibonacci kalitesi
                fib_quality = min(abs(last_close - fib_618) / (fib_79 - fib_618), 1.0)
                    
                # Toplam kalite
                setup_quality = min((move_size / avg_move) * volume_quality * fib_quality, 1.0)
                
            except Exception as e:
                self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                setup_quality = 0.5  # Varsayılan değer

            # TP hesaplama
            try:
                tp = smc.get_trend_target(recent_data, bos_direction)
                if tp is None:
                    self.logger.error("❌ TP hesaplanamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ TP hesaplama hatası: {e}")
                return None

            # Setup verisi oluştur
            return {
                "type": "OTE",
                "direction": "LONG" if bos_direction == 1 else "SHORT",
                "entry": last_close,
                "stop": fib_79,  # %79 seviyesinin hemen üstü/altı
                "tp": float(tp),
                "setup_quality": setup_quality,
                "liquidity_sweep": liquidity_sweep,
                "bos": bos,
                "fibonacci": {
                    "high": high,
                    "low": low,
                    "fib_618": fib_618,
                    "fib_79": fib_79
                },
                "timestamp": recent_data.index[-1],
                "timeframe": "current",
                "status": "ACTIVE"
            }
            
        except Exception as e:
            self.logger.error(f"❌ OTE tespit hatası: {e}")
            return None

class SILVERBULLETModel(ICTModel):
    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Silver Bullet setup tespiti"""
        try:
            if not self._validate_data(ohlc, min_length=50):
                return None
                
            # Son 50 mumu al
            recent_data = ohlc.tail(50).copy()
            if len(recent_data) < 50:
                self.logger.error("❌ Silver Bullet için yetersiz veri")
                return None
                
            # Güvenli liste erişimi için son mumları al
            try:
                last_candles = recent_data.tail(5)
                if len(last_candles) < 5:
                    return None
                    
                # Son 5 mumun OHLC değerlerini al
                c1 = last_candles.iloc[0]
                c2 = last_candles.iloc[1]
                c3 = last_candles.iloc[2]
                c4 = last_candles.iloc[3]
                c5 = last_candles.iloc[4]
                
                # Momentum teyidi
                if not smc.confirm_momentum(recent_data):
                    self.logger.debug("Momentum teyidi başarısız")
                    return None
                    
                # Killzone kontrolü
                if not smc.is_in_silver_bullet_time():  # Silver Bullet için özel zaman kontrolü
                    self.logger.debug("Silver Bullet zamanı değil")
                    return None
                    
                # Setup kalitesi hesaplama
                try:
                    # Hareket büyüklüğü
                    move_size = abs(float(c5["close"]) - float(c4["close"]))
                    avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                    avg_move = float(avg_range.mean())
                    
                    # Hacim teyidi
                    volume_quality = 1.0
                    if "volume" in recent_data.columns:
                        curr_volume = float(c5["volume"])
                        avg_volume = float(recent_data["volume"].mean())
                        volume_quality = min(curr_volume / avg_volume, 1.0)
                        
                    # Toplam kalite
                    setup_quality = min((move_size / avg_move) * volume_quality, 1.0)
                    
                except Exception as e:
                    self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                    setup_quality = 0.5  # Varsayılan değer
                
                # Silver Bullet pattern kontrolü
                if (float(c5["close"]) > float(c4["high"]) and  # Bullish engulfing
                    float(c4["close"]) < float(c4["open"]) and  # Önceki mum kırmızı
                    float(c3["high"]) > float(c4["high"]) and   # Yüksek seviye kırıldı
                    float(c2["low"]) < float(c3["low"])):       # Düşük seviye test edildi
                    
                    # TP hesaplama
                    try:
                        tp = smc.get_trend_target(recent_data, 1)  # Yukarı hedef
                        if tp is None:
                            self.logger.error("❌ TP hesaplanamadı")
                            return None
                    except Exception as e:
                        self.logger.error(f"❌ TP hesaplama hatası: {e}")
                        return None
                    
                    return {
                        "type": "SILVER_BULLET",
                        "direction": 1,
                        "entry": float(c5["close"]),
                        "stop": float(c4["low"]),
                        "tp": float(tp),
                        "setup_quality": setup_quality,
                        "timestamp": recent_data.index[-1],
                        "timeframe": "current",
                        "status": "ACTIVE"
                    }
                    
                return None
                
            except (IndexError, KeyError) as e:
                self.logger.error(f"❌ Silver Bullet veri erişim hatası: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Silver Bullet tespit hatası: {e}")
            return None

class TURTLESOUPModel(ICTModel):
    """
    ICT Turtle Soup Setup:
    Likidite bölgelerindeki yanlış kırılımları ve başarısız breakout'ları tespit eder.
    HTF'de likidite bölgelerini belirler, LTF'de likidite sweep'lerini ve yapısal değişimleri (MSS/CHoCH) takip eder.
    """
    def __init__(self):
        super().__init__()
        self.min_data_length = 50
        
    def find_entry(self, setup: Dict, data: pd.DataFrame) -> Optional[Dict]:
        """Giriş fırsatı ara"""
        try:
            if not isinstance(setup, dict) or not isinstance(data, pd.DataFrame):
                return None
                
            # Temel kontroller
            if len(data) < self.min_data_length:
                return None
                
            # Setup verilerini al
            direction = setup.get("direction")
            if not direction:
                return None
                
            # Son kapanış fiyatı
            last_close = float(data["close"].iloc[-1])
            
            # Likidite bölgelerini bul
            liquidity_zones = self._find_liquidity_zones(data)
            if not liquidity_zones:
                return None
                
            # Market yapısını kontrol et
            market_structure = smc.bos_choch(data)
            if not market_structure:
                return None
                
            # FVG kontrolü
            fvg = smc.fvg(data)
            if not fvg:
                return None
                
            # HTF likidite kontrolü
            htf_liquidity = liquidity_zones.get("htf", {})
            
            # Sweep kontrolü
            sweep = smc.detect_liquidity_sweep(data)
            if not sweep:
                return None
                
            # Setup kalitesini hesapla
            setup_quality = self._calculate_setup_quality(
                sweep=sweep,
                market_structure=market_structure,
                fvg=fvg,
                htf_liquidity=htf_liquidity
            )
            
            # Giriş seviyesi
            if direction == 1:  # Long
                entry = float(fvg["price"]) if fvg["type"] == "BULLISH" else last_close
                stop = float(sweep["price"]) * 0.995  # %0.5 altı
            else:  # Short
                entry = float(fvg["price"]) if fvg["type"] == "BEARISH" else last_close
                stop = float(sweep["price"]) * 1.005  # %0.5 üstü
                
            # Hedef seviyesi
            target = self._find_target_level(data, direction)
            
            return {
                "found": True,
                "entry": entry,
                "stop": stop,
                "tp": target,
                "setup_quality": setup_quality,
                "supporting_tools": {
                    "sweep": sweep,
                    "market_structure": market_structure,
                    "fvg": fvg,
                    "htf_liquidity": htf_liquidity
                }
            }
            
        except Exception as e:
            logging.error(f"❌ Turtle Soup giriş arama hatası: {e}")
            return None

    def _find_liquidity_zones(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """HTF'de likidite bölgelerini tespit et"""
        try:
            # Son 50 mumda swing high/low'ları bul
            swings = smc.swing_highs_lows(ohlc)
            if not swings or not swings["Level"]:
                return None

            # Buy-Side Liquidity (BSL) - Son yüksekler
            bsl_levels = []
            for i, level in enumerate(swings["Level"]):
                if swings["HighLow"][i] == 1:  # Swing High
                    bsl_levels.append(float(level))

            # Sell-Side Liquidity (SSL) - Son düşükler
            ssl_levels = []
            for i, level in enumerate(swings["Level"]):
                if swings["HighLow"][i] == -1:  # Swing Low
                    ssl_levels.append(float(level))

            return {
                "bsl": bsl_levels[-3:] if len(bsl_levels) >= 3 else bsl_levels,  # Son 3 BSL
                "ssl": ssl_levels[-3:] if len(ssl_levels) >= 3 else ssl_levels,  # Son 3 SSL
                "timestamp": ohlc.index[-1]
            }

        except Exception as e:
            self.logger.error(f"❌ Likidite bölgesi tespit hatası: {e}")
            return None

    def _find_target_level(self, ohlc: pd.DataFrame, direction: int) -> float:
        """Hedef seviyeyi belirle"""
        try:
            if direction == 1:  # Bullish için BSL hedef
                highs = ohlc["high"].astype(float)
                target = float(highs.nlargest(3).iloc[-1])  # Son 3 yüksekten biri
                return target
            else:  # Bearish için SSL hedef
                lows = ohlc["low"].astype(float)
                target = float(lows.nsmallest(3).iloc[-1])  # Son 3 düşükten biri
                return target
        except Exception:
            # Hedef belirlenemezse R:R oranına göre hesapla
            entry = float(ohlc["close"].iloc[-1])
            stop = float(ohlc["low"].iloc[-1]) if direction == 1 else float(ohlc["high"].iloc[-1])
            risk = abs(entry - stop)
            return entry + (risk * 2 * direction)  # 2R hedef

    def _calculate_setup_quality(
        self,
        sweep: Dict,
        market_structure: Dict,
        fvg: Dict,
        htf_liquidity: Dict
    ) -> float:
        """Setup kalitesini hesapla"""
        try:
            quality = 0.5  # Başlangıç kalitesi

            # Sweep kalitesi (0.2)
            if sweep.get("strength", 0) > 1.5:
                quality += 0.2
            elif sweep.get("strength", 0) > 1.0:
                quality += 0.1

            # Market yapısı kalitesi (0.4)
            if market_structure["bos"].get("type"):
                quality += 0.2
            if market_structure["choch"].get("type"):
                quality += 0.2

            # FVG kalitesi (0.2)
            if fvg.get("size", 0) > 0:
                quality += min(fvg["size"] * 100, 0.2)

            # HTF likidite kalitesi (0.2)
            if htf_liquidity:
                if len(htf_liquidity["bsl"]) >= 2 or len(htf_liquidity["ssl"]) >= 2:
                    quality += 0.2
                elif len(htf_liquidity["bsl"]) >= 1 or len(htf_liquidity["ssl"]) >= 1:
                    quality += 0.1

            return min(quality, 1.0)  # Maksimum 1.0

        except Exception as e:
            self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
            return 0.5  # Hata durumunda orta kalite

    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Turtle Soup pattern tespiti"""
        try:
            if not self._validate_data(ohlc, self.min_data_length):
                return None
                
            # HTF'de likidite bölgelerini belirle
            htf_liquidity = self._find_liquidity_zones(ohlc)
            if not htf_liquidity:
                return None
                
            # LTF'de likidite sweep kontrolü
            sweep = smc.detect_liquidity_sweep(ohlc)
            if not sweep:
                return None
                
            # Market yapısı değişimi kontrolü (MSS/CHoCH)
            market_structure = smc.bos_choch(ohlc)
            if not market_structure:
                return None
                
            # FVG kontrolü
            fvg = smc.fvg(ohlc)
            if not fvg:
                return None
                
            # Bullish Turtle Soup
            if (sweep["type"] == "LOW_SWEEP" and  # SSL sweep
                market_structure["bos"]["direction"] == 1 and  # Yukarı MSS
                fvg["type"] == "BULLISH"):  # Bullish FVG
                
                return {
                    "type": "BULLISH_TURTLE_SOUP",
                    "direction": 1,
                    "entry": float(fvg["price"]),  # FVG'de giriş
                    "stop": float(sweep["price"]) * 0.995,  # Sweep seviyesinin %0.5 altı
                    "tp": self._find_target_level(ohlc, 1),  # BSL hedef
                    "liquidity_sweep": sweep,
                    "market_structure": market_structure,
                    "fvg": fvg,
                    "htf_liquidity": htf_liquidity,
                    "setup_quality": self._calculate_setup_quality(
                        sweep, market_structure, fvg, htf_liquidity
                    ),
                    "timestamp": ohlc.index[-1]
                }

            # Bearish Turtle Soup
            elif (sweep["type"] == "HIGH_SWEEP" and  # BSL sweep
                  market_structure["bos"]["direction"] == -1 and  # Aşağı MSS
                  fvg["type"] == "BEARISH"):  # Bearish FVG
                
                return {
                    "type": "BEARISH_TURTLE_SOUP",
                    "direction": -1,
                    "entry": float(fvg["price"]),  # FVG'de giriş
                    "stop": float(sweep["price"]) * 1.005,  # Sweep seviyesinin %0.5 üstü
                    "tp": self._find_target_level(ohlc, -1),  # SSL hedef
                    "liquidity_sweep": sweep,
                    "market_structure": market_structure,
                    "fvg": fvg,
                    "htf_liquidity": htf_liquidity,
                    "setup_quality": self._calculate_setup_quality(
                        sweep, market_structure, fvg, htf_liquidity
                    ),
                    "timestamp": ohlc.index[-1]
                }

            return None
            
        except Exception as e:
            logging.error(f"❌ Turtle Soup tespit hatası: {e}")
            return None

class LONDONREVERSALModel(ICTModel):
    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """London Reversal setup tespiti"""
        try:
            if not self._validate_data(ohlc, min_length=50):
                return None
                
            # Son 50 mumu al
            recent_data = ohlc.tail(50).copy()
            if len(recent_data) < 50:
                self.logger.error("❌ London Reversal için yetersiz veri")
                return None
                
            # Güvenli liste erişimi için son mumları al
            try:
                last_candles = recent_data.tail(5)
                if len(last_candles) < 5:
                    return None
                    
                # Son 5 mumun OHLC değerlerini al
                c1 = last_candles.iloc[0]
                c2 = last_candles.iloc[1]
                c3 = last_candles.iloc[2]
                c4 = last_candles.iloc[3]
                c5 = last_candles.iloc[4]
                
                # Momentum teyidi
                if not smc.confirm_momentum(recent_data):
                    self.logger.debug("Momentum teyidi başarısız")
                    return None
                    
                # London session kontrolü
                if not smc.is_in_london_open():  # London açılış kontrolü
                    self.logger.debug("London açılış zamanı değil")
                    return None
                    
                # Setup kalitesi hesaplama
                try:
                    # Hareket büyüklüğü
                    move_size = abs(float(c5["close"]) - float(c4["close"]))
                    avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                    avg_move = float(avg_range.mean())
                    
                    # Hacim teyidi
                    volume_quality = 1.0
                    if "volume" in recent_data.columns:
                        curr_volume = float(c5["volume"])
                        avg_volume = float(recent_data["volume"].mean())
                        volume_quality = min(curr_volume / avg_volume, 1.0)
                        
                    # Toplam kalite
                    setup_quality = min((move_size / avg_move) * volume_quality, 1.0)
                    
                except Exception as e:
                    self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                    setup_quality = 0.5  # Varsayılan değer
                
                # London Reversal pattern kontrolü
                if (float(c5["close"]) < float(c4["low"]) and   # Bearish engulfing
                    float(c4["close"]) > float(c4["open"]) and  # Önceki mum yeşil
                    float(c3["low"]) < float(c4["low"]) and     # Düşük seviye kırıldı
                    float(c2["high"]) > float(c3["high"])):     # Yüksek seviye test edildi
                    
                    # TP hesaplama
                    try:
                        tp = smc.get_trend_target(recent_data, -1)  # Aşağı hedef
                        if tp is None:
                            self.logger.error("❌ TP hesaplanamadı")
                            return None
                    except Exception as e:
                        self.logger.error(f"❌ TP hesaplama hatası: {e}")
                        return None
                    
                    return {
                        "type": "LONDON_REVERSAL",
                        "direction": -1,
                        "entry": float(c5["close"]),
                        "stop": float(c4["high"]),
                        "tp": float(tp),
                        "setup_quality": setup_quality,
                        "timestamp": recent_data.index[-1],
                        "timeframe": "current",
                        "status": "ACTIVE"
                    }
                    
                return None
                
            except (IndexError, KeyError) as e:
                self.logger.error(f"❌ London Reversal veri erişim hatası: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ London Reversal tespit hatası: {e}")
            return None

class NYREVERSALModel(ICTModel):
    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """NY Reversal setup tespiti"""
        try:
            if not self._validate_data(ohlc, min_length=50):
                return None
                
            # Son 50 mumu al
            recent_data = ohlc.tail(50).copy()
            if len(recent_data) < 50:
                self.logger.error("❌ NY Reversal için yetersiz veri")
                return None
                
            # Güvenli liste erişimi için son mumları al
            try:
                last_candles = recent_data.tail(5)
                if len(last_candles) < 5:
                    return None
                    
                # Son 5 mumun OHLC değerlerini al
                c1 = last_candles.iloc[0]
                c2 = last_candles.iloc[1]
                c3 = last_candles.iloc[2]
                c4 = last_candles.iloc[3]
                c5 = last_candles.iloc[4]
                
                # Momentum teyidi
                if not smc.confirm_momentum(recent_data):
                    self.logger.debug("Momentum teyidi başarısız")
                    return None
                    
                # NY session kontrolü
                if not smc.is_in_ny_open():  # NY açılış kontrolü
                    self.logger.debug("NY açılış zamanı değil")
                    return None
                    
                # Setup kalitesi hesaplama
                try:
                    # Hareket büyüklüğü
                    move_size = abs(float(c5["close"]) - float(c4["close"]))
                    avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                    avg_move = float(avg_range.mean())
                    
                    # Hacim teyidi
                    volume_quality = 1.0
                    if "volume" in recent_data.columns:
                        curr_volume = float(c5["volume"])
                        avg_volume = float(recent_data["volume"].mean())
                        volume_quality = min(curr_volume / avg_volume, 1.0)
                        
                    # Toplam kalite
                    setup_quality = min((move_size / avg_move) * volume_quality, 1.0)
                    
                except Exception as e:
                    self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                    setup_quality = 0.5  # Varsayılan değer
                
                # NY Reversal pattern kontrolü
                if (float(c5["close"]) > float(c4["high"]) and  # Bullish engulfing
                    float(c4["close"]) < float(c4["open"]) and  # Önceki mum kırmızı
                    float(c3["high"]) > float(c4["high"]) and   # Yüksek seviye kırıldı
                    float(c2["low"]) < float(c3["low"])):       # Düşük seviye test edildi
                    
                    # TP hesaplama
                    try:
                        tp = smc.get_trend_target(recent_data, 1)  # Yukarı hedef
                        if tp is None:
                            self.logger.error("❌ TP hesaplanamadı")
                            return None
                    except Exception as e:
                        self.logger.error(f"❌ TP hesaplama hatası: {e}")
                        return None
                    
                    return {
                        "type": "NY_REVERSAL",
                        "direction": 1,
                        "entry": float(c5["close"]),
                        "stop": float(c4["low"]),
                        "tp": float(tp),
                        "setup_quality": setup_quality,
                        "timestamp": recent_data.index[-1],
                        "timeframe": "current",
                        "status": "ACTIVE"
                    }
                    
                return None
                
            except (IndexError, KeyError) as e:
                self.logger.error(f"❌ NY Reversal veri erişim hatası: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ NY Reversal tespit hatası: {e}")
            return None

class JUDASSWINGModel(ICTModel):
    def __init__(self):
        super().__init__()
        self.min_data_length = 20  # 50'den 20'ye düşürüldü
        
    def _validate_dataframe(self, data: pd.DataFrame, min_length: int = 3) -> bool:
        """DataFrame doğrulama yardımcı fonksiyonu"""
        try:
            if not isinstance(data, pd.DataFrame):
                self.logger.error("❌ Geçersiz veri tipi: DataFrame değil")
                return False
            
            if data is None or data.empty:
                self.logger.error("❌ Veri yok veya boş")
                return False
                
            if len(data) < min_length:
                self.logger.error(f"❌ Yetersiz veri uzunluğu: {len(data)} < {min_length}")
                return False
                
            required_columns = ["high", "low", "open", "close"]
            if not all(col in data.columns for col in required_columns):
                self.logger.error("❌ Gerekli sütunlar eksik")
                return False
                
            if data[required_columns].isnull().values.any():
                self.logger.error("❌ Veride eksik değerler var")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Veri doğrulama hatası: {e}")
            return False
            
    def swing_highs_lows(self, data: pd.DataFrame) -> Dict:
        """Swing High ve Low noktalarını tespit et"""
        try:
            swings = {"HighLow": [], "Level": []}
            
            # Minimum veri uzunluğunu 3'e düşürdük
            if not self._validate_dataframe(data, min_length=3):
                return swings
                
            data_reset = data.reset_index(drop=True)
            
            # İlk ve son mum hesaplamaya dahil edilmiyor
            for i in range(1, len(data_reset)-1):
                try:
                    current_high = float(data_reset.loc[i, "high"])
                    prev_high = float(data_reset.loc[i-1, "high"])
                    next_high = float(data_reset.loc[i+1, "high"])
                    current_low = float(data_reset.loc[i, "low"])
                    prev_low = float(data_reset.loc[i-1, "low"])
                    next_low = float(data_reset.loc[i+1, "low"])
                    
                    if pd.isna(current_high) or pd.isna(prev_high) or pd.isna(next_high) or \
                       pd.isna(current_low) or pd.isna(prev_low) or pd.isna(next_low):
                        continue
                    
                    if (current_high > prev_high and current_high > next_high):
                        swings["HighLow"].append(1)
                        swings["Level"].append(current_high)
                    elif (current_low < prev_low and current_low < next_low):
                        swings["HighLow"].append(-1)
                        swings["Level"].append(current_low)
                        
                except (KeyError, IndexError) as e:
                    self.logger.error(f"❌ Veri erişim hatası: {e}")
                    continue
                except Exception as e:
                    self.logger.error(f"❌ Swing hesaplama hatası: {e}")
                    continue
                    
            return swings
            
        except Exception as e:
            self.logger.error(f"❌ Swing highs/lows tespit hatası: {e}")
            return {"HighLow": [], "Level": []}
            
    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Judas Swing pattern tespiti"""
        try:
            if not self._validate_data(ohlc, self.min_data_length):
                return None
                
            # Son 20 mumu al
            recent_data = ohlc.tail(self.min_data_length).copy()
            
            # Swing noktalarını bul
            swings = self.swing_highs_lows(recent_data)
            if not swings or not swings["HighLow"] or not swings["Level"]:
                return None
                
            # Son 3 swing noktasını kontrol et
            last_swings = swings["HighLow"][-3:]
            last_levels = swings["Level"][-3:]
            
            if len(last_swings) < 3 or len(last_levels) < 3:
                return None
                
            # Bullish Judas Swing
            if last_swings[0] == -1 and last_swings[1] == 1 and last_swings[2] == -1:
                if last_levels[2] > last_levels[0]:  # Higher Low
                    return {
                        "type": "BULLISH_JUDAS",
                        "direction": 1,
                        "entry": last_levels[2],
                        "stop": last_levels[0],
                        "timestamp": recent_data.index[-1]
                    }
                    
            # Bearish Judas Swing
            if last_swings[0] == 1 and last_swings[1] == -1 and last_swings[2] == 1:
                if last_levels[2] < last_levels[0]:  # Lower High
                    return {
                        "type": "BEARISH_JUDAS",
                        "direction": -1,
                        "entry": last_levels[2],
                        "stop": last_levels[0],
                        "timestamp": recent_data.index[-1]
                    }
                    
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Judas Swing tespit hatası: {e}")
            return None

class PO3Model(ICTModel):
    """
    PO3 (Premium/Discount Order Block) - Fiyat Aksiyon Modeli
    PO3, fiyatın premium/discount bölgesinden dönüş yapmasına dayanır.
    """
    def __init__(self):
        super().__init__()
        self.min_data_length = 20

    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """PO3 setup'ını tespit eder"""
        try:
            # Temel veri doğrulama
            if not self._validate_data(ohlc, min_length=100):
                self.logger.error("❌ Veri doğrulama başarısız")
                return None

            # Son verileri güvenli şekilde al
            try:
                if len(ohlc) < 20:
                    self.logger.error("❌ Yetersiz veri uzunluğu")
                    return None
                recent_data = ohlc.tail(20).copy()
                if recent_data.empty:
                    self.logger.error("❌ Son veri alınamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Son veri alma hatası: {e}")
                return None

            # Momentum teyidi
            if not smc.confirm_momentum(recent_data):
                self.logger.debug("Momentum teyidi başarısız")
                return None
                
            # Killzone kontrolü
            if not smc.is_in_killzone():
                self.logger.debug("Killzone'da değil")
                return None

            # Order block kontrolü
            try:
                ob = smc.detect_ob(recent_data)
                if not isinstance(ob, dict):
                    return None
                    
                ob_price = self._safe_get_dict_item(ob, "price")
                ob_type = self._safe_get_dict_item(ob, "type")
                ob_sl_level = self._safe_get_dict_item(ob, "sl_level")
                
                if ob_price is None or ob_type is None or ob_sl_level is None:
                    self.logger.error("❌ OB verisi eksik")
                    return None
                    
                try:
                    ob_price = float(ob_price)
                    ob_sl_level = float(ob_sl_level)
                except (TypeError, ValueError):
                    self.logger.error("❌ OB değerleri dönüştürülemedi")
                    return None
                    
                # OB test kontrolü
                if not smc.is_ob_tested(ob):
                    self.logger.debug("OB henüz test edilmedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ OB hatası: {e}")
                return None

            # Premium/Discount kontrolü
            try:
                pd_zone = smc.detect_premium_discount(recent_data)
                if not isinstance(pd_zone, dict):
                    return None
                    
                pd_type = self._safe_get_dict_item(pd_zone, "type")
                pd_level = self._safe_get_dict_item(pd_zone, "level")
                
                if pd_type is None or pd_level is None:
                    self.logger.error("❌ Premium/Discount verisi eksik")
                    return None
                    
                try:
                    pd_level = float(pd_level)
                except (TypeError, ValueError):
                    self.logger.error("❌ Premium/Discount seviyesi dönüştürülemedi")
                    return None
                    
                # Yön kontrolü
                if (ob_type == "BULLISH" and pd_type != "DISCOUNT") or \
                   (ob_type == "BEARISH" and pd_type != "PREMIUM"):
                    self.logger.debug("OB ve Premium/Discount uyumsuz")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Premium/Discount hatası: {e}")
                return None

            # Setup kalitesi hesaplama
            try:
                # Son 3 mumu al
                last_candles = recent_data.tail(3)
                
                # Hareket büyüklüğü
                move_size = abs(float(last_candles.iloc[-1]["close"]) - float(last_candles.iloc[-2]["close"]))
                avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                avg_move = float(avg_range.mean())
                
                # Hacim teyidi
                volume_quality = 1.0
                if "volume" in recent_data.columns:
                    curr_volume = float(last_candles.iloc[-1]["volume"])
                    avg_volume = float(recent_data["volume"].mean())
                    volume_quality = min(curr_volume / avg_volume, 1.0)
                    
                # PD kalitesi
                pd_quality = min(abs(float(last_candles.iloc[-1]["close"]) - pd_level) / avg_move, 1.0)
                    
                # Toplam kalite
                setup_quality = min((move_size / avg_move) * volume_quality * pd_quality, 1.0)
                
            except Exception as e:
                self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                setup_quality = 0.5  # Varsayılan değer

            # TP hesaplama
            try:
                direction = 1 if ob_type == "BULLISH" else -1
                tp = smc.get_trend_target(recent_data, direction)
                if tp is None:
                    self.logger.error("❌ TP hesaplanamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ TP hesaplama hatası: {e}")
                return None

            # Setup verisi oluştur
            return {
                "type": "PO3",
                "direction": "LONG" if ob_type == "BULLISH" else "SHORT",
                "entry": ob_price,
                "stop": ob_sl_level,
                "tp": float(tp),
                "setup_quality": setup_quality,
                "ob": ob,
                "pd_zone": pd_zone,
                "timestamp": recent_data.index[-1],
                "timeframe": "current",
                "status": "ACTIVE"
            }

        except Exception as e:
            self.logger.error(f"❌ PO3 tespit hatası: {e}")
            return None

class SBSModel(ICTModel):
    """
    SBS (Smart Breakout Strategy) - Akıllı Kırılım Stratejisi
    SBS, fiyatın önemli bir seviyeyi kırması ve geri test etmesine dayanır.
    """
    def __init__(self):
        super().__init__()
        self.min_data_length = 20

    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """SBS setup'ını tespit eder"""
        try:
            # Temel veri doğrulama
            if not self._validate_data(ohlc, min_length=100):
                self.logger.error("❌ Veri doğrulama başarısız")
                return None

            # Son verileri güvenli şekilde al
            try:
                if len(ohlc) < 20:
                    self.logger.error("❌ Yetersiz veri uzunluğu")
                    return None
                recent_data = ohlc.tail(20).copy()
                if recent_data.empty:
                    self.logger.error("❌ Son veri alınamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Son veri alma hatası: {e}")
                return None

            # Momentum teyidi
            if not smc.confirm_momentum(recent_data):
                self.logger.debug("Momentum teyidi başarısız")
                return None
                
            # Killzone kontrolü
            if not smc.is_in_killzone():
                self.logger.debug("Killzone'da değil")
                return None

            # Kırılım kontrolü
            try:
                breakout = smc.detect_breakout(recent_data)
                if not isinstance(breakout, dict):
                    return None
                    
                breakout_type = self._safe_get_dict_item(breakout, "type")
                breakout_price = self._safe_get_dict_item(breakout, "price")
                breakout_level = self._safe_get_dict_item(breakout, "level")
                
                if breakout_type is None or breakout_price is None or breakout_level is None:
                    self.logger.error("❌ Kırılım verisi eksik")
                    return None
                    
                try:
                    breakout_price = float(breakout_price)
                    breakout_level = float(breakout_level)
                except (TypeError, ValueError):
                    self.logger.error("❌ Kırılım değerleri dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Kırılım hatası: {e}")
                return None

            # Geri test kontrolü
            try:
                retest = smc.detect_retest(recent_data, breakout)
                if not isinstance(retest, dict):
                    return None
                    
                retest_price = self._safe_get_dict_item(retest, "price")
                retest_sl = self._safe_get_dict_item(retest, "sl_level")
                
                if retest_price is None or retest_sl is None:
                    self.logger.error("❌ Geri test verisi eksik")
                    return None
                    
                try:
                    retest_price = float(retest_price)
                    retest_sl = float(retest_sl)
                except (TypeError, ValueError):
                    self.logger.error("❌ Geri test değerleri dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Geri test hatası: {e}")
                return None

            # Setup kalitesi hesaplama
            try:
                # Son 3 mumu al
                last_candles = recent_data.tail(3)
                
                # Hareket büyüklüğü
                move_size = abs(float(last_candles.iloc[-1]["close"]) - float(last_candles.iloc[-2]["close"]))
                avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                avg_move = float(avg_range.mean())
                
                # Hacim teyidi
                volume_quality = 1.0
                if "volume" in recent_data.columns:
                    curr_volume = float(last_candles.iloc[-1]["volume"])
                    avg_volume = float(recent_data["volume"].mean())
                    volume_quality = min(curr_volume / avg_volume, 1.0)
                    
                # Kırılım kalitesi
                breakout_quality = min(abs(breakout_price - breakout_level) / avg_move, 1.0)
                    
                # Toplam kalite
                setup_quality = min((move_size / avg_move) * volume_quality * breakout_quality, 1.0)
                
            except Exception as e:
                self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                setup_quality = 0.5  # Varsayılan değer

            # TP hesaplama
            try:
                direction = 1 if breakout_type == "BULLISH" else -1
                tp = smc.get_trend_target(recent_data, direction)
                if tp is None:
                    self.logger.error("❌ TP hesaplanamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ TP hesaplama hatası: {e}")
                return None

            # Setup verisi oluştur
            return {
                "type": "SBS",
                "direction": "LONG" if breakout_type == "BULLISH" else "SHORT",
                "entry": retest_price,
                "stop": retest_sl,
                "tp": float(tp),
                "setup_quality": setup_quality,
                "breakout": breakout,
                "retest": retest,
                "timestamp": recent_data.index[-1],
                "timeframe": "current",
                "status": "ACTIVE"
            }

        except Exception as e:
            self.logger.error(f"❌ SBS tespit hatası: {e}")
            return None

class IMBALANCEPLAYModel(ICTModel):
    """
    Imbalance Play (Fiyat Dengesizlikleri)
    Piyasa, boşlukları doldurur. FVG (Fair Value Gap) veya Liquidity Void varsa, fiyat burayı doldurduktan sonra yön değiştirir.
    """
    def __init__(self):
        super().__init__()
        self.min_data_length = 20

    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Imbalance Play setup'ını tespit eder"""
        try:
            # Temel veri doğrulama
            if not self._validate_data(ohlc, min_length=100):
                self.logger.error("❌ Veri doğrulama başarısız")
                return None

            # Son verileri güvenli şekilde al
            try:
                if len(ohlc) < 20:
                    self.logger.error("❌ Yetersiz veri uzunluğu")
                    return None
                recent_data = ohlc.tail(20).copy()
                if recent_data.empty:
                    self.logger.error("❌ Son veri alınamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Son veri alma hatası: {e}")
                return None

            # HTF'de (4H / 1D) büyük bir Imbalance kontrolü - güvenli erişim
            try:
                htf_imbalance = smc.detect_htf_imbalance(recent_data)
                if not isinstance(htf_imbalance, dict):
                    return None
                    
                imbalance_type = self._safe_get_dict_item(htf_imbalance, "type")
                imbalance_price = self._safe_get_dict_item(htf_imbalance, "price")
                imbalance_extreme = self._safe_get_dict_item(htf_imbalance, "extreme")
                imbalance_direction = self._safe_get_dict_item(htf_imbalance, "direction")
                
                if (imbalance_type is None or imbalance_price is None or 
                    imbalance_extreme is None or imbalance_direction is None):
                    self.logger.error("❌ HTF Imbalance verisi eksik")
                    return None
                    
                try:
                    imbalance_price = float(imbalance_price)
                    imbalance_extreme = float(imbalance_extreme)
                    imbalance_direction = int(imbalance_direction)
                except (TypeError, ValueError):
                    self.logger.error("❌ Imbalance değerleri dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ HTF Imbalance hatası: {e}")
                return None

            # Mean Reversion kontrolü
            if not smc.is_filling_imbalance(recent_data, htf_imbalance):
                return None

            # OB/FVG kontrolü - güvenli erişim
            try:
                ob = smc.detect_ob(recent_data)
                fvg = smc.detect_fvg(recent_data)

                if ob is not None and not isinstance(ob, dict):
                    ob = None
                if fvg is not None and not isinstance(fvg, dict):
                    fvg = None

                if not (ob or fvg):
                    self.logger.error("❌ OB veya FVG bulunamadı")
                    return None

                # Entry price'ı güvenli şekilde al
                entry = None
                if ob:
                    entry = self._safe_get_dict_item(ob, "price")
                if entry is None and fvg:
                    entry = self._safe_get_dict_item(fvg, "price")

                if entry is None:
                    self.logger.error("❌ Entry hesaplanamadı")
                    return None

                try:
                    entry = float(entry)
                except (TypeError, ValueError):
                    self.logger.error("❌ Entry fiyatı sayıya dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ OB/FVG hatası: {e}")
                return None

            # Geri dönüş kontrolü
            if not smc.is_returning_to_ob_fvg(recent_data, ob if ob else fvg):
                return None

            # Momentum teyidi
            if not smc.confirm_momentum(recent_data):
                return None

            # TP hesaplama - güvenli erişim
            try:
                tp = smc.get_previous_liquidity_level(recent_data)
                if tp is None:
                    self.logger.error("❌ TP hesaplanamadı")
                    return None

                try:
                    tp = float(tp)
                except (TypeError, ValueError):
                    self.logger.error("❌ TP değeri sayıya dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ TP hesaplama hatası: {e}")
                return None

            # Setup verisi oluştur
            setup_data = {
                "setup": "IMBALANCE_PLAY",
                "direction": "LONG" if imbalance_direction == 1 else "SHORT",
                "entry": entry,
                "sl": imbalance_extreme,
                "tp": tp,
                "htf_imbalance": htf_imbalance,
                "ob": ob,
                "fvg": fvg,
                "timestamp": pd.Timestamp.now(),
                "timeframe": "current",
                "status": "ACTIVE"
            }

            # Son kontrol
            required_fields = ["setup", "direction", "entry", "sl", "tp"]
            if not self._validate_setup_data(setup_data, required_fields):
                self.logger.error("❌ Setup verisi doğrulama başarısız")
                return None

            return setup_data

        except Exception as e:
            self.logger.error(f"❌ Imbalance Play tespit hatası: {e}")
            return None

class SMTDivergenceModel(ICTModel):
    """
    SMT Divergence (Smart Money Divergence) - Akıllı Para Uyumsuzluğu
    SMT Divergence, fiyat ve momentum göstergeleri arasındaki uyumsuzluğa dayanır.
    """
    def __init__(self):
        super().__init__()
        self.min_data_length = 20

    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """SMT Divergence setup'ını tespit eder"""
        try:
            # Temel veri doğrulama
            if not self._validate_data(ohlc, min_length=100):
                self.logger.error("❌ Veri doğrulama başarısız")
                return None

            # Son verileri güvenli şekilde al
            try:
                if len(ohlc) < 20:
                    self.logger.error("❌ Yetersiz veri uzunluğu")
                    return None
                recent_data = ohlc.tail(20).copy()
                if recent_data.empty:
                    self.logger.error("❌ Son veri alınamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Son veri alma hatası: {e}")
                return None

            # Momentum teyidi
            if not smc.confirm_momentum(recent_data):
                self.logger.debug("Momentum teyidi başarısız")
                return None
                
            # Killzone kontrolü
            if not smc.is_in_killzone():
                self.logger.debug("Killzone'da değil")
                return None

            # Divergence kontrolü
            try:
                divergence = smc.detect_divergence(recent_data)
                if not isinstance(divergence, dict):
                    return None
                    
                div_type = self._safe_get_dict_item(divergence, "type")
                div_price = self._safe_get_dict_item(divergence, "price")
                div_sl = self._safe_get_dict_item(divergence, "sl_level")
                
                if div_type is None or div_price is None or div_sl is None:
                    self.logger.error("❌ Divergence verisi eksik")
                    return None
                    
                try:
                    div_price = float(div_price)
                    div_sl = float(div_sl)
                except (TypeError, ValueError):
                    self.logger.error("❌ Divergence değerleri dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Divergence hatası: {e}")
                return None

            # Setup kalitesi hesaplama
            try:
                # Son 3 mumu al
                last_candles = recent_data.tail(3)
                
                # Hareket büyüklüğü
                move_size = abs(float(last_candles.iloc[-1]["close"]) - float(last_candles.iloc[-2]["close"]))
                avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                avg_move = float(avg_range.mean())
                
                # Hacim teyidi
                volume_quality = 1.0
                if "volume" in recent_data.columns:
                    curr_volume = float(last_candles.iloc[-1]["volume"])
                    avg_volume = float(recent_data["volume"].mean())
                    volume_quality = min(curr_volume / avg_volume, 1.0)
                    
                # Divergence kalitesi
                div_quality = min(abs(float(last_candles.iloc[-1]["close"]) - div_price) / avg_move, 1.0)
                    
                # Toplam kalite
                setup_quality = min((move_size / avg_move) * volume_quality * div_quality, 1.0)
                
            except Exception as e:
                self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                setup_quality = 0.5  # Varsayılan değer

            # TP hesaplama
            try:
                direction = 1 if div_type == "BULLISH" else -1
                tp = smc.get_trend_target(recent_data, direction)
                if tp is None:
                    self.logger.error("❌ TP hesaplanamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ TP hesaplama hatası: {e}")
                return None

            # Setup verisi oluştur
            return {
                "type": "SMT_DIVERGENCE",
                "direction": "LONG" if div_type == "BULLISH" else "SHORT",
                "entry": div_price,
                "stop": div_sl,
                "tp": float(tp),
                "setup_quality": setup_quality,
                "divergence": divergence,
                "timestamp": recent_data.index[-1],
                "timeframe": "current",
                "status": "ACTIVE"
            }

        except Exception as e:
            self.logger.error(f"❌ SMT Divergence tespit hatası: {e}")
            return None

class BPRModel(ICTModel):
    """
    BPR (Break of Previous Range) - Önceki Range Kırılımı
    BPR, önceki range'in kırılması ve geri test edilmesine dayanır.
    """
    def __init__(self):
        super().__init__()
        self.min_data_length = 20

    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """BPR setup'ını tespit eder"""
        try:
            # Temel veri doğrulama
            if not self._validate_data(ohlc, min_length=100):
                self.logger.error("❌ Veri doğrulama başarısız")
                return None

            # Son verileri güvenli şekilde al
            try:
                if len(ohlc) < 20:
                    self.logger.error("❌ Yetersiz veri uzunluğu")
                    return None
                recent_data = ohlc.tail(20).copy()
                if recent_data.empty:
                    self.logger.error("❌ Son veri alınamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Son veri alma hatası: {e}")
                return None

            # Momentum teyidi
            if not smc.confirm_momentum(recent_data):
                self.logger.debug("Momentum teyidi başarısız")
                return None
                
            # Killzone kontrolü
            if not smc.is_in_killzone():
                self.logger.debug("Killzone'da değil")
                return None

            # Range kontrolü
            try:
                prev_range = smc.detect_previous_range(recent_data)
                if not isinstance(prev_range, dict):
                    return None
                    
                range_high = self._safe_get_dict_item(prev_range, "high")
                range_low = self._safe_get_dict_item(prev_range, "low")
                range_type = self._safe_get_dict_item(prev_range, "type")
                
                if range_high is None or range_low is None or range_type is None:
                    self.logger.error("❌ Range verisi eksik")
                    return None
                    
                try:
                    range_high = float(range_high)
                    range_low = float(range_low)
                except (TypeError, ValueError):
                    self.logger.error("❌ Range değerleri dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Range hatası: {e}")
                return None

            # Kırılım kontrolü
            try:
                breakout = smc.detect_range_breakout(recent_data, prev_range)
                if not isinstance(breakout, dict):
                    return None
                    
                breakout_price = self._safe_get_dict_item(breakout, "price")
                breakout_type = self._safe_get_dict_item(breakout, "type")
                
                if breakout_price is None or breakout_type is None:
                    self.logger.error("❌ Kırılım verisi eksik")
                    return None
                    
                try:
                    breakout_price = float(breakout_price)
                except (TypeError, ValueError):
                    self.logger.error("❌ Kırılım fiyatı dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Kırılım hatası: {e}")
                return None

            # Setup kalitesi hesaplama
            try:
                # Son 3 mumu al
                last_candles = recent_data.tail(3)
                
                # Hareket büyüklüğü
                move_size = abs(float(last_candles.iloc[-1]["close"]) - float(last_candles.iloc[-2]["close"]))
                avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                avg_move = float(avg_range.mean())
                
                # Hacim teyidi
                volume_quality = 1.0
                if "volume" in recent_data.columns:
                    curr_volume = float(last_candles.iloc[-1]["volume"])
                    avg_volume = float(recent_data["volume"].mean())
                    volume_quality = min(curr_volume / avg_volume, 1.0)
                    
                # Range kalitesi
                range_size = range_high - range_low
                range_quality = min(range_size / avg_move, 1.0)
                    
                # Toplam kalite
                setup_quality = min((move_size / avg_move) * volume_quality * range_quality, 1.0)
                
            except Exception as e:
                self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                setup_quality = 0.5  # Varsayılan değer

            # TP hesaplama
            try:
                direction = 1 if breakout_type == "BULLISH" else -1
                tp = smc.get_trend_target(recent_data, direction)
                if tp is None:
                    self.logger.error("❌ TP hesaplanamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ TP hesaplama hatası: {e}")
                return None

            # Setup verisi oluştur
            return {
                "type": "BPR",
                "direction": "LONG" if breakout_type == "BULLISH" else "SHORT",
                "entry": breakout_price,
                "stop": range_low if breakout_type == "BULLISH" else range_high,
                "tp": float(tp),
                "setup_quality": setup_quality,
                "range": prev_range,
                "breakout": breakout,
                "timestamp": recent_data.index[-1],
                "timeframe": "current",
                "status": "ACTIVE"
            }

        except Exception as e:
            self.logger.error(f"❌ BPR tespit hatası: {e}")
            return None

class BREADBUTTERModel(ICTModel):
    def __init__(self):
        super().__init__()
        self.min_data_length = 20
        
    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Bread & Butter pattern tespiti"""
        try:
            if not self._validate_data(ohlc, self.min_data_length):
                return None
                
            # Son 20 mumu al
            recent_data = ohlc.tail(self.min_data_length).copy()
            
            # Momentum teyidi
            if not smc.confirm_momentum(recent_data):
                self.logger.debug("Momentum teyidi başarısız")
                return None
                
            # Killzone kontrolü
            if not smc.is_in_killzone():
                self.logger.debug("Killzone'da değil")
                return None
                
            # FVG kontrolü
            fvg = smc.fvg(recent_data)
            if not fvg:
                return None
                
            # Son 3 mumu al
            last_candles = recent_data.tail(3)
            if len(last_candles) < 3:
                return None
                
            # Setup kalitesi hesaplama
            try:
                # Hareket büyüklüğü
                move_size = abs(float(last_candles.iloc[-1]["close"]) - float(last_candles.iloc[-2]["close"]))
                avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                avg_move = float(avg_range.mean())
                
                # Hacim teyidi
                volume_quality = 1.0
                if "volume" in recent_data.columns:
                    curr_volume = float(last_candles.iloc[-1]["volume"])
                    avg_volume = float(recent_data["volume"].mean())
                    volume_quality = min(curr_volume / avg_volume, 1.0)
                    
                # FVG kalitesi
                fvg_quality = min(abs(float(fvg["size"])) / avg_move, 1.0)
                    
                # Toplam kalite
                setup_quality = min((move_size / avg_move) * volume_quality * fvg_quality, 1.0)
                
            except Exception as e:
                self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                setup_quality = 0.5  # Varsayılan değer
                
            # Bullish Bread & Butter
            if fvg["direction"] == 1:
                if float(last_candles.iloc[-1]["close"]) > float(last_candles.iloc[-2]["high"]) and \
                   float(last_candles.iloc[-2]["low"]) > float(last_candles.iloc[-3]["high"]):
                    
                    # TP hesaplama
                    try:
                        tp = smc.get_trend_target(recent_data, 1)  # Yukarı hedef
                        if tp is None:
                            self.logger.error("❌ TP hesaplanamadı")
                            return None
                    except Exception as e:
                        self.logger.error(f"❌ TP hesaplama hatası: {e}")
                        return None
                    
                    return {
                        "type": "BULLISH_BREAD_BUTTER",
                        "direction": 1,
                        "entry": float(last_candles.iloc[-1]["close"]),
                        "stop": float(last_candles.iloc[-3]["low"]),
                        "tp": float(tp),
                        "setup_quality": setup_quality,
                        "fvg": fvg,
                        "timestamp": recent_data.index[-1],
                        "timeframe": "current",
                        "status": "ACTIVE"
                    }
                    
            # Bearish Bread & Butter
            if fvg["direction"] == -1:
                if float(last_candles.iloc[-1]["close"]) < float(last_candles.iloc[-2]["low"]) and \
                   float(last_candles.iloc[-2]["high"]) < float(last_candles.iloc[-3]["low"]):
                    
                    # TP hesaplama
                    try:
                        tp = smc.get_trend_target(recent_data, -1)  # Aşağı hedef
                        if tp is None:
                            self.logger.error("❌ TP hesaplanamadı")
                            return None
                    except Exception as e:
                        self.logger.error(f"❌ TP hesaplama hatası: {e}")
                        return None
                    
                    return {
                        "type": "BEARISH_BREAD_BUTTER",
                        "direction": -1,
                        "entry": float(last_candles.iloc[-1]["close"]),
                        "stop": float(last_candles.iloc[-3]["high"]),
                        "tp": float(tp),
                        "setup_quality": setup_quality,
                        "fvg": fvg,
                        "timestamp": recent_data.index[-1],
                        "timeframe": "current",
                        "status": "ACTIVE"
                    }
                    
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Bread & Butter tespit hatası: {e}")
            return None

class INDUCEMENTModel(ICTModel):
    """
    Inducement (Likidite Tuzağı) Setup'ı
    Piyasa yapıcılar, büyük pozisyonlar almadan önce likidite tuzakları kurarlar.
    Bu tuzaklar genellikle önemli destek/direnç seviyelerinde oluşur.
    """
    def __init__(self):
        super().__init__()
        self.min_data_length = 20

    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """Inducement setup'ını tespit eder"""
        try:
            # Temel veri doğrulama
            if not self._validate_data(ohlc, min_length=100):
                self.logger.error("❌ Veri doğrulama başarısız")
                return None

            # Son verileri güvenli şekilde al
            try:
                if len(ohlc) < 20:
                    self.logger.error("❌ Yetersiz veri uzunluğu")
                    return None
                recent_data = ohlc.tail(20).copy()
                if recent_data.empty:
                    self.logger.error("❌ Son veri alınamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Son veri alma hatası: {e}")
                return None

            # Momentum teyidi
            if not smc.confirm_momentum(recent_data):
                self.logger.debug("Momentum teyidi başarısız")
                return None
                
            # Killzone kontrolü
            if not smc.is_in_killzone():
                self.logger.debug("Killzone'da değil")
                return None

            # Likidite birikimi kontrolü
            try:
                liquidity = smc.detect_liquidity_buildup(recent_data)
                if not isinstance(liquidity, dict):
                    return None
                    
                liquidity_side = self._safe_get_dict_item(liquidity, "side")
                liquidity_volume = self._safe_get_dict_item(liquidity, "volume")
                
                if liquidity_side is None or liquidity_volume is None:
                    self.logger.error("❌ Likidite verisi eksik")
                    return None
                    
                try:
                    liquidity_volume = float(liquidity_volume)
                except (TypeError, ValueError):
                    self.logger.error("❌ Likidite değerleri dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Likidite birikimi hatası: {e}")
                return None

            # Tuzak kontrolü
            try:
                trap = smc.detect_trap_pattern(recent_data)
                if not isinstance(trap, dict):
                    return None
                    
                trap_type = self._safe_get_dict_item(trap, "type")
                trap_price = self._safe_get_dict_item(trap, "price")
                
                if trap_type is None or trap_price is None:
                    self.logger.error("❌ Tuzak verisi eksik")
                    return None
                    
                try:
                    trap_price = float(trap_price)
                except (TypeError, ValueError):
                    self.logger.error("❌ Tuzak fiyatı dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Tuzak tespit hatası: {e}")
                return None

            # Setup kalitesi hesaplama
            try:
                # Hareket büyüklüğü
                last_candles = recent_data.tail(3)
                move_size = abs(float(last_candles.iloc[-1]["close"]) - float(last_candles.iloc[-2]["close"]))
                avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                avg_move = float(avg_range.mean())
                
                # Hacim teyidi
                volume_quality = 1.0
                if "volume" in recent_data.columns:
                    curr_volume = float(last_candles.iloc[-1]["volume"])
                    avg_volume = float(recent_data["volume"].mean())
                    volume_quality = min(curr_volume / avg_volume, 1.0)
                    
                # Likidite kalitesi
                liquidity_quality = min(liquidity_volume / avg_volume, 1.0)
                    
                # Toplam kalite
                setup_quality = min((move_size / avg_move) * volume_quality * liquidity_quality, 1.0)
                
            except Exception as e:
                self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                setup_quality = 0.5  # Varsayılan değer

            # Bullish Inducement
            if trap_type == "BULLISH_TRAP":
                # TP hesaplama
                try:
                    tp = smc.get_trend_target(recent_data, 1)  # Yukarı hedef
                    if tp is None:
                        self.logger.error("❌ TP hesaplanamadı")
                        return None
                except Exception as e:
                    self.logger.error(f"❌ TP hesaplama hatası: {e}")
                    return None
                    
                return {
                    "type": "BULLISH_INDUCEMENT",
                    "direction": 1,
                    "entry": float(last_candles.iloc[-1]["close"]),
                    "stop": trap_price,
                    "tp": float(tp),
                    "setup_quality": setup_quality,
                    "liquidity": liquidity,
                    "trap": trap,
                    "timestamp": recent_data.index[-1],
                    "timeframe": "current",
                    "status": "ACTIVE"
                }
                    
            # Bearish Inducement
            if trap_type == "BEARISH_TRAP":
                # TP hesaplama
                try:
                    tp = smc.get_trend_target(recent_data, -1)  # Aşağı hedef
                    if tp is None:
                        self.logger.error("❌ TP hesaplanamadı")
                        return None
                except Exception as e:
                    self.logger.error(f"❌ TP hesaplama hatası: {e}")
                    return None
                    
                return {
                    "type": "BEARISH_INDUCEMENT",
                    "direction": -1,
                    "entry": float(last_candles.iloc[-1]["close"]),
                    "stop": trap_price,
                    "tp": float(tp),
                    "setup_quality": setup_quality,
                    "liquidity": liquidity,
                    "trap": trap,
                    "timestamp": recent_data.index[-1],
                    "timeframe": "current",
                    "status": "ACTIVE"
                }
                    
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Inducement tespit hatası: {e}")
            return None

class MMXMModel(ICTModel):
    """
    MMXM (Market Maker Execution Model) - Piyasa Yapıcı İşlem Modeli
    
    MMBM (Market Maker Buy Model) ve MMSM (Market Maker Sell Model) olmak üzere iki durumu vardır.
    
    Beş aşamada çalışır:
    1. Original Consolidation - İlk konsolidasyon
    2. Price Run - Fiyat hareketi
    3. Smart Money Reversal - Akıllı para dönüşü
    4. Accumulation/Distribution - Birikim/Dağıtım
    5. Completion - Tamamlanma
    
    Kullanılan göstergeler:
    - SMT Divergence: İlgili varlıklar arasındaki uyumsuzluk
    - Liquidity Sweep: Likidite bölgelerinin süpürülmesi
    - HTF PD Array: Yüksek zaman dilimlerindeki premium/discount bölgeleri
    - MSS/ChoCh: Market yapısı değişimi
    - CISD: Fiyat dağıtım mekanizmasındaki değişim
    - FVG: Fair Value Gap
    """
    def __init__(self):
        super().__init__()
        self.min_data_length = 50  # En az 50 mum gerekli

    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """MMXM setup'ını tespit eder"""
        try:
            # Temel veri doğrulama
            if not self._validate_data(ohlc, min_length=100):
                self.logger.error("❌ Veri doğrulama başarısız")
                return None

            # Son verileri güvenli şekilde al
            try:
                if len(ohlc) < 50:
                    self.logger.error("❌ Yetersiz veri uzunluğu")
                    return None
                recent_data = ohlc.tail(50).copy()
                if recent_data.empty:
                    self.logger.error("❌ Son veri alınamadı")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Son veri alma hatası: {e}")
                return None

            # 1. SMT Divergence kontrolü
            try:
                divergence = smc.detect_divergence(recent_data)
                if not isinstance(divergence, dict):
                    return None
                    
                div_type = self._safe_get_dict_item(divergence, "type")
                div_strength = self._safe_get_dict_item(divergence, "strength")
                
                if div_type is None or div_strength is None:
                    self.logger.error("❌ Divergence verisi eksik")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Divergence hatası: {e}")
                return None

            # 2. Likidite Sweep kontrolü
            try:
                sweep = smc.detect_liquidity_sweep(recent_data)
                if not isinstance(sweep, dict):
                    return None
                    
                sweep_type = self._safe_get_dict_item(sweep, "type")
                sweep_price = self._safe_get_dict_item(sweep, "price")
                
                if sweep_type is None or sweep_price is None:
                    self.logger.error("❌ Sweep verisi eksik")
                    return None
                    
                try:
                    sweep_price = float(sweep_price)
                except (TypeError, ValueError):
                    self.logger.error("❌ Sweep fiyatı dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Sweep hatası: {e}")
                return None

            # 3. HTF PD Array kontrolü
            try:
                pd_array = smc.detect_pd_array(recent_data)
                if not isinstance(pd_array, dict):
                    return None
                    
                pd_type = self._safe_get_dict_item(pd_array, "type")
                pd_level = self._safe_get_dict_item(pd_array, "level")
                
                if pd_type is None or pd_level is None:
                    self.logger.error("❌ PD Array verisi eksik")
                    return None
                    
                try:
                    pd_level = float(pd_level)
                except (TypeError, ValueError):
                    self.logger.error("❌ PD level dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ PD Array hatası: {e}")
                return None

            # 4. Market Structure Shift kontrolü
            try:
                mss = smc.detect_market_structure_shift(recent_data)
                if not isinstance(mss, dict):
                    return None
                    
                mss_type = self._safe_get_dict_item(mss, "type")
                mss_level = self._safe_get_dict_item(mss, "level")
                
                if mss_type is None or mss_level is None:
                    self.logger.error("❌ MSS verisi eksik")
                    return None
                    
                try:
                    mss_level = float(mss_level)
                except (TypeError, ValueError):
                    self.logger.error("❌ MSS level dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ MSS hatası: {e}")
                return None

            # 5. CISD kontrolü
            try:
                cisd = smc.detect_cisd(recent_data)
                if not isinstance(cisd, dict):
                    return None
                    
                cisd_type = self._safe_get_dict_item(cisd, "type")
                cisd_confirmed = self._safe_get_dict_item(cisd, "confirmed")
                
                if cisd_type is None or cisd_confirmed is None:
                    self.logger.error("❌ CISD verisi eksik")
                    return None
            except Exception as e:
                self.logger.error(f"❌ CISD hatası: {e}")
                return None

            # 6. FVG kontrolü
            try:
                fvg = smc.detect_fvg(recent_data)
                if not isinstance(fvg, dict):
                    return None
                    
                fvg_type = self._safe_get_dict_item(fvg, "type")
                fvg_price = self._safe_get_dict_item(fvg, "price")
                
                if fvg_type is None or fvg_price is None:
                    self.logger.error("❌ FVG verisi eksik")
                    return None
                    
                try:
                    fvg_price = float(fvg_price)
                except (TypeError, ValueError):
                    self.logger.error("❌ FVG fiyatı dönüştürülemedi")
                    return None
            except Exception as e:
                self.logger.error(f"❌ FVG hatası: {e}")
                return None

            # Setup kalitesi hesaplama
            try:
                # Son 3 mumu al
                last_candles = recent_data.tail(3)
                
                # Hareket büyüklüğü
                move_size = abs(float(last_candles.iloc[-1]["close"]) - float(last_candles.iloc[-2]["close"]))
                avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                avg_move = float(avg_range.mean())
                
                # Hacim teyidi
                volume_quality = 1.0
                if "volume" in recent_data.columns:
                    curr_volume = float(last_candles.iloc[-1]["volume"])
                    avg_volume = float(recent_data["volume"].mean())
                    volume_quality = min(curr_volume / avg_volume, 1.0)
                    
                # Divergence kalitesi
                div_quality = min(float(div_strength), 1.0)
                    
                # Toplam kalite
                setup_quality = min((move_size / avg_move) * volume_quality * div_quality, 1.0)
                
            except Exception as e:
                self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                setup_quality = 0.5  # Varsayılan değer

            # MMBM - Market Maker Buy Model
            if (div_type == "BULLISH" and
                sweep_type == "LOW_SWEEP" and
                pd_type == "DISCOUNT" and
                mss_type == "BULLISH" and
                cisd_confirmed and
                fvg_type == "BULLISH"):
                
                # TP hesaplama
                try:
                    tp = smc.get_trend_target(recent_data, 1)  # Yukarı hedef
                    if tp is None:
                        self.logger.error("❌ TP hesaplanamadı")
                        return None
                except Exception as e:
                    self.logger.error(f"❌ TP hesaplama hatası: {e}")
                    return None
                
                return {
                    "type": "MMBM",
                    "direction": 1,
                    "entry": fvg_price,  # FVG'de giriş
                    "stop": sweep_price * 0.999,  # Sweep seviyesinin altı
                    "tp": float(tp),
                    "setup_quality": setup_quality,
                    "divergence": divergence,
                    "sweep": sweep,
                    "pd_array": pd_array,
                    "mss": mss,
                    "cisd": cisd,
                    "fvg": fvg,
                    "timestamp": recent_data.index[-1],
                    "timeframe": "current",
                    "status": "ACTIVE"
                }

            # MMSM - Market Maker Sell Model
            elif (div_type == "BEARISH" and
                  sweep_type == "HIGH_SWEEP" and
                  pd_type == "PREMIUM" and
                  mss_type == "BEARISH" and
                  cisd_confirmed and
                  fvg_type == "BEARISH"):
                
                # TP hesaplama
                try:
                    tp = smc.get_trend_target(recent_data, -1)  # Aşağı hedef
                    if tp is None:
                        self.logger.error("❌ TP hesaplanamadı")
                        return None
                except Exception as e:
                    self.logger.error(f"❌ TP hesaplama hatası: {e}")
                    return None
                
                return {
                    "type": "MMSM",
                    "direction": -1,
                    "entry": fvg_price,  # FVG'de giriş
                    "stop": sweep_price * 1.001,  # Sweep seviyesinin üstü
                    "tp": float(tp),
                    "setup_quality": setup_quality,
                    "divergence": divergence,
                    "sweep": sweep,
                    "pd_array": pd_array,
                    "mss": mss,
                    "cisd": cisd,
                    "fvg": fvg,
                    "timestamp": recent_data.index[-1],
                    "timeframe": "current",
                    "status": "ACTIVE"
                }

            return None

        except Exception as e:
            self.logger.error(f"❌ MMXM tespit hatası: {e}")
            return None

class TGIFModel(ICTModel):
    def detect(self, ohlc: pd.DataFrame) -> Optional[Dict]:
        """TGIF setup tespiti"""
        try:
            if not self._validate_data(ohlc, min_length=50):
                return None
                
            # Son 50 mumu al
            recent_data = ohlc.tail(50).copy()
            if len(recent_data) < 50:
                self.logger.error("❌ TGIF için yetersiz veri")
                return None
                
            # Güvenli liste erişimi için son mumları al
            try:
                last_candles = recent_data.tail(5)
                if len(last_candles) < 5:
                    return None
                    
                # Son 5 mumun OHLC değerlerini al
                c1 = last_candles.iloc[0]
                c2 = last_candles.iloc[1]
                c3 = last_candles.iloc[2]
                c4 = last_candles.iloc[3]
                c5 = last_candles.iloc[4]
                
                # Momentum teyidi
                if not smc.confirm_momentum(recent_data):
                    self.logger.debug("Momentum teyidi başarısız")
                    return None
                    
                # Cuma günü kontrolü
                if not smc.is_friday():  # Sadece Cuma günleri
                    self.logger.debug("Cuma günü değil")
                    return None
                    
                # Setup kalitesi hesaplama
                try:
                    # Hareket büyüklüğü
                    move_size = abs(float(c5["close"]) - float(c4["close"]))
                    avg_range = recent_data["high"].astype(float) - recent_data["low"].astype(float)
                    avg_move = float(avg_range.mean())
                    
                    # Hacim teyidi
                    volume_quality = 1.0
                    if "volume" in recent_data.columns:
                        curr_volume = float(c5["volume"])
                        avg_volume = float(recent_data["volume"].mean())
                        volume_quality = min(curr_volume / avg_volume, 1.0)
                        
                    # Toplam kalite
                    setup_quality = min((move_size / avg_move) * volume_quality, 1.0)
                    
                except Exception as e:
                    self.logger.error(f"❌ Setup kalitesi hesaplama hatası: {e}")
                    setup_quality = 0.5  # Varsayılan değer
                
                # TGIF pattern kontrolü
                if (float(c5["close"]) < float(c4["low"]) and   # Bearish engulfing
                    float(c4["close"]) > float(c4["open"]) and  # Önceki mum yeşil
                    float(c3["low"]) < float(c4["low"]) and     # Düşük seviye kırıldı
                    float(c2["high"]) > float(c3["high"])):     # Yüksek seviye test edildi
                    
                    # TP hesaplama
                    try:
                        tp = smc.get_trend_target(recent_data, -1)  # Aşağı hedef
                        if tp is None:
                            self.logger.error("❌ TP hesaplanamadı")
                            return None
                    except Exception as e:
                        self.logger.error(f"❌ TP hesaplama hatası: {e}")
                        return None
                    
                    return {
                        "type": "TGIF",
                        "direction": -1,
                        "entry": float(c5["close"]),
                        "stop": float(c4["high"]),
                        "tp": float(tp),
                        "setup_quality": setup_quality,
                        "timestamp": recent_data.index[-1],
                        "timeframe": "current",
                        "status": "ACTIVE"
                    }
                    
                return None
                
            except (IndexError, KeyError) as e:
                self.logger.error(f"❌ TGIF veri erişim hatası: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ TGIF tespit hatası: {e}")
            return None

def get_ict_model(model_name: str, parameters: dict = None) -> ICTModel:
    """Model fabrikası (Factory) fonksiyonu; model adını alıp ilgili sınıfı döndürür."""
    models = {
        "bos_fvg": BOSFVGModel,
        "choch_ob": CHOCHOBModel,
        "ote": OTEModel,
        "silver_bullet": SILVERBULLETModel,
        "turtle_soup": TURTLESOUPModel,
        "london_reversal": LONDONREVERSALModel,
        "ny_reversal": NYREVERSALModel,
        "judas_swing": JUDASSWINGModel,
        "po3": PO3Model,
        "sbs": SBSModel,
        "imbalance_play": IMBALANCEPLAYModel,
        "smt_divergence": SMTDivergenceModel,
        "bpr": BPRModel,
        "bread_butter": BREADBUTTERModel,
        "inducement": INDUCEMENTModel,
        "mmxm": MMXMModel,
        "tgif": TGIFModel
    }
    model_class = models.get(model_name.lower())
    if model_class:
        return model_class(parameters)
    else:
        raise ValueError(f"Geçersiz ICT model adı: {model_name}")