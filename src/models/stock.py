from dataclasses import dataclass
from datetime import datetime

@dataclass
class StockSnapshot:
    """跨模組傳遞股票分析結果的資料載體 (Data Transfer Object) """
    ticker: str
    name: str
    current_price: float
    change_percent: float
    rsi_value: float
    latest_time: datetime

    @property
    def change_str(self) -> str:
        """格式化漲跌幅，附帶漲跌符號 (∆ / ∇)"""
        icon = '∆' if self.change_percent >= 0 else '∇'
        return f"{icon} {abs(self.change_percent):.2f}%"

    @property
    def latest_time_str(self) -> str:
        """格式化資料時間戳"""
        if hasattr(self.latest_time, 'strftime'):
            return self.latest_time.strftime('%m-%d %H:%M')
        return str(self.latest_time)