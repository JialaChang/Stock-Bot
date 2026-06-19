from dataclasses import dataclass
from datetime import date
import pandas as pd

@dataclass
class Trade:
    """紀錄執行單次交易的資料"""
    ticker: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    shares: int = 1  # 買賣股數

    @property
    def profit_and_loss(self) -> float:
        return (self.exit_price - self.entry_price) * self.shares

    @property
    def return_on_investment(self) -> float:
        return (self.exit_price - self.entry_price) / self.entry_price * 100
    
    @property
    def is_profit(self) -> bool:
        return self.profit_and_loss > 0
    
@dataclass
class BacktestResult:
    """一次完整回測的彙總結果"""
    ticker: str
    trades: list[Trade]
    equity_curve: pd.Series  # index=date, value=netWorth

    @property
    def total_return(self) -> float:
        first = self.equity_curve.iloc[0]
        last = self.equity_curve.iloc[-1]
        return (last - first) / first * 100
    
    @property
    def win_rate(self) -> float:
        if not self.trades: return 0.0
        return sum(t.is_profit for t in self.trades) / len(self.trades) * 100
    
    @property
    def max_drawdown(self) -> float:
        peak = self.equity_curve.cummax()
        drawdown = (self.equity_curve - peak) / peak * 100
        return drawdown.min()
    
    @property
    def trade_count(self) -> int:
        return len(self.trades)