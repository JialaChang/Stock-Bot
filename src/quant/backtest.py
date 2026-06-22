import pandas as pd
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.models import BacktestResult, Trade, Position
from src.quant import compute_indicators, RSIStrategy

initial_capital = 1_000_000

class BacktestEngine:
    def __init__(self) -> None:
        self.strategy = RSIStrategy()
        self.capital = initial_capital

    def run(self, ticker: str, data: pd.DataFrame) -> BacktestResult:
        """逐日迭代歷史資料進行回測"""
        compute_indicators(ticker, data)

        position: Position | None = None
        trades: list[Trade] = []
        equity: list[float] = []

        for date, row in data.iterrows():
            date = pd.Timestamp(date) # pyright: ignore[reportArgumentType]
            price_now = row['Close']

            if position is None:
                equity.append(self.capital)
            else:
                equity.append(self.capital * (price_now / position.entry_price))  # 浮動損益

            signal = self.strategy.signal(row, position)

            if signal.action == "BUY" and position is None:
                position = Position(date.date(), price_now, signal)

            elif signal.action == "SELL" and position is not None:
                self.capital *= price_now / position.entry_price  # 出場後更新資金
                trade = Trade(ticker,
                              position.entry_date, position.entry_price,
                              date.date(), price_now,
                              position.entry_signal, signal)
                trades.append(trade)
                position = None

            elif signal.action == "HOLD":
                ...
        
        equity_curve = pd.Series(equity, index=data.index)
        return BacktestResult(ticker, trades, equity_curve)
    
if __name__ == "__main__":
    from src.data import StockDataFetcher
    from src.database import get_stock
    ticker = "2330.TW"
    fetcher = StockDataFetcher(ticker)
    data = fetcher.fetch_historical_data(period="10y")
    engine = BacktestEngine()
    result = engine.run(ticker, data)
    
    for trade in result.trades:
        print(f"買入 {trade.entry_date} @{trade.entry_price:.2f}  條件:{trade.entry_signal.conditions}  指標:{trade.entry_signal.values}")
        print(f"賣出 {trade.exit_date} @{trade.exit_price:.2f}  條件:{trade.exit_signal.conditions}  指標:{trade.exit_signal.values}")
        print(f"報酬率:{trade.return_on_investment:.2f}%")
        print("---")

    print(f"總報酬率：{result.total_return:.2f}%")
    print(f"勝率：{result.win_rate:.2f}%")
    print(f"最大回撤：{result.max_drawdown:.2f}%")
    print(f"交易次數：{result.trade_count}")