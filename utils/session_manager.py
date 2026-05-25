from typing import Dict, Optional
import pandas as pd
from datetime import datetime, time
import pytz
import logging

class SessionManager:
    def __init__(self):
        """Seans yöneticisini başlat"""
        # UTC-4 (New York EDT - Yaz saati) zaman dilimi
        self.ny_tz = pytz.timezone('America/New_York')
        
        # Session saatleri (New York saatine göre)
        self.sessions = {
            "asia": {"start": time(18, 0), "end": time(4, 0), "name": "Asia"},    # NY 18:00 - 04:00 (Sydney+Tokyo)
            "london": {"start": time(3, 0), "end": time(12, 0), "name": "London"},  # NY 03:00 - 12:00
            "new_york": {"start": time(8, 0), "end": time(17, 0), "name": "New York"} # NY 08:00 - 17:00
        }
        
        # Killzone saatleri (New York saatine göre)
        self.killzones = {
            "london_open": {"start": time(3, 0), "end": time(5, 0), "name": "London Open"},          # NY 03:00 - 05:00
            "london_ny_overlap": {"start": time(8, 0), "end": time(12, 0), "name": "London-NY Overlap"}, # NY 08:00 - 12:00
            "ny_open": {"start": time(8, 0), "end": time(10, 0), "name": "NY Open"},                # NY 08:00 - 10:00
            "ny_close": {"start": time(15, 0), "end": time(17, 0), "name": "NY Close"}              # NY 15:00 - 17:00
        }
        
    def get_ny_time(self) -> str:
        """New York saatini döndürür"""
        try:
            utc_now = datetime.now(pytz.UTC)
            ny_time = utc_now.astimezone(self.ny_tz)
            return ny_time.strftime("%H:%M:%S")
        except Exception as e:
            print(f"❌ NY saati alma hatası: {e}")
            return "00:00:00"
            
    def get_current_session(self) -> Optional[str]:
        """Şu anki aktif seansı döndürür"""
        try:
            current_time = datetime.now(pytz.UTC).time()
            active_sessions = []
            
            for name, session in self.sessions.items():
                start, end = session["start"], session["end"]
                if start < end:
                    if start <= current_time < end:
                        active_sessions.append(session["name"])
                else:
                    if current_time >= start or current_time < end:
                        active_sessions.append(session["name"])
                        
            return ", ".join(active_sessions) if active_sessions else "No Active Session"
        except Exception as e:
            print(f"❌ Seans tespiti hatası: {e}")
            return None
            
    def get_current_killzone(self) -> Optional[str]:
        """Şu anki killzone'u döndürür"""
        try:
            current_time = datetime.now(pytz.UTC).time()
            active_killzones = []
            
            for name, kz in self.killzones.items():
                start, end = kz["start"], kz["end"]
                if start <= current_time < end:
                    active_killzones.append(kz["name"])
                    
            return ", ".join(active_killzones) if active_killzones else "No Active Killzone"
        except Exception as e:
            print(f"❌ Killzone tespiti hatası: {e}")
            return None
            
    def get_session_info(self) -> str:
        """Tüm session bilgilerini döndürür"""
        try:
            ny_time = self.get_ny_time()
            current_session = self.get_current_session()
            current_killzone = self.get_current_killzone()
            
            info = f"🕒 NY Time: {ny_time}\n"
            info += f"📈 Active Sessions: {current_session}\n"
            info += f"⚔️ Active Killzone: {current_killzone}"
            
            return info
        except Exception as e:
            print(f"❌ Session bilgisi alma hatası: {e}")
            return "Session bilgisi alınamadı"
            
    def is_session_active(self, session_name: str) -> bool:
        """Belirtilen seansın aktif olup olmadığını kontrol et"""
        try:
            if session_name not in self.sessions:
                return False
                
            utc_now = datetime.now(pytz.UTC)
            ny_now = utc_now.astimezone(self.ny_tz)
            current_time = ny_now.time()
            
            session = self.sessions[session_name]
            if session["start"] < session["end"]:
                return session["start"] <= current_time < session["end"]
            else:
                return current_time >= session["start"] or current_time < session["end"]
        except Exception as e:
            print(f"❌ Seans aktivite kontrolü hatası: {e}")
            return False
            
    def get_session_data(self, data: pd.DataFrame, session_name: str) -> pd.DataFrame:
        """Belirtilen seans için veri filtreleme"""
        try:
            if session_name not in self.sessions:
                return pd.DataFrame()
            session = self.sessions[session_name]
            if not isinstance(data.index, pd.DatetimeIndex):
                data = data.set_index(pd.to_datetime(data.index))
            data.index = data.index.tz_localize(pytz.UTC)
            if session["start"] < session["end"]:
                return data[(data.index.time >= session["start"]) & (data.index.time < session["end"])]
            else:
                return data[(data.index.time >= session["start"]) | (data.index.time < session["end"])]
        except Exception as e:
            print(f"❌ Seans verisi filtreleme hatası: {e}")
            return pd.DataFrame()
            
    def get_session_overlap(self, session1: str, session2: str) -> Optional[Dict]:
        """İki seans arasındaki çakışma saatlerini bul"""
        try:
            if session1 not in self.sessions or session2 not in self.sessions:
                return None
            s1 = self.sessions[session1]
            s2 = self.sessions[session2]
            start = max(s1["start"], s2["start"])
            end = min(s1["end"], s2["end"])
            if start < end:
                return {
                    "start": start,
                    "end": end,
                    "duration_hours": (datetime.combine(datetime.today(), end) - datetime.combine(datetime.today(), start)).total_seconds() / 3600
                }
            return None
        except Exception as e:
            print(f"❌ Seans çakışması hesaplama hatası: {e}")
            return None
            
    def is_high_volatility_period(self) -> bool:
        """London ve New York seans çakışması gibi durumları kontrol eder."""
        try:
            current_time = datetime.now(pytz.UTC).time()
            for kz in self.killzones.values():
                if kz["start"] <= current_time < kz["end"]:
                    return True
            return False
        except Exception as e:
            print(f"❌ Volatilite kontrolü hatası: {e}")
            return False
            
    def get_session_times(self, session_name: str) -> Optional[Dict]:
        """Belirtilen seansın başlangıç ve bitiş saatlerini döndürür (New York saatine göre)"""
        try:
            if session_name not in self.sessions:
                return None
                
            session = self.sessions[session_name]
            utc_now = datetime.now(pytz.UTC)
            ny_now = utc_now.astimezone(self.ny_tz)
            
            # NY saatine göre başlangıç ve bitiş zamanlarını ayarla
            start_time = datetime.combine(ny_now.date(), session["start"])
            end_time = datetime.combine(ny_now.date(), session["end"])
            
            # NY zaman dilimini ekle
            start_time = self.ny_tz.localize(start_time)
            end_time = self.ny_tz.localize(end_time)
            
            # Eğer bitiş saati başlangıç saatinden küçükse, ertesi güne geçiyor demektir
            if session["start"] > session["end"]:
                end_time = end_time + pd.Timedelta(days=1)
                
            return {
                "start": start_time,
                "end": end_time
            }
        except Exception as e:
            print(f"❌ Seans saatleri alma hatası: {e}")
            return None

    def _analyze_sessions(self) -> Dict:
        """Session durumunu analiz et"""
        try:
            sessions = {
                "london": self.is_session_active("london"),
                "new_york": self.is_session_active("new_york"),
                "asia": self.is_session_active("asia")
            }
            
            # Session bilgilerini logla
            ny_time = self.get_ny_time()
            logging.info(f"\n🕒 Seans Durumu (New York Saati: {ny_time})")
            session_emojis = {
                "london": "🇬🇧",
                "new_york": "🇺🇸",
                "asia": "🌏"
            }
            
            # Önce aktif killzone'ları göster
            current_killzone = self.get_current_killzone()
            if current_killzone and current_killzone != "No Active Killzone":
                logging.info(f"⚔️ Aktif Killzone: {current_killzone}")
            
            # Sonra session durumlarını göster
            for session_name, is_active in sessions.items():
                emoji = session_emojis.get(session_name, "🌍")
                status = "🟢 Aktif" if is_active else "🔴 Kapalı"
                session_times = self.get_session_times(session_name)
                if session_times:
                    start_time = session_times["start"].strftime("%H:%M")
                    end_time = session_times["end"].strftime("%H:%M")
                    logging.info(f"  {emoji} {session_name.upper()}: {status} ({start_time}-{end_time} NY)")
                else:
                    logging.info(f"  {emoji} {session_name.upper()}: {status}")
            
            return sessions
        except Exception as e:
            print(f"❌ Session analiz hatası: {e}")
            return {}