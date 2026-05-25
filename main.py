from typing import Dict, List, Optional
import pandas as pd
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

# Model importları
from models.ict_models import (
    PO3Model, BOSFVGModel, CHOCHOBModel, OTEModel, 
    SILVERBULLETModel, LONDONREVERSALModel, NYREVERSALModel,
    TURTLESOUPModel, JUDASSWINGModel, SBSModel,
    INDUCEMENTModel, BREADBUTTERModel, MMXMModel, TGIFModel,
    IMBALANCEPLAYModel, SMTDivergenceModel, BPRModel
)

# ICT Tools importları
from models.ict_tools import smc

# Util importları
from utils.data_fetcher import DataFetcher
from utils.risk_manager import calculate_position_size, calculate_take_profit_levels, validate_risk_parameters, adjust_position_for_correlation
from utils.trade_manager import TradeManager
from utils.session_manager import SessionManager
from config.settings import exchange, timeframes

class ICTTrader:
    def __init__(self, config_path: str = 'config/settings.py'):
        """Trading sistemini başlat"""
        try:
            self.config = self._load_config(config_path)
            self._setup_logging()

            if "exchange" not in self.config:
                self.config["exchange"] = {}
            if "name" not in self.config["exchange"]:
                self.config["exchange"]["name"] = "bybit"
            if "demo" not in self.config["exchange"]:
                self.config["exchange"]["demo"] = True

            api_key = self.config["exchange"].get("api_key")
            api_secret = self.config["exchange"].get("api_secret")
            if not api_key or not api_secret:
                logging.warning("⚠️ API anahtarları eksik veya geçersiz")
                logging.warning("ℹ️ Testnet için: https://testnet.bybit.com/app/user/api-management")
                logging.warning("ℹ️ Mainnet için: https://www.bybit.com/app/user/api-management")
                logging.warning("⚠️ Sistem sadece market verisi çekebilecek, trading işlemleri devre dışı")
            
            self.data_fetcher = DataFetcher(
                api_key=api_key,
                api_secret=api_secret,
                demo=self.config["exchange"].get("demo", True)
            )
            if self.data_fetcher.client is None:
                raise Exception("DataFetcher başlatılamadı")
            
            self.trade_manager = TradeManager(
                trade_history_file=self.config["paths"].get("trade_history", "trade_history.json")
            )
            
            self.session_manager = SessionManager()
            self.data = {
                "htf": None,  # High Time Frame (4h)
                "h1": None,   # 1-hour data
                "ltf": None,  # Low Time Frame (15m)
                "mtf": None,  # Micro Time Frame (5m)
                "inm": None,  # 1-minute data (trade yönetimi için)
                "weekly": None,
                "daily": None
            }
            
            # Tüm modeller her timeframe'de çalışabilir
            all_models = [
                "po3", "judas_swing", "sbs", "bos_fvg", 
                "choch_ob", "inducement", "bread_butter",
                "silver_bullet", "london_reversal", "ny_reversal",
                "turtle_soup", "tgif", "mmxm", "ote",
                "imbalance", "smt_divergence", "bpr"
            ]
            
            self.timeframes = {
                "htf": {
                    "primary": "4h",
                    "secondary": ["1d", "1w"],
                    "models": all_models
                },
                "h1": {
                    "primary": "1h",
                    "secondary": [],
                    "models": all_models
                },
                "ltf": {
                    "primary": "15m",
                    "secondary": [],
                    "models": all_models
                },
                "mtf": {
                    "primary": "5m",
                    "secondary": ["1m"],
                    "models": all_models
                }
            }
            self.models = {
                "po3": PO3Model(),
                "bos_fvg": BOSFVGModel(),
                "choch_ob": CHOCHOBModel(),
                "ote": OTEModel(),
                "silver_bullet": SILVERBULLETModel(),
                "london_reversal": LONDONREVERSALModel(),
                "ny_reversal": NYREVERSALModel(),
                "turtle_soup": TURTLESOUPModel(),
                "judas_swing": JUDASSWINGModel(),
                "sbs": SBSModel(),
                "inducement": INDUCEMENTModel(),
                "bread_butter": BREADBUTTERModel(),
                "mmxm": MMXMModel(),
                "tgif": TGIFModel(),
                "imbalance": IMBALANCEPLAYModel(),
                "smt_divergence": SMTDivergenceModel(),
                "bpr": BPRModel()
            }
            self.model_emojis = {
                "silver_bullet": "🔫",
                "turtle_soup": "🐢",
                "london_reversal": "🎡",
                "ny_reversal": "🗽",
                "judas_swing": "🎯",
                "po3": "🎪",
                "sbs": "📊",
                "inducement": "🎣",
                "bread_butter": "🍞",
                "mmxm": "🎲",
                "tgif": "🎉",
                "imbalance": "⚖️",
                "smt_divergence": "📈",
                "bpr": "🎯",
                "bos_fvg": "🌊",
                "choch_ob": "🔄",
                "ote": "🎯"
            }
            logging.info("✅ Trading sistemi başlatıldı")
            logging.info("📊 Yüklenen modeller:")
            for model_name in self.models.keys():
                emoji = self.model_emojis.get(model_name, "❓")
                logging.info(f"  {emoji} {model_name.upper()}")
            
        except Exception as e:
            logging.error(f"❌ Sistem başlatma hatası: {e}")
            raise
            
    def _setup_logging(self):
        try:
            file_handler = RotatingFileHandler(
                filename=self.config["logging"]["file"],
                maxBytes=self.config["logging"]["max_size"],
                backupCount=self.config["logging"]["backup_count"],
                encoding='utf-8'
            )
            console_handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(self.config["logging"]["format"])
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            root_logger = logging.getLogger()
            root_logger.setLevel(self.config["logging"]["level"])
            root_logger.addHandler(file_handler)
            root_logger.addHandler(console_handler)
        except Exception as e:
            print(f"Logging yapılandırma hatası: {e}")
            raise
            
    def _load_config(self, config_path: str) -> Dict:
        try:
            config = {}
            with open(config_path) as f:
                exec(f.read(), {}, config)
            return config
        except Exception as e:
            logging.error(f"❌ Konfigürasyon yükleme hatası: {e}")
            raise
            
    def update_market_data(self, symbol: str) -> bool:
        """Market verilerini güncelle"""
        try:
            max_retries = self.config["scan_settings"]["max_retries"]
            retry_delay = self.config["scan_settings"]["retry_delay"]
            failed_timeframes = []
            
            # Gerekli veri uzunlukları - timeframe'e göre optimize edildi
            required_lengths = {
                "htf": 100,   # 4h için yaklaşık 50 gün
                "h1": 100,    # 1h için yaklaşık 12 gün
                "ltf": 100,   # 15m için yaklaşık 3 gün
                "mtf": 100,   # 5m için yaklaşık 1 gün
                "inm": 100,   # 1m için yaklaşık 5 saat
                "daily": 50,  # Günlük için yaklaşık 3 ay
                "weekly": 25   # Haftalık için 1 yıl
            }
            
            # Günlük ve haftalık veriler
            timeframes_info = {
                "1d": {"name": "daily", "display": "GÜNLÜK"},
                "1w": {"name": "weekly", "display": "HAFTALIK"}
            }
            
            for tf, info in timeframes_info.items():
                data = None
                retries = 0
                while retries < max_retries and (data is None or len(data) < required_lengths[info["name"]]):
                    try:
                        data = self.data_fetcher.fetch_ohlcv(
                            symbol=symbol,
                            timeframe=tf,
                            limit=required_lengths[info["name"]] * 2  # 2 katı veri çek
                        )
                        if data is not None and len(data) >= required_lengths[info["name"]]:
                            self.data[info["name"]] = data
                            break
                    except Exception as e:
                        logging.debug(f"❌ {info['display']} veri çekme hatası: {e}")
                        
                    retries += 1
                    time.sleep(retry_delay)
                
                if data is None or len(data) < required_lengths[info["name"]]:
                    failed_timeframes.append(info["name"])

            # 1h verisi
            h1_data = None
            retries = 0
            while retries < max_retries and (h1_data is None or len(h1_data) < required_lengths["h1"]):
                try:
                    h1_data = self.data_fetcher.fetch_ohlcv(
                        symbol=symbol,
                        timeframe="1h",
                        limit=required_lengths["h1"] * 2
                    )
                    if h1_data is not None and len(h1_data) >= required_lengths["h1"]:
                        self.data["h1"] = h1_data
                        break
                except Exception as e:
                    logging.debug(f"❌ 1H veri çekme hatası: {e}")
                    
                retries += 1
                time.sleep(retry_delay)

            if h1_data is None or len(h1_data) < required_lengths["h1"]:
                failed_timeframes.append("h1")

            # Normal timeframe'ler
            for tf_name, tf_config in self.timeframes.items():
                if tf_name == "h1":  # 1h verisi zaten çekildi
                    continue
                    
                data = None
                retries = 0
                while retries < max_retries and (data is None or len(data) < required_lengths[tf_name]):
                    try:
                        data = self.data_fetcher.fetch_ohlcv(
                            symbol=symbol,
                            timeframe=tf_config["primary"],
                            limit=required_lengths[tf_name] * 2
                        )
                        if data is not None and len(data) >= required_lengths[tf_name]:
                            self.data[tf_name] = data
                            break
                    except Exception as e:
                        logging.debug(f"❌ {tf_name.upper()} veri çekme hatası: {e}")
                        
                    retries += 1
                    time.sleep(retry_delay)
                
                if data is None or len(data) < required_lengths[tf_name]:
                    failed_timeframes.append(tf_name)

            # 1 dakikalık veri (trade yönetimi için)
            inm_data = None
            retries = 0
            while retries < max_retries and (inm_data is None or len(inm_data) < required_lengths["inm"]):
                try:
                    inm_data = self.data_fetcher.fetch_ohlcv(
                        symbol=symbol,
                        timeframe="1m",
                        limit=required_lengths["inm"] * 2
                    )
                    if inm_data is not None and len(inm_data) >= required_lengths["inm"]:
                        self.data["inm"] = inm_data
                        break
                except Exception as e:
                    logging.debug(f"❌ 1M veri çekme hatası: {e}")
                    
                retries += 1
                time.sleep(retry_delay)

            if inm_data is None or len(inm_data) < required_lengths["inm"]:
                failed_timeframes.append("inm")
            
            # Veri uzunluklarını logla
            logging.info("\n📊 Veri Uzunlukları:")
            for tf_name, data in self.data.items():
                if data is not None:
                    logging.info(f"  • {tf_name.upper()}: {len(data)} mum")
            
            # Sonuç raporu
            if failed_timeframes:
                failed_str = ", ".join(failed_timeframes)
                logging.error(f"❌ {symbol} için bazı timeframe'lerde yeterli veri alınamadı: {failed_str}")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"❌ {symbol} için veri güncelleme hatası: {e}")
            return False
            
    def _log_risk_status(self):
        """Risk durumunu logla"""
        try:
            account_balance = self.trade_manager.get_account_balance()
            daily_risk = self.trade_manager.get_daily_risk()
            open_trades = len(self.trade_manager.get_active_trades())
            
            logging.info("💰 Risk Durumu:")
            logging.info(f"  Bakiye: {account_balance:.2f} USDT")
            logging.info(f"  Günlük Risk: {daily_risk:.1f}%/{self.config['risk_management']['max_risk_per_day']}%")
            logging.info(f"  Açık Trade: {open_trades}/{self.config['risk_management']['max_open_trades']}")
        except Exception as e:
            logging.error(f"❌ Risk durumu hesaplama hatası: {e}")

    def _analyze_market_structure(self, symbol: str, data: pd.DataFrame) -> Dict:
        """Market yapısını analiz et"""
        try:
            # Swing noktaları tespit et
            swings = smc.swing_highs_lows(data, swing_length=10)  # 20'den 10'a düşürüldü
            if not isinstance(swings, dict):
                swings = {"HighLow": [], "Level": []}
            
            # BOS/CHOCH analizi
            bos_choch = smc.bos_choch(data, swings)
            if not isinstance(bos_choch, dict):
                bos_choch = {
                    "bos": {"type": None, "direction": None, "price": None, "timestamp": None},
                    "choch": {"type": None, "direction": None, "price": None, "timestamp": None}
                }
            
            # FVG analizi
            fvg = smc.fvg(data)
            if not isinstance(fvg, dict):
                fvg = {}
            
            # OB analizi
            ob = smc.ob(data)
            if not isinstance(ob, dict):
                ob = {}
            
            # Market yapısı loglaması
            def get_market_state(tf_data):
                swings = tf_data.get("swings", {})
                if not swings or not swings.get("HighLow"):
                    return "Range ➖"
                
                # Son 2 swing noktasına bak (3'ten 2'ye düşürüldü)
                last_swings = swings["HighLow"][-2:]
                
                # Yükselen trend
                if all(x == 1 for x in last_swings):
                    return "Bullish Swing 📈"
                # Düşen trend    
                elif all(x == -1 for x in last_swings):
                    return "Bearish Swing 📉"
                # Karışık hareket
                else:
                    return "Range ➖"
            
            market_structure = {
                "swings": swings,
                "bos_choch": bos_choch,
                "fvg": fvg,
                "ob": ob
            }
            
            # Market durumunu logla
            state = get_market_state(market_structure)
            logging.info(f"  • Market Durumu: {state}")
            
            # BOS/CHoCH durumunu logla
            bos = bos_choch.get("bos", {})
            choch = bos_choch.get("choch", {})
            
            if bos.get("type"):
                direction = "YUKARI 📈" if bos.get("direction") == 1 else "AŞAĞI 📉"
                logging.info(f"    ↳ BOS: {direction}")
            
            if choch.get("type"):
                direction = "YUKARI 📈" if choch.get("direction") == 1 else "AŞAĞI 📉"
                logging.info(f"    ↳ CHoCH: {direction}")
            
            return market_structure
            
        except Exception as e:
            logging.debug(f"❌ Market yapısı analizi hatası: {e}")
            return {}

    def _analyze_sessions(self) -> Dict:
        """Session durumunu analiz et"""
        try:
            sessions = {
                "london": self.session_manager.is_session_active("london"),
                "new_york": self.session_manager.is_session_active("new_york"),
                "asia": self.session_manager.is_session_active("asia")
            }
            
            # Session bilgilerini logla
            ny_time = self.session_manager.get_ny_time()
            logging.info(f"\n🕒 Seans Durumu (New York Saati: {ny_time})")
            session_emojis = {
                "london": "🇬🇧",
                "new_york": "🇺🇸",
                "asia": "🌏"
            }
            
            # Önce aktif killzone'ları göster
            current_killzone = self.session_manager.get_current_killzone()
            if current_killzone and current_killzone != "No Active Killzone":
                logging.info(f"⚔️ Aktif Killzone: {current_killzone}")
            
            # Sonra session durumlarını göster
            for session_name, is_active in sessions.items():
                emoji = session_emojis.get(session_name, "🌍")
                status = "🟢 Aktif" if is_active else "🔴 Kapalı"
                session_times = self.session_manager.get_session_times(session_name)
                if session_times:
                    start_time = session_times["start"].strftime("%H:%M")
                    end_time = session_times["end"].strftime("%H:%M")
                    logging.info(f"  {emoji} {session_name.upper()}: {status} ({start_time}-{end_time} NY)")
                else:
                    logging.info(f"  {emoji} {session_name.upper()}: {status}")
            
            return sessions
            
        except Exception as e:
            logging.error(f"❌ Session analizi hatası: {e}")
            return {}

    def analyze_market(self, symbol: str) -> Dict:
        """Piyasa analizi yap"""
        try:
            if not self.update_market_data(symbol):
                raise Exception("Market verileri güncellenemedi")
                
            analysis = {
                "symbol": symbol,
                "timestamp": pd.Timestamp.now(),
                "market_structure": {},
                "models": {},
                "tools": {},
                "volume": {},
                "session": {}
            }
            
            # Market yapısı analizi
            logging.info(f"\n📊 {symbol} Market Yapısı:")
            
            # Her timeframe için veri kontrolü
            timeframes = {
                "htf": {"name": "HTF (4H)", "data": self.data["htf"]},
                "h1": {"name": "1H", "data": self.data["h1"]},
                "ltf": {"name": "LTF (15M)", "data": self.data["ltf"]},
                "mtf": {"name": "MTF (5M)", "data": self.data["mtf"]}
            }
            
            for tf_key, tf_info in timeframes.items():
                if tf_info["data"] is not None and not tf_info["data"].empty:
                    try:
                        analysis["market_structure"][tf_key] = self._analyze_market_structure(symbol, tf_info["data"])
                        tf_state = self._get_market_state(analysis["market_structure"][tf_key])
                        logging.info(f"  • {tf_info['name']}: {tf_state}")
                    except Exception as e:
                        logging.error(f"❌ {tf_info['name']} analiz hatası: {e}")
                        analysis["market_structure"][tf_key] = {}

            # Her model için analiz yap
            for model_name, model_instance in self.models.items():
                try:
                    # Her timeframe için kontrol
                    for tf_key, tf_info in timeframes.items():
                        if tf_info["data"] is None or tf_info["data"].empty:
                            continue
                            
                        min_length = getattr(model_instance, "min_data_length", 100)
                        if len(tf_info["data"]) < min_length:
                            continue
                            
                        try:
                            # Son min_length kadar veriyi al
                            analysis_data = tf_info["data"].tail(min_length).copy()
                            if len(analysis_data) < min_length:
                                continue
                                
                            # Model analizi yap
                            result = model_instance.detect(analysis_data)
                            if result:
                                if model_name not in analysis["models"]:
                                    analysis["models"][model_name] = {}
                                analysis["models"][model_name][tf_key] = result
                                logging.info(f"  ✅ {self.model_emojis.get(model_name, '❓')} {model_name.upper()} {tf_info['name']} sinyali bulundu")
                        except Exception as e:
                            logging.debug(f"❌ {model_name} {tf_info['name']} analizi hatası: {e}")

                except Exception as e:
                    logging.debug(f"❌ {model_name} model analizi hatası: {e}")
                    continue
            
            # Session analizi
            analysis["session"] = self._analyze_sessions()
            
            # Özet rapor
            logging.info("\n📈 Analiz Özeti:")
            
            # Aktif modelleri logla
            active_models = []
            for model_name, timeframes in analysis["models"].items():
                if timeframes:  # Eğer herhangi bir timeframe'de sinyal varsa
                    active_models.append(f"{self.model_emojis.get(model_name, '❓')} {model_name.upper()}")
            
            if active_models:
                logging.info("  ✅ Aktif Modeller:")
                for model in active_models:
                    logging.info(f"    {model}")
            else:
                logging.info("  ❌ Aktif Model Yok")
            
            # Risk durumunu logla
            self._log_risk_status()
            
            # Fırsatları bul
            opportunities = self.find_entry_opportunities(analysis)
            if opportunities:
                logging.info(f"  🎯 {len(opportunities)} adet fırsat bulundu")
                for opportunity in opportunities:
                    if self.execute_trade(opportunity):
                        logging.info(f"  💫 {opportunity['model']} trade açıldı")
            else:
                logging.info("  ❗ Uygun fırsat bulunamadı")
            
            return analysis
            
        except Exception as e:
            logging.error(f"❌ Piyasa analizi hatası: {e}")
            return {}
            
    def _get_market_state(self, tf_data: Dict) -> str:
        """Market durumunu belirle"""
        try:
            swings = tf_data.get("swings", {})
            if not swings or not swings.get("HighLow"):
                return "Range ➖"
            
            # Son 2 swing noktasına bak
            last_swings = swings["HighLow"][-2:]
            
            # Yükselen trend
            if all(x == 1 for x in last_swings):
                return "Bullish Swing 📈"
            # Düşen trend    
            elif all(x == -1 for x in last_swings):
                return "Bearish Swing 📉"
            # Karışık hareket
            else:
                return "Range ➖"
        except Exception:
            return "Range ➖"

    def find_entry_opportunities(self, analysis: Dict) -> List[Dict]:
        try:
            opportunities = []
            
            # Her timeframe için modelleri kontrol et
            timeframe_data = {
                "ltf": self.data["ltf"],  # 15M
                "mtf": self.data["mtf"],  # 5M
                "inm": self.data["inm"]   # 1M
            }
            
            # Her model için kontrol et
            for model_name, model in analysis["models"].items():
                if not model:
                    continue
                    
                # Her timeframe için giriş fırsatı ara
                for tf_name, tf_data in timeframe_data.items():
                    if tf_data is None or tf_data.empty:
                        continue
                        
                    # Model nesnesini al
                    model_instance = self.models.get(model_name)
                    if not model_instance:
                        continue
                    
                    # Giriş fırsatı ara
                    entry = model_instance.find_entry(model, tf_data)
                    
                    if entry and entry.get("found", False):
                        opportunity = {
                            "model": model_name,
                            "timeframe": tf_name,
                            "entry": entry["entry"],
                            "stop": entry["stop"],
                            "setup_quality": entry["setup_quality"],
                            "direction": model["direction"],
                            "timestamp": pd.Timestamp.now(),
                            "context": {
                                "market_structure": analysis["market_structure"],
                                "volume": analysis["volume"],
                                "session": analysis["session"]
                            }
                        }
                        
                        # Risk parametrelerini kontrol et
                        risk_validation = validate_risk_parameters(
                            setup=opportunity,
                            account_size=self.trade_manager.get_account_balance(),
                            max_risk_per_trade=self.config["risk_management"]["risk_per_trade"]
                        )
                        
                        if risk_validation["is_valid"]:
                            # Timeframe'e göre setup kalitesini ayarla
                            if tf_name == "ltf":  # 15M
                                opportunity["setup_quality"] *= 1.0  # Normal kalite
                            elif tf_name == "mtf":  # 5M
                                opportunity["setup_quality"] *= 0.9  # Biraz daha düşük
                            elif tf_name == "inm":  # 1M
                                opportunity["setup_quality"] *= 0.8  # En düşük kalite
                                
                            opportunities.append(opportunity)
                            
                            # Setup'ı logla
                            emoji = self.model_emojis.get(model_name, "❓")
                            tf_display = {"ltf": "15M", "mtf": "5M", "inm": "1M"}
                            logging.info(f"  🎯 {emoji} {model_name.upper()} fırsatı bulundu ({tf_display[tf_name]})")
            
            return opportunities
            
        except Exception as e:
            logging.error(f"❌ Entry fırsatı arama hatası: {e}")
            return []
            
    def execute_trade(self, opportunity: Dict) -> bool:
        try:
            daily_risk = self.trade_manager.get_daily_risk()
            if daily_risk >= self.config["risk_management"]["max_risk_per_day"]:
                logging.warning(f"⚠️ Trade açılamadı: Günlük risk limiti doldu ({daily_risk:.1f}%/{self.config['risk_management']['max_risk_per_day']}%)")
                return False

            open_trades = len(self.trade_manager.get_active_trades())
            if open_trades >= self.config["risk_management"]["max_open_trades"]:
                logging.warning(f"⚠️ Trade açılamadı: Maksimum açık pozisyon sayısına ulaşıldı ({open_trades}/{self.config['risk_management']['max_open_trades']})")
                return False

            # 1 dakikalık veriyi kullanarak giriş fiyatını optimize et
            if self.data.get("inm") is not None and not self.data["inm"].empty:
                last_1m = self.data["inm"].iloc[-1]
                if opportunity["direction"] == "LONG":
                    # Long için en düşük fiyattan giriş yapmaya çalış
                    opportunity["entry"] = min(float(opportunity["entry"]), float(last_1m["low"]))
                else:
                    # Short için en yüksek fiyattan giriş yapmaya çalış
                    opportunity["entry"] = max(float(opportunity["entry"]), float(last_1m["high"]))

            position = calculate_position_size(
                account_size=self.trade_manager.get_account_balance(),
                risk_percentage=self.config["risk_management"]["risk_per_trade"],
                entry_price=opportunity["entry"],
                stop_loss=opportunity["stop"]
            )

            if position["size"] < self.config["risk_management"]["position_sizing"]["min_position"]:
                logging.warning(f"⚠️ Trade açılamadı: Pozisyon büyüklüğü çok küçük ({position['size']} < {self.config['risk_management']['position_sizing']['min_position']})")
                return False

            if position["size"] > self.config["risk_management"]["position_sizing"]["max_position"]:
                position["size"] = self.config["risk_management"]["position_sizing"]["max_position"]
                logging.info("ℹ️ Pozisyon büyüklüğü maksimum limite göre ayarlandı")

            # Setup kalitesi kontrolü
            if opportunity.get("setup_quality", 0) < self.config["risk_management"].get("min_setup_quality", 0.5):
                logging.warning(f"⚠️ Trade açılamadı: Setup kalitesi düşük ({opportunity.get('setup_quality', 0):.2f})")
                return False

            # Risk/Reward kontrolü
            entry = float(opportunity["entry"])
            stop = float(opportunity["stop"])
            tp = float(opportunity.get("tp", 0))
            
            if tp > 0:  # TP varsa R:R hesapla
                risk = abs(entry - stop)
                reward = abs(tp - entry)
                rr_ratio = reward / risk if risk > 0 else 0
                
                min_rr = self.config["risk_management"].get("min_risk_reward_ratio", 1.5)
                if rr_ratio < min_rr:
                    logging.warning(f"⚠️ Trade açılamadı: Risk/Reward oranı düşük ({rr_ratio:.2f} < {min_rr})")
                    return False

            if position["size"] < self.config["risk_management"]["position_sizing"]["min_position"]:
                logging.warning("⚠️ Pozisyon büyüklüğü minimum limitin altında")
                return False
            if position["size"] > self.config["risk_management"]["position_sizing"]["max_position"]:
                position["size"] = self.config["risk_management"]["position_sizing"]["max_position"]
                logging.info("ℹ️ Pozisyon büyüklüğü maksimum limite göre ayarlandı")
            tp_levels = []
            for tp_key, tp_value in self.config["take_profit"].items():
                tp_price = opportunity["entry"] + ((opportunity["entry"] - opportunity["stop"]) * tp_value["ratio"] if opportunity["direction"] == "LONG" else -(opportunity["entry"] - opportunity["stop"]) * tp_value["ratio"])
                tp_size = position["size"] * tp_value["size"]
                tp_levels.append({"price": tp_price, "size": tp_size})
            trade_id = self.trade_manager.open_trade(
                symbol=self.config["symbols"][0],
                direction=opportunity["direction"],
                entry=opportunity["entry"],
                stop=opportunity["stop"],
                take_profits=tp_levels,
                size=position["size"],
                model=opportunity["model"],
                context=opportunity["context"],
                supporting_tools=opportunity.get("supporting_tools", [])
            )
            if trade_id:
                logging.info(f"✅ Trade açıldı: {trade_id}")
                if self.config["telegram"]["enabled"] and self.config["telegram"]["notifications"]["trade_open"]:
                    message = (
                        f"🔔 Yeni Trade Açıldı\n"
                        f"Symbol: {self.config['symbols'][0]}\n"
                        f"Model: {opportunity['model']}\n"
                        f"Yön: {opportunity['direction']}\n"
                        f"Giriş: {opportunity['entry']:.8f}\n"
                        f"Stop: {opportunity['stop']:.8f}\n"
                        f"Risk: {position['risk_amount']:.2f} USDT\n"
                        f"Kalite: {opportunity['setup_quality']}\n\n"
                    )
                    self._send_telegram_notification(message)
                return True
            return False
        except Exception as e:
            logging.error(f"❌ Trade uygulama hatası: {e}")
            return False
            
    def _send_telegram_notification(self, message: str):
        try:
            if not self.config["telegram"]["enabled"]:
                return
            import requests
            url = f"https://api.telegram.org/bot{self.config['telegram']['bot_token']}/sendMessage"
            data = {"chat_id": self.config["telegram"]["chat_id"], "text": message, "parse_mode": "HTML"}
            response = requests.post(url, json=data)
            if not response.ok:
                logging.error(f"❌ Telegram bildirimi gönderilemedi: {response.text}")
        except Exception as e:
            logging.error(f"❌ Telegram bildirimi hatası: {e}")
            
    def run(self):
        while True:
            try:
                # Tüm sembolleri analiz et
                for symbol in self.config["symbols"]:
                    analysis = self.analyze_market(symbol)
                    if not analysis:
                        logging.error(f"❌ {symbol} için analiz başarısız")
                        continue
                        
                    # Haftalık seviyeleri sessizce güncelle
                    try:
                        if self.data.get("weekly") is not None:
                            self.data["weekly"].attrs["symbol"] = symbol
                            from utils.weekly_levels_storage import update_weekly_levels
                            update_weekly_levels(self.data["weekly"], symbol)
                    except Exception:
                        pass

                    # Fırsatları kontrol et
                    opportunities = self.find_entry_opportunities(analysis)
                    if opportunities:
                        logging.info(f"🎯 {len(opportunities)} adet fırsat bulundu")
                        for opportunity in opportunities:
                            if self.execute_trade(opportunity):
                                logging.info(f"💫 {symbol} için {opportunity['model']} trade açıldı")
                    else:
                        logging.info(f"❗ {symbol} için uygun fırsat bulunamadı")
                
                # Tüm semboller tarandıktan sonra bekle
                time.sleep(self.config["scan_settings"]["interval"])
                    
            except Exception as e:
                logging.error(f"❌ Trading döngüsü hatası: {e}")
                time.sleep(self.config["scan_settings"]["retry_delay"])
                
    def generate_daily_report(self):
        try:
            report = "🤖 ICT Trading Bot - Günlük Rapor\n\n"
            account_balance = self.trade_manager.get_account_balance()
            daily_risk = self.trade_manager.get_daily_risk()
            open_trades = len(self.trade_manager.get_active_trades())
            report += "💰 Hesap Durumu:\n"
            report += f"  • Bakiye: {account_balance:.2f} USDT\n"
            report += f"  • Günlük Risk: %{daily_risk:.1f}\n"
            report += f"  • Açık Trade: {open_trades}\n\n"
            report += self.trade_manager.generate_performance_report()
            if self.config["telegram"]["enabled"] and self.config["telegram"]["notifications"]["daily_summary"]:
                self._send_telegram_notification(report)
            return report
        except Exception as e:
            logging.error(f"❌ Günlük rapor oluşturma hatası: {e}")
            return "Rapor oluşturulamadı"

def main():
    try:
        trader = ICTTrader()
        trader.run()
    except Exception as e:
        logging.error(f"❌ Main hatası: {e}")

if __name__ == "__main__":
    main()