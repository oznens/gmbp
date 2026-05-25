from typing import Dict, List, Optional
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import time

class TradeManager:
    def __init__(self, trade_history_file: str = 'trade_history.json'):
        """Trade yöneticisini başlatır."""
        self.trade_history_file = Path(trade_history_file)
        self.trade_history = self._load_trade_history()
        self.account_balance = 2588.0  # Başlangıç bakiyesi (USDT)
        self.model_stats = ModelStats()  # Model istatistikleri
        
    def _load_trade_history(self) -> List[Dict]:
        """Trade geçmişini yükler."""
        try:
            if self.trade_history_file.exists():
                with open(self.trade_history_file, "r") as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"❌ Trade geçmişi yükleme hatası: {e}")
            return []
            
    def _save_trade_history(self):
        """Trade geçmişini kaydeder."""
        try:
            with open(self.trade_history_file, "w") as f:
                json.dump(self.trade_history, f, indent=2)
        except Exception as e:
            print(f"❌ Trade geçmişi kaydetme hatası: {e}")
            
    def add_trade(self, trade_data: Dict):
        """Yeni trade ekler ve geçmişi günceller."""
        self.trade_history.append(trade_data)
        self._save_trade_history()
            
    def get_last_trade(self) -> Optional[Dict]:
        """Son trade'i getir"""
        try:
            return self.trade_history[-1] if self.trade_history else None
        except Exception as e:
            print(f"❌ Son trade getirme hatası: {e}")
            return None
            
    def get_trades_by_model(self, model_type: str) -> List[Dict]:
        """Model tipine göre trade'leri getir"""
        try:
            return [trade for trade in self.trade_history if trade.get("model_type") == model_type]
        except Exception as e:
            print(f"❌ Model bazlı trade getirme hatası: {e}")
            return []
            
    def calculate_model_performance(self, model_type: str) -> Dict:
        """Model performansını hesapla"""
        try:
            model_trades = self.get_trades_by_model(model_type)
            if not model_trades:
                return {
                    "win_rate": 0.0,
                    "avg_risk_reward": 0.0,
                    "total_trades": 0
                }
            winning_trades = [t for t in model_trades if t.get("result", "LOSS") == "WIN"]
            performance = {
                "win_rate": len(winning_trades) / len(model_trades) * 100,
                "avg_risk_reward": sum(t.get("risk_reward", 0) for t in model_trades) / len(model_trades),
                "total_trades": len(model_trades)
            }
            return performance
        except Exception as e:
            print(f"❌ Model performans hesaplama hatası: {e}")
            return {"win_rate": 0.0, "avg_risk_reward": 0.0, "total_trades": 0}
            
    def get_active_trades(self) -> List[Dict]:
        """Aktif trade'leri getir"""
        try:
            return [trade for trade in self.trade_history if trade.get("status") == "ACTIVE"]
        except Exception as e:
            print(f"❌ Aktif trade getirme hatası: {e}")
            return []
            
    def update_trade_status(self, trade_id: str, new_status: str, result: Optional[str] = None, profit: float = 0.0, drawdown: float = 0.0):
        """Trade durumunu güncelle"""
        try:
            for trade in self.trade_history:
                if trade.get("id") == trade_id:
                    trade["status"] = new_status
                    if result:
                        trade["result"] = result
                        trade["profit"] = profit
                        trade["drawdown"] = drawdown
                        self.model_stats.update_model_stats(trade.get("model"), {"result": result, "profit": profit, "drawdown": drawdown})
                    trade["updated_at"] = datetime.now().isoformat()
                    break
            self._save_trade_history()
        except Exception as e:
            print(f"❌ Trade durumu güncelleme hatası: {e}")
            
    def analyze_trade_history(self) -> Dict:
        """Trade geçmişini analiz et"""
        try:
            if not self.trade_history:
                return {"total_trades": 0, "win_rate": 0.0, "best_model": None, "avg_risk_reward": 0.0}
            analysis = {
                "total_trades": len(self.trade_history),
                "winning_trades": len([t for t in self.trade_history if t.get("result") == "WIN"]),
                "losing_trades": len([t for t in self.trade_history if t.get("result") == "LOSS"]),
                "model_performance": {}
            }
            model_types = set(t.get("model_type") for t in self.trade_history if t.get("model_type"))
            for model in model_types:
                analysis["model_performance"][model] = self.calculate_model_performance(model)
            analysis["win_rate"] = (analysis["winning_trades"] / analysis["total_trades"]) * 100
            analysis["avg_risk_reward"] = sum(t.get("risk_reward", 0) for t in self.trade_history) / analysis["total_trades"]
            if analysis["model_performance"]:
                analysis["best_model"] = max(analysis["model_performance"].items(), key=lambda x: x[1]["win_rate"])[0]
            return analysis
        except Exception as e:
            print(f"❌ Trade geçmişi analiz hatası: {e}")
            return {"total_trades": 0, "win_rate": 0.0, "best_model": None, "avg_risk_reward": 0.0}
            
    def get_account_balance(self) -> float:
        """Hesap bakiyesini getir"""
        try:
            active_trades_value = sum(float(trade.get("size", 0)) * float(trade.get("entry", 0)) for trade in self.get_active_trades())
            available_balance = self.account_balance - active_trades_value
            return max(available_balance, 0.0)
        except Exception as e:
            print(f"❌ Bakiye getirme hatası: {e}")
            return 0.0
            
    def update_account_balance(self, new_balance: float):
        """Hesap bakiyesini güncelle"""
        try:
            self.account_balance = max(new_balance, 0.0)
        except Exception as e:
            print(f"❌ Bakiye güncelleme hatası: {e}") 
            
    def get_daily_risk(self) -> float:
        """Günlük riski hesapla"""
        try:
            today = datetime.now().date()
            todays_trades = [trade for trade in self.trade_history if isinstance(trade.get("timestamp"), str) and datetime.fromisoformat(trade["timestamp"].split(".")[0]).date() == today]
            active_trades = [trade for trade in todays_trades if trade.get("status") == "ACTIVE"]
            total_risk = sum(float(trade.get("risk_amount", 0)) / self.account_balance * 100 for trade in active_trades)
            return round(total_risk, 2)
        except Exception as e:
            print(f"❌ Günlük risk hesaplama hatası: {e}")
            return 0.0
            
    def open_trade(self, symbol: str, direction: str, entry: float, stop: float, 
                   take_profits: List[Dict], size: float, model: str, 
                   context: Dict, supporting_tools: List[Dict]) -> str:
        """Yeni trade aç"""
        try:
            trade_id = f"{symbol}_{int(time.time())}"
            risk_amount = abs(entry - stop) * size
            trade_data = {
                "id": trade_id,
                "symbol": symbol,
                "direction": direction,
                "entry": entry,
                "stop": stop,
                "take_profits": take_profits,
                "size": size,
                "model": model,
                "context": context,
                "supporting_tools": supporting_tools,
                "status": "ACTIVE",
                "risk_amount": risk_amount,
                "timestamp": datetime.now().isoformat()
            }
            self.add_trade(trade_data)
            return trade_id
        except Exception as e:
            print(f"❌ Trade açma hatası: {e}")
            return None

    def get_model_performance(self, model_type: str = None) -> Dict:
        """Model performansını getir"""
        try:
            if model_type:
                return self.model_stats.get_model_stats(model_type)
            else:
                return self.model_stats.get_all_stats()
        except Exception as e:
            print(f"❌ Model performansı getirme hatası: {e}")
            return {}
            
    def get_best_performing_models(self, metric: str = "win_rate", top_n: int = 3) -> List[Dict]:
        """En iyi performans gösteren modelleri getir"""
        try:
            return self.model_stats.get_best_models(metric, top_n)
        except Exception as e:
            print(f"❌ En iyi model getirme hatası: {e}")
            return []
            
    def generate_performance_report(self) -> str:
        """Performans raporu oluştur"""
        try:
            return self.model_stats.generate_report()
        except Exception as e:
            print(f"❌ Performans raporu oluşturma hatası: {e}")
            return "Rapor oluşturulamadı"

    def generate_report(self) -> str:
        """Detaylı trade raporu oluşturur."""
        try:
            report = "📊 Trade Raporu\n"
            report += f"Toplam Trade: {len(self.trade_history)}\n"
            return report
        except Exception as e:
            print(f"❌ Rapor oluşturma hatası: {e}")
            return "Rapor oluşturulamadı"

class ModelStats:
    def __init__(self):
        self.stats = {
            "PO3": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "BOS_FVG": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "CHOCH_OB": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "OTE": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "SILVER_BULLET_2022": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "LONDON_REVERSAL": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "JUDAS_SWING": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "TURTLE_SOUP": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "NY_REVERSAL": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "SBS": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "IMBALANCE_PLAY": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "SMT_DIVERGENCE": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0},
            "BPR": {"wins": 0, "losses": 0, "total_profit": 0.0, "max_drawdown": 0.0, "best_streak": 0, "worst_streak": 0}
        }
        
    def update_model_stats(self, model_type: str, trade_result: Dict):
        try:
            if model_type not in self.stats:
                return
            model_stats = self.stats[model_type]
            if trade_result["result"] == "WIN":
                model_stats["wins"] += 1
                model_stats["best_streak"] += 1
                model_stats["worst_streak"] = 0
            else:
                model_stats["losses"] += 1
                model_stats["worst_streak"] += 1
                model_stats["best_streak"] = 0
            model_stats["total_profit"] += trade_result.get("profit", 0.0)
            current_drawdown = trade_result.get("drawdown", 0.0)
            if current_drawdown > model_stats["max_drawdown"]:
                model_stats["max_drawdown"] = current_drawdown
        except Exception as e:
            print(f"❌ Model istatistikleri güncelleme hatası: {e}")
            
    def get_model_stats(self, model_type: str) -> Dict:
        try:
            if model_type not in self.stats:
                return {}
            stats = self.stats[model_type]
            total_trades = stats["wins"] + stats["losses"]
            return {
                "model": model_type,
                "total_trades": total_trades,
                "win_rate": (stats["wins"] / total_trades * 100) if total_trades > 0 else 0.0,
                "total_profit": stats["total_profit"],
                "max_drawdown": stats["max_drawdown"],
                "best_streak": stats["best_streak"],
                "worst_streak": stats["worst_streak"],
                "profit_factor": abs(stats["total_profit"] / stats["max_drawdown"]) if stats["max_drawdown"] > 0 else 0.0
            }
        except Exception as e:
            print(f"❌ Model istatistikleri getirme hatası: {e}")
            return {}
            
    def get_all_stats(self) -> Dict:
        try:
            all_stats = {}
            for model_type in self.stats:
                all_stats[model_type] = self.get_model_stats(model_type)
            return all_stats
        except Exception as e:
            print(f"❌ Tüm istatistikleri getirme hatası: {e}")
            return {}
            
    def get_best_models(self, metric: str = "win_rate", top_n: int = 3) -> List[Dict]:
        try:
            all_stats = self.get_all_stats()
            sorted_models = sorted(all_stats.values(), key=lambda x: x.get(metric, 0), reverse=True)
            return sorted_models[:top_n]
        except Exception as e:
            print(f"❌ En iyi modelleri getirme hatası: {e}")
            return []
            
    def generate_report(self) -> str:
        try:
            all_stats = self.get_all_stats()
            report = "📊 Model İstatistikleri Raporu\n\n"
            best_models = self.get_best_models(metric="win_rate", top_n=3)
            report += "🏆 En İyi Modeller (Win Rate):\n"
            for i, model in enumerate(best_models, 1):
                report += f"{i}. {model['model']}: %{model['win_rate']:.1f} ({model['total_trades']} trade)\n"
            report += "\n📈 Tüm Modeller:\n"
            for model_type, stats in all_stats.items():
                if stats["total_trades"] > 0:
                    report += f"\n{model_type}:\n"
                    report += f"  • Trade Sayısı: {stats['total_trades']}\n"
                    report += f"  • Win Rate: %{stats['win_rate']:.1f}\n"
                    report += f"  • Toplam Kâr: {stats['total_profit']:.2f} USDT\n"
                    report += f"  • Max Drawdown: {stats['max_drawdown']:.2f} USDT\n"
                    report += f"  • En İyi Seri: {stats['best_streak']}\n"
                    report += f"  • En Kötü Seri: {stats['worst_streak']}\n"
                    report += f"  • Profit Faktör: {stats['profit_factor']:.2f}\n"
            return report
        except Exception as e:
            print(f"❌ Rapor oluşturma hatası: {e}")
            return "Rapor oluşturulamadı"