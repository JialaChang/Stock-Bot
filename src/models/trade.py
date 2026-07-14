from dataclasses import dataclass
from datetime import date
import pandas as pd
from typing import Literal


@dataclass
class Signal:
    """A buy/sell signal along with the strategy conditions that produced it."""
    action: Literal["ENTER_LONG", "EXIT_LONG", "ENTER_SHORT", "EXIT_SHORT", "HOLD"]
    conditions: dict[str, bool]  # Whether each sub-condition holds
    values: dict[str, float]     # Indicator values at trigger time

@dataclass
class Position:
    """An open position and the signal that opened it."""
    entry_date: date
    entry_price: float
    entry_signal: Signal
    side: Literal["LONG", "SHORT"]

    def unrealized_pnl_ratio(self, price_now: float) -> float:
        if self.side == "LONG":
            return price_now / self.entry_price
        else:  # SHORT
            return 2 - price_now / self.entry_price
                #  = 1 + (entry_price - price_now) / entry_price


@dataclass
class Trade:
    """Record of a single completed round-trip trade."""
    ticker: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    entry_signal: Signal
    exit_signal: Signal
    side: Literal["LONG", "SHORT"]
    shares: int = 1  # Number of shares traded

    @property
    def profit_and_loss(self) -> float:
        if self.side == "LONG":
            return (self.exit_price - self.entry_price) * self.shares
        else:
            return (self.entry_price - self.exit_price) * self.shares

    @property
    def return_on_investment(self) -> float:
        if self.side == "LONG":
            return (self.exit_price / self.entry_price - 1) * 100
        else:
            return (1 - self.exit_price / self.entry_price) * 100

    @property
    def is_profit(self) -> bool:
        return self.profit_and_loss > 0


@dataclass
class BacktestResult:
    """Aggregated result of a single complete backtest run."""
    ticker: str
    trades: list[Trade]
    equity_curve: pd.Series  # index=date, value=netWorth
    data: pd.DataFrame  # OHLCV data

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
