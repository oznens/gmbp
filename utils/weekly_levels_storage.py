import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from models.ict_tools import smc

# Depolama dosyası yolunu belirleyin
STORAGE_FILE = os.path.join(os.path.dirname(__file__), "weekly_levels.json")

def initialize_storage():
    """Storage dosyasını doğru format ile başlat"""
    if not os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "w") as f:
            json.dump({}, f)

def load_weekly_levels(symbol: str = None) -> Dict:
    """Kaydedilmiş haftalık seviyeleri yükler"""
    try:
        initialize_storage()
        with open(STORAGE_FILE, "r") as f:
            try:
                data = json.load(f)
                # Eğer data liste ise, boş dict ile başlat
                if isinstance(data, list):
                    data = {}
            except json.JSONDecodeError:
                data = {}
            
        # Eğer sembol belirtilmişse sadece o sembolün verilerini döndür
        if symbol:
            return data.get(symbol, {"levels": []})
        return data
    except Exception as e:
        logging.error(f"❌ Haftalık seviyeler yüklenirken hata: {e}")
        return {}

def save_weekly_levels(levels: Dict):
    """Haftalık seviyeleri JSON dosyasına kaydeder"""
    try:
        initialize_storage()
        # Mevcut verileri yükle
        existing_data = load_weekly_levels()
        
        # Yeni verileri ekle/güncelle (sembol bazlı)
        for symbol, data in levels.items():
            if isinstance(data, dict) and "levels" in data:
                existing_data[symbol] = {
                    "levels": data["levels"],
                    "last_update": datetime.now().isoformat()
                }
            else:
                logging.error(f"❌ {symbol} için geçersiz veri formatı")
                continue
        
        # Dosyaya kaydet
        with open(STORAGE_FILE, "w") as f:
            json.dump(existing_data, f, indent=4)
            
        logging.debug(f"💾 Haftalık seviyeler kaydedildi: {len(existing_data)} sembol")
    except Exception as e:
        logging.error(f"❌ Haftalık seviyeler kaydedilirken hata: {e}")

def update_weekly_levels(data: pd.DataFrame, symbol: str):
    try:
        # Haftalık seviyeleri güncelle
        weekly_levels = calculate_weekly_levels(data)
        
        # Dosyaya kaydet
        save_weekly_levels(weekly_levels, symbol)
        
    except Exception:
        pass 