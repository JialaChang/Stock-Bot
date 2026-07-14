import pandas as pd
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.models import BacktestResult, Trade, Position, Signal
from src.quant import compute_indicators, RSIStrategy, EMAStrategy

INITIAL_CAPITAL = 100_000
STOP_LOSS = 0.15

class BacktestEngine:
    def __init__(self) -> None:
        self.strategy = EMAStrategy()
        self.cumulative_multiplier = 1.0  # Compounding multiplier
        self.position: Position | None = None
        self.trades: list[Trade] = []
        self.equity: list[float] = []

    def run(self, ticker: str, data: pd.DataFrame) -> BacktestResult:
        """Iterate over historical data day by day to run the backtest."""
        self.cumulative_multiplier = 1.0
        self.position = None
        self.trades = []
        self.equity = []
        signal = Signal("HOLD", {}, {})

        compute_indicators(ticker, data, self.strategy.required_columns)
        data = data.dropna(subset=self.strategy.required_columns)

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

            # Intraday stop-loss: fill immediately at the stop price
            if self.position is not None:
                if self.position.side == "LONG" and row['Low'] / self.position.entry_price < (1 - STOP_LOSS):
                    stop_price = self.position.entry_price * (1 - STOP_LOSS)
                    stop_price = min(stop_price, price_open)  # Fill at the open if it gaps below the stop price
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
                    stop_price = max(stop_price, price_open)  # Fill at the open if it gaps above the stop price
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

            # Floating (unrealized) P&L
            pnl_ratio = self.position.unrealized_pnl_ratio(price_close) if self.position else 1.0
            self.equity.append(INITIAL_CAPITAL * self.cumulative_multiplier * pnl_ratio)

            # Generate today's signal from the close, to be used the next day
            signal = self.strategy.signal(row, self.position)

        # Force-close any open position at the end of the backtest
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
        return BacktestResult(ticker, self.trades, equity_curve, data)

    def print_backtest_result(self, result: BacktestResult) -> None:
        """Print the backtest result."""
        for trade in result.trades:
            print("-" * 50)
            if trade.side == "LONG":
                print("LONG:")
                print(f"Buy  {trade.entry_date} @{trade.entry_price:.2f}  conditions:{trade.entry_signal.conditions}  indicators:{trade.entry_signal.values}")
                print(f"Sell {trade.exit_date} @{trade.exit_price:.2f}  conditions:{trade.exit_signal.conditions}  indicators:{trade.exit_signal.values}")
                print(f"Return: {trade.return_on_investment:.2f}%")
            else:
                print("SHORT:")
                print(f"Sell {trade.entry_date} @{trade.entry_price:.2f}  conditions:{trade.entry_signal.conditions}  indicators:{trade.entry_signal.values}")
                print(f"Buy  {trade.exit_date} @{trade.exit_price:.2f}  conditions:{trade.exit_signal.conditions}  indicators:{trade.exit_signal.values}")
                print(f"Return: {trade.return_on_investment:.2f}%")

        print("=" * 50)
        print(f"Total return: {result.total_return:.2f}%")
        print(f"Win rate: {result.win_rate:.2f}%")
        print(f"Max drawdown: {result.max_drawdown:.2f}%")
        print(f"Trade count: {result.trade_count}")
        print(f"Initial capital: {result.equity_curve.iloc[0]:.2f}")
        print(f"Final capital: {result.equity_curve.iloc[-1]:.2f}")
        print(f"Equity curve min: {result.equity_curve.min():.2f}")
        print(f"Equity curve max: {result.equity_curve.max():.2f}")
        print("=" * 50)


if __name__ == "__main__":
    import logging
    from src.data import StockDataFetcher
    from src.quant import RSIStrategy, EMAStrategy

    logging.basicConfig(level=logging.WARNING)

    STRATEGIES = {
        "1": ("RSI", RSIStrategy),
        "2": ("EMA", EMAStrategy),
    }
    PERIODS = {"1mo": 30, "2mo": 60, "3mo": 90, "4mo": 120, "5mo": 150, "6mo": 180, "8mo": 210, "10mo": 240,
               "1y": 365, "2y": 730, "3y": 1095, "4y": 1460, "5y": 1825, "10y": 3650, "max": 36500}

    engine = BacktestEngine()

    while True:
        print("-" * 50)
        while True:
            ticker = input("╎ Enter a ticker (-1 to exit): ").strip()
            if ticker == "-1":
                break
            fetcher = StockDataFetcher(ticker)
            if fetcher.check_stock_exist():
                break
            print(f"╎ Stock '{ticker}' not found, please check the ticker...")
        if ticker == "-1":
            break

        ticker = fetcher.ticker
        name = fetcher.fetch_stock_name()
        print(f"╎ Ticker: {ticker}")
        print(f"╎ Name: {name}")

        print("-" * 50)
        while True:
            strategy_input = input("╎ Choose a strategy [1=RSI, 2=EMA]: ").strip()
            if strategy_input in STRATEGIES:
                break
            print(f"╎ Invalid input, please try again...")
        strategy_label, strategy_cls = STRATEGIES[strategy_input]
        engine.strategy = strategy_cls()
        print(f"╎ Strategy: {strategy_label}")

        print("-" * 50)
        while True:
            period_input = input(f"╎ Choose a backtest period [{'/'.join(PERIODS)}]: ").strip()
            if period_input in PERIODS:
                break
            print(f"╎ Invalid period, please try again...")
        print(f"╎ Backtest period: {period_input}")

        print("-" * 50)
        data = fetcher.fetch_historical_data(days=PERIODS[period_input])
        if data.empty:
            print(f"╎ No historical data found for '{ticker}'...")
            continue

        result = engine.run(ticker, data)
        engine.print_backtest_result(result)
