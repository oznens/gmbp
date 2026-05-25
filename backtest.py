from typing import Dict, List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from tqdm import tqdm

from main import ICTTrader
from utils.data_fetcher import DataFetcher

class ICTBacktester(ICTTrader):
    def __init__(self, config_path: str = 'config/settings.py'):
        super().__init__(config_path)
        self.trades = []
        self.equity_curve = []
        self.initial_balance = 10000  # Başlangıç bakiyesi
        self.current_balance = self.initial_balance
        
        self.data = {
            "htf": None,  # High Time Frame (1w, 1d, 4h)
            "ltf": None,  # Low Time Frame (15m)
            "mtf": None,  # Micro Time Frame (5m)
            "inm": None,  # 1-minute data
            "weekly": None,
            "daily": None
        }
        
    def backtest(self, symbol: str, start_date: str, end_date: str):
        """Belirtilen tarih aralığında backtest yapar"""
        try:
            # Tarihleri datetime'a çevir
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            
            # Tüm timeframe'ler için veri çek
            logging.info(f"📊 {symbol} için backtest verisi çekiliyor...")
            
            # HTF verisi (4h)
            htf_data = self.data_fetcher.fetch_ohlcv(
                symbol=symbol,
                timeframe="4h",
                limit=1000
            )
            
            # LTF verisi (15m)
            ltf_data = self.data_fetcher.fetch_ohlcv(
                symbol=symbol,
                timeframe="15m",
                limit=1000
            )
            
            # MTF verisi (5m)
            mtf_data = self.data_fetcher.fetch_ohlcv(
                symbol=symbol,
                timeframe="5m",
                limit=1000
            )
            
            # 1m verisi (1m)
            inm_data = self.data_fetcher.fetch_ohlcv(
                symbol=symbol,
                timeframe="1m",
                limit=1000
            )
            
            if htf_data is None or ltf_data is None or mtf_data is None or inm_data is None:
                raise Exception("Veri çekilemedi")
                
            # Verileri tarihe göre filtrele
            htf_data = htf_data[start:end]
            ltf_data = ltf_data[start:end]
            mtf_data = mtf_data[start:end]
            inm_data = inm_data[start:end]
            
            # Her gün için backtest yap
            current_date = start
            pbar = tqdm(total=(end - start).days)
            
            while current_date <= end:
                next_date = current_date + timedelta(days=1)
                
                # O güne ait verileri al
                daily_htf = htf_data[current_date:next_date]
                daily_ltf = ltf_data[current_date:next_date]
                daily_mtf = mtf_data[current_date:next_date]
                daily_inm = inm_data[current_date:next_date]
                
                if len(daily_htf) == 0 or len(daily_ltf) == 0 or len(daily_mtf) == 0:
                    current_date = next_date
                    pbar.update(1)
                    continue
                
                # Verileri güncelle
                self.data = {
                    "htf": daily_htf,
                    "ltf": daily_ltf,
                    "mtf": daily_mtf,
                    "inm": daily_inm
                }
                
                # Market analizi yap
                analysis = self.analyze_market(symbol)
                
                # Fırsatları kontrol et
                opportunities = self.find_entry_opportunities(analysis)
                
                # Trade'leri simüle et
                for opportunity in opportunities:
                    trade = self.simulate_trade(opportunity)
                    if trade:
                        self.trades.append(trade)
                        # Bakiyeyi güncelle
                        pnl = trade["pnl"]
                        self.current_balance += pnl
                        self.equity_curve.append({
                            "timestamp": trade["exit_time"],
                            "balance": self.current_balance
                        })
                
                current_date = next_date
                pbar.update(1)
            
            pbar.close()
            
            # Sonuçları raporla
            self.generate_backtest_report()
            
        except Exception as e:
            logging.error(f"❌ Backtest hatası: {e}")
            
    def simulate_trade(self, opportunity: Dict) -> Dict:
        """Trade simülasyonu"""
        try:
            entry_price = float(opportunity["entry"])
            stop_loss = float(opportunity["stop"])
            direction = opportunity["direction"]
            
            # Position size hesapla
            risk_amount = self.current_balance * 0.01  # %1 risk
            position_size = risk_amount / abs(entry_price - stop_loss)
            
            # İlgili timeframe verisinde trade'i simüle et
            data = self.data["inm"] if self.data.get("inm") is not None and not self.data["inm"].empty else self.data["ltf"]
            if direction == "LONG":
                # Long pozisyon için
                for idx, row in data.iterrows():
                    # Stop loss kontrolü
                    if float(row["low"]) <= stop_loss:
                        return {
                            "entry_time": opportunity["timestamp"],
                            "exit_time": idx,
                            "entry_price": entry_price,
                            "exit_price": stop_loss,
                            "direction": direction,
                            "size": position_size,
                            "pnl": position_size * (stop_loss - entry_price),
                            "model": opportunity["model"],
                            "reason": "stop_loss"
                        }
                    # Take profit kontrolü (örn: 1:2 RR)
                    target = entry_price + 2 * abs(entry_price - stop_loss)
                    if float(row["high"]) >= target:
                        return {
                            "entry_time": opportunity["timestamp"],
                            "exit_time": idx,
                            "entry_price": entry_price,
                            "exit_price": target,
                            "direction": direction,
                            "size": position_size,
                            "pnl": position_size * (target - entry_price),
                            "model": opportunity["model"],
                            "reason": "take_profit"
                        }
            else:
                # Short pozisyon için
                for idx, row in data.iterrows():
                    # Stop loss kontrolü
                    if float(row["high"]) >= stop_loss:
                        return {
                            "entry_time": opportunity["timestamp"],
                            "exit_time": idx,
                            "entry_price": entry_price,
                            "exit_price": stop_loss,
                            "direction": direction,
                            "size": position_size,
                            "pnl": position_size * (entry_price - stop_loss),
                            "model": opportunity["model"],
                            "reason": "stop_loss"
                        }
                    # Take profit kontrolü (örn: 1:2 RR)
                    target = entry_price - 2 * abs(entry_price - stop_loss)
                    if float(row["low"]) <= target:
                        return {
                            "entry_time": opportunity["timestamp"],
                            "exit_time": idx,
                            "entry_price": entry_price,
                            "exit_price": target,
                            "direction": direction,
                            "size": position_size,
                            "pnl": position_size * (entry_price - target),
                            "model": opportunity["model"],
                            "reason": "take_profit"
                        }
            
            return None
            
        except Exception as e:
            logging.error(f"❌ Trade simülasyon hatası: {e}")
            return None
            
    def generate_backtest_report(self):
        """Backtest sonuçlarını raporla"""
        try:
            total_trades = len(self.trades)
            if total_trades == 0:
                logging.info("❌ Backtest süresince hiç trade bulunamadı")
                return
                
            winning_trades = len([t for t in self.trades if t["pnl"] > 0])
            losing_trades = len([t for t in self.trades if t["pnl"] < 0])
            
            win_rate = (winning_trades / total_trades) * 100
            
            total_profit = sum([t["pnl"] for t in self.trades if t["pnl"] > 0])
            total_loss = sum([t["pnl"] for t in self.trades if t["pnl"] < 0])
            
            profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float('inf')
            
            max_drawdown = self.calculate_max_drawdown()
            
            # Modellere göre performans
            model_performance = {}
            for trade in self.trades:
                model = trade["model"]
                if model not in model_performance:
                    model_performance[model] = {
                        "total": 0,
                        "wins": 0,
                        "losses": 0,
                        "pnl": 0
                    }
                model_performance[model]["total"] += 1
                if trade["pnl"] > 0:
                    model_performance[model]["wins"] += 1
                else:
                    model_performance[model]["losses"] += 1
                model_performance[model]["pnl"] += trade["pnl"]
            
            # Raporu yazdır
            logging.info("\n📊 Backtest Sonuçları:")
            logging.info(f"💰 Başlangıç Bakiye: {self.initial_balance:.2f} USDT")
            logging.info(f"💰 Bitiş Bakiye: {self.current_balance:.2f} USDT")
            logging.info(f"📈 Toplam Kâr/Zarar: {(self.current_balance - self.initial_balance):.2f} USDT")
            logging.info(f"🎯 Toplam Trade: {total_trades}")
            logging.info(f"✅ Kazanan Trade: {winning_trades}")
            logging.info(f"❌ Kaybeden Trade: {losing_trades}")
            logging.info(f"📊 Kazanma Oranı: {win_rate:.2f}%")
            logging.info(f"📈 Profit Faktör: {profit_factor:.2f}")
            logging.info(f"📉 Maksimum Drawdown: {max_drawdown:.2f}%")
            
            logging.info("\n📊 Model Performansları:")
            for model, stats in model_performance.items():
                win_rate = (stats["wins"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                logging.info(f"\n{self.model_emojis.get(model, '❓')} {model.upper()}:")
                logging.info(f"  • Toplam Trade: {stats['total']}")
                logging.info(f"  • Kazanan: {stats['wins']}")
                logging.info(f"  • Kaybeden: {stats['losses']}")
                logging.info(f"  • Kazanma Oranı: {win_rate:.2f}%")
                logging.info(f"  • Toplam PNL: {stats['pnl']:.2f} USDT")
            
        except Exception as e:
            logging.error(f"❌ Rapor oluşturma hatası: {e}")
            
    def calculate_max_drawdown(self) -> float:
        """Maksimum drawdown hesapla"""
        try:
            if not self.equity_curve:
                return 0.0
                
            balances = [point["balance"] for point in self.equity_curve]
            peak = balances[0]
            max_dd = 0
            
            for balance in balances:
                if balance > peak:
                    peak = balance
                dd = (peak - balance) / peak * 100
                if dd > max_dd:
                    max_dd = dd
                    
            return max_dd
            
        except Exception as e:
            logging.error(f"❌ Drawdown hesaplama hatası: {e}")
            return 0.0

def main():
    try:
        # Backtest parametreleri
        symbol = "BTCUSDT"
        start_date = "2024-11-01"
        end_date = "2025-02-11"
        
        # Backtester'ı başlat
        backtester = ICTBacktester()
        
        # Backtest yap
        backtester.backtest(symbol, start_date, end_date)
        
    except Exception as e:
        logging.error(f"❌ Backtest hatası: {e}")

if __name__ == "__main__":
    main() 