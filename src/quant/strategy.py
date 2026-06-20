from abc import ABC, abstractmethod

class Strategy(ABC):
    @abstractmethod
    def signal(self, row, position) -> str:
        ...

class RSIStrategy(Strategy):
    def signal(self, row, position) -> str:
        if position is None and row['RSI'] < 30: return "BUY"
        if position is not None and row['RSI'] > 70: return "SELL"
        return "HOLD"