import pandas as pd
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.models import BacktestResult, Trade
from src.quant import compute_indicators, RSIStrategy

initial_capital = 1_000_000

class BacktestEngine:
    def __init__(self) -> None:
        self.strategy = RSIStrategy()
        self.capital = initial_capital

    def run(self, ticker: str, data: pd.DataFrame) -> BacktestResult:
        """逐日迭代歷史資料進行回測"""
        compute_indicators(ticker, data)

        position = None  # 持倉日期與價格
        trades = []
        equity = []

        for date, row in data.iterrows():
            if position is None:
                equity.append(self.capital)
            else:
                equity.append(self.capital * (row['Close'] / position[1]))  # 浮動損益

            signal = self.strategy.signal(row, position)

            if signal == "BUY" and position is None:
                position = (date.date(), row['Close']) # pyright: ignore[reportAttributeAccessIssue]

            elif signal == "SELL" and position is not None:
                self.capital *= row['Close'] / position[1]  # 出場後更新資金
                trade = Trade(ticker, position[0], position[1], date.date(), row['Close']) # pyright: ignore[reportAttributeAccessIssue]
                trades.append(trade)
                position = None

            elif signal == "HOLD":
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

    print(f"總報酬率：{result.total_return:.2f}%")
    print(f"勝率：{result.win_rate:.2f}%")
    print(f"最大回撤：{result.max_drawdown:.2f}%")
    print(f"交易次數：{result.trade_count}")