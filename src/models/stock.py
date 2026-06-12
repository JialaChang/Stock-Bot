from dataclasses import dataclass
from datetime import datetime

@dataclass
class StockSnapshot:
    """
    股票快照資料載體 (Data Transfer Object)\n
    提供型別安全 (Type-Safety) 的方式在系統各模組之間傳遞分析結果
    """
    ticker: str
    name: str
    current_price: float
    change_percent: float
    rsi_value: float
    latest_time: datetime

    @property
    def change_str(self) -> str:
        """漲跌幅格式化：根據正負值補上漲跌符號"""
        icon = '∆' if self.change_percent >= 0 else '∇'
        return f"{icon} {abs(self.change_percent):.2f}%"
    
    @property
    def latest_time_str(self) -> str:
        """時間格式化輸出"""
        if hasattr(self.latest_time, 'strftime'):
            return self.latest_time.strftime('%m-%d %H:%M')
        return str(self.latest_time)