from abc import ABC, abstractmethod
from pandas import Series
from src.models import Signal, Position

class Strategy(ABC):
    @abstractmethod
    def signal(self, row: Series, position: Position | None) -> Signal:
        ...

class RSIStrategy(Strategy):
    def signal(self, row: Series, position: Position | None) -> Signal:
        rsi = round(float(row['RSI']), 2)

        # Long
        if position is None and rsi < 35:
            return Signal("ENTER_LONG", {"rsi_oversold": True}, {"RSI": rsi})
        if position is not None and position.side == "LONG" and rsi > 70:
            return Signal("EXIT_LONG", {"rsi_overbought": True}, {"RSI": rsi})
        # Short
        if position is None and rsi > 75:
            return Signal("ENTER_SHORT", {"rsi_overbought": True}, {"RSI": rsi})
        if position is not None and position.side == "SHORT" and rsi < 35:
            return Signal("EXIT_SHORT", {"rsi_oversold": True}, {"RSI": rsi})
        
        return Signal("HOLD", {}, {"RSI": rsi})