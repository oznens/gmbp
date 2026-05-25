from typing import Dict, Optional
import pandas as pd

def calculate_position_size(account_size: float, risk_percentage: float, entry_price: float, stop_loss: float) -> Dict:
    """Pozisyon büyüklüğünü hesaplar."""
    try:
        risk_amount = account_size * (risk_percentage / 100)
        stop_distance = abs(entry_price - stop_loss)
        position_size = risk_amount / stop_distance
        return {
            "size": float(position_size),
            "risk_amount": float(risk_amount),
            "stop_distance": float(stop_distance)
        }
    except Exception as e:
        print(f"❌ Pozisyon büyüklüğü hesaplama hatası: {e}")
        return {"size": 0.0, "risk_amount": 0.0, "stop_distance": 0.0}

def calculate_take_profit_levels(entry_price: float, stop_loss: float, direction: str) -> Dict:
    """Take profit seviyelerini hesaplar."""
    try:
        risk = abs(entry_price - stop_loss)
        tp1 = entry_price + risk * 1.5 if direction.upper() == "LONG" else entry_price - risk * 1.5
        tp2 = entry_price + risk * 2.5 if direction.upper() == "LONG" else entry_price - risk * 2.5
        tp3 = entry_price + risk * 4 if direction.upper() == "LONG" else entry_price - risk * 4
        return {"tp1": tp1, "tp2": tp2, "tp3": tp3}
    except Exception as e:
        print(f"❌ Take profit hesaplama hatası: {e}")
        return {}

def validate_risk_parameters(setup: Dict, account_size: float, max_risk_per_trade: float = 2.0) -> Dict:
    """Risk parametrelerini doğrula"""
    try:
        validation = {
            "is_valid": False,
            "reasons": [],
            "risk_score": 0  # 0-100 arası risk skoru
        }
        
        # 1. Stop Loss Mesafesi Kontrolü
        stop_distance = abs(setup["entry"] - setup["stop"]) / setup["entry"] * 100  # Yüzde olarak
        if stop_distance > 2.0:  # %2'den büyük
            validation["reasons"].append("Stop loss mesafesi çok büyük")
            validation["risk_score"] += 30
        elif stop_distance > 1.0:
            validation["reasons"].append("Stop loss mesafesi büyük")
            validation["risk_score"] += 15
            
        # 2. Risk Miktarı Kontrolü
        risk_amount = account_size * (max_risk_per_trade / 100)
        if risk_amount > account_size * 0.03:
            validation["reasons"].append("Risk miktarı çok yüksek")
            validation["risk_score"] += 30
            
        # 3. Setup Kalitesi Kontrolü
        if setup.get("setup_quality", "MEDIUM") == "LOW":
            validation["reasons"].append("Setup kalitesi düşük")
            validation["risk_score"] += 20
            
        # 4. Hacim Kontrolü
        if not setup.get("volume_confirm", True):
            validation["reasons"].append("Hacim teyidi yok")
            validation["risk_score"] += 15
            
        validation["is_valid"] = validation["risk_score"] < 50
        
        return validation
        
    except Exception as e:
        print(f"❌ Risk parametreleri doğrulama hatası: {e}")
        return {
            "is_valid": False,
            "reasons": [str(e)],
            "risk_score": 100
        }

def adjust_position_for_correlation(base_size: float, correlated_pairs: Dict[str, float]) -> float:
    """Korelasyon bazlı pozisyon büyüklüğü ayarlama"""
    try:
        correlation_factor = 1.0
        for pair, correlation in correlated_pairs.items():
            if abs(correlation) > 0.7:
                correlation_factor *= 0.7
        return base_size * correlation_factor
    except Exception as e:
        print(f"❌ Korelasyon ayarlama hatası: {e}")
        return base_size