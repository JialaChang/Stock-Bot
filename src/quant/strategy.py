from abc import ABC, abstractmethod
from src.models import Signal

class Strategy(ABC):
    @abstractmethod
    def signal(self, row, position) -> Signal:
        ...

class RSIStrategy(Strategy):
    def signal(self, row, position) -> Signal:
        rsi = float(row['RSI'])
        if position is None and rsi < 30:
            return Signal(
                "BUY",
                {"rsi_oversold": True},
                {"RSI": rsi}
            )
        if position is not None and rsi > 70:
            return Signal(
                "SELL",
                {"rsi_overbought": True},
                {"RSI": rsi}
            )
        return Signal("HOLD", {}, {"RSI": rsi})