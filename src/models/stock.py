from dataclasses import dataclass
from datetime import datetime


def format_change(percent: float) -> str:
    """'∆ 1.40%' / '∇ 0.52%', as the Embed and the terminal show a price change."""
    icon = '∆' if percent >= 0 else '∇'
    return f"{icon} {abs(percent):.2f}%"


@dataclass
class StockSnapshot:
    """What the `/stock` Embed shows."""
    ticker: str
    name: str
    current_price: float
    previous_close: float
    rsi_value: float | None
    latest_time: datetime

    @property
    def change_percent(self) -> float:
        """Change against the previous close; 0.0 without a usable baseline."""
        if self.previous_close <= 0:
            return 0.0
        return (self.current_price - self.previous_close) / self.previous_close * 100

    @property
    def change_str(self) -> str:
        return format_change(self.change_percent)

    @property
    def rsi_str(self) -> str:
        return f"{self.rsi_value:.2f}" if self.rsi_value is not None else "N/A"

    @property
    def latest_time_str(self) -> str:
        return self.latest_time.strftime('%m-%d %H:%M')
