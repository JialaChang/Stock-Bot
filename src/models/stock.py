from dataclasses import dataclass
from datetime import datetime

@dataclass
class StockSnapshot:
    """儲存股票分析結果的資料載體"""
    ticker: str  # 股票代號
    name: str    # 股票名稱   
    current_price: float
    change_percent: float
    rsi_value: float
    latest_time: datetime

    @property
    def change_str(self) -> str:
        """漲跌幅的格式化字串"""
        icon = '∆' if self.change_percent >= 0 else '∇'
        return f"{icon} {abs(self.change_percent):.2f}%"
    
    @property
    def latest_time_str(self) -> str:
        """資料時間的格式化字串"""
        if hasattr(self.latest_time, 'strftime'):
            return self.latest_time.strftime('%m-%d %H:%M')
        return str(self.latest_time)