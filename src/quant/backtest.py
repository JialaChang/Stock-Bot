import pandas as pd
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.models import BacktestResult, Trade, Position, Signal
from src.quant import compute_indicators, RSIStrategy

INITIAL_CAPITAL = 100_000
STOP_LOSS = 0.15

class BacktestEngine:
    def __init__(self) -> None:
        self.strategy = RSIStrategy()
        self.cumulative_multiplier = 1.0  # 複利乘數
        self.position: Position | None = None
        self.trades: list[Trade] = []
        self.equity: list[float] = []

    def run(self, ticker: str, data: pd.DataFrame) -> BacktestResult:
        """逐日迭代歷史資料進行回測"""
        self.cumulative_multiplier = 1.0
        self.position = None
        self.trades = []
        self.equity = []
        signal = Signal("HOLD", {}, {})

        compute_indicators(ticker, data)
        data = data.dropna()  # 避免指標數值缺失

        for date, row in data.iterrows():
            date = pd.Timestamp(date) # pyright: ignore[reportArgumentType]
            price_open = row['Open']
            price_close = row['Close']

            if signal.action == "ENTER_LONG" and self.position is None:
                self.position = Position(date.date(), price_open, signal, side="LONG")

            elif signal.action == "EXIT_LONG" and self.position is not None and self.position.side == "LONG":
                self.cumulative_multiplier *= price_open / self.position.entry_price
                trade = Trade(ticker,
                              self.position.entry_date, self.position.entry_price,
                              date.date(), price_open,
                              self.position.entry_signal, signal,
                              "LONG")
                self.trades.append(trade)
                self.position = None

            elif signal.action == "ENTER_SHORT" and self.position is None:
                self.position = Position(date.date(), price_open, signal, side="SHORT")

            elif signal.action == "EXIT_SHORT" and self.position is not None and self.position.side == "SHORT":
                self.cumulative_multiplier *= 2 - price_open / self.position.entry_price
                trade = Trade(ticker,
                              self.position.entry_date, self.position.entry_price,
                              date.date(), price_open,
                              self.position.entry_signal, signal,
                              "SHORT")
                self.trades.append(trade)
                self.position = None
            
            elif signal.action == "HOLD":
                pass

            # 盤中止損，直接以止損價成交
            if self.position is not None:
                if self.position.side == "LONG" and row['Low'] / self.position.entry_price < (1 - STOP_LOSS):
                    stop_price = self.position.entry_price * (1 - STOP_LOSS)
                    stop_price = min(stop_price, price_open)  # 跳空開盤低於止損價時以開盤價成交
                    self.cumulative_multiplier *= stop_price / self.position.entry_price
                    exit_signal = Signal("EXIT_LONG",
                                         {"stop_loss": True},
                                         {})
                    trade = Trade(ticker,
                                  self.position.entry_date, self.position.entry_price,
                                  date.date(), stop_price,
                                  self.position.entry_signal, exit_signal,
                                  "LONG")
                    self.trades.append(trade)
                    self.position = None

                elif self.position.side == "SHORT" and row['High'] / self.position.entry_price > (1 + STOP_LOSS):
                    stop_price = self.position.entry_price * (1 + STOP_LOSS)
                    stop_price = max(stop_price, price_open)  # 跳空開盤高於止損價時以開盤價成交
                    self.cumulative_multiplier *= 2 - stop_price / self.position.entry_price
                    exit_signal = Signal("EXIT_SHORT",
                                         {"stop_loss": True},
                                         {})
                    trade = Trade(ticker,
                                  self.position.entry_date, self.position.entry_price,
                                  date.date(), stop_price,
                                  self.position.entry_signal, exit_signal,
                                  "SHORT")
                    self.trades.append(trade)
                    self.position = None
                    
            # 浮動損益
            pnl_ratio = self.position.unrealized_pnl_ratio(price_close) if self.position else 1.0
            self.equity.append(INITIAL_CAPITAL * self.cumulative_multiplier * pnl_ratio)

            # 以今日收盤產生訊號明天使用
            signal = self.strategy.signal(row, self.position)

        # 回測結束強制平倉
        if self.position is not None:
            last_price = data['Close'].iloc[-1]
            last_date = data.index[-1]

            if self.position.side == "LONG":
                self.cumulative_multiplier *= last_price / self.position.entry_price
            else:
                self.cumulative_multiplier *= 2 - last_price / self.position.entry_price

            exit_signal = Signal("EXIT_LONG" if self.position.side == "LONG" else "EXIT_SHORT", 
                                {"end_of_backtest": True},
                                {})
            trade = Trade(ticker,
                        self.position.entry_date, self.position.entry_price,
                        last_date.date(), last_price,
                        self.position.entry_signal, exit_signal,
                        self.position.side)
            
            self.trades.append(trade)
            self.position = None

        equity_curve = pd.Series(self.equity, index=data.index)
        return BacktestResult(ticker, self.trades, equity_curve)
    
    def print_backtest_result(self, result: BacktestResult) -> None:
        """輸出回測結果"""
        for trade in result.trades:
            print("-" * 50)
            if trade.side == "LONG":
                print("LONG:")
                print(f"買入 {trade.entry_date} @{trade.entry_price:.2f}  條件:{trade.entry_signal.conditions}  指標:{trade.entry_signal.values}")
                print(f"賣出 {trade.exit_date} @{trade.exit_price:.2f}  條件:{trade.exit_signal.conditions}  指標:{trade.exit_signal.values}")
                print(f"報酬率: {trade.return_on_investment:.2f}%")
            else:
                print("SHORT:")
                print(f"賣出 {trade.entry_date} @{trade.entry_price:.2f}  條件:{trade.entry_signal.conditions}  指標:{trade.entry_signal.values}")
                print(f"買入 {trade.exit_date} @{trade.exit_price:.2f}  條件:{trade.exit_signal.conditions}  指標:{trade.exit_signal.values}")
                print(f"報酬率: {trade.return_on_investment:.2f}%")

        print("=" * 50)
        print(f"總報酬率：{result.total_return:.2f}%")
        print(f"勝率：{result.win_rate:.2f}%")
        print(f"最大回撤：{result.max_drawdown:.2f}%")
        print(f"交易次數：{result.trade_count}")
        print(f"初始資金: {result.equity_curve.iloc[0]:.2f}")
        print(f"最後資金: {result.equity_curve.iloc[-1]:.2f}")
        print(f"equity_curve 最小值: {result.equity_curve.min():.2f}")
        print(f"equity_curve 最大值: {result.equity_curve.max():.2f}")
        print("=" * 50)


if __name__ == "__main__":
    from src.data import StockDataFetcher
    from src.database import get_stock
    ticker = "AAPL"
    fetcher = StockDataFetcher(ticker)
    data = fetcher.fetch_historical_data(period="5y")
    engine = BacktestEngine()
    result = engine.run(ticker, data)
    engine.print_backtest_result(result)