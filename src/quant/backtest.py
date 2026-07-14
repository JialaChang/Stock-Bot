import pandas as pd
import sys, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
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

    def export_backtest_result_html(self, result: BacktestResult) -> str:
        """Write the backtest result to an HTML report and return the file path."""
        from src.utils.html_report import html_document, html_table, fmt_num

        def signed_class(v: float) -> str:
            return 'up' if v > 0 else 'down' if v < 0 else 'flat'

        def signal_reason(sig: Signal) -> str:
            reasons = [name for name, holds in sig.conditions.items() if holds]
            return ', '.join(reasons) if reasons else 'N/A'

        # --- Performance summary ---
        total_ret = result.total_return
        summary_rows = [
            ['Total return', (f'{total_ret:+.2f}%', signed_class(total_ret))],
            ['Win rate', f'{result.win_rate:.2f}%'],
            ['Max drawdown', (f'{result.max_drawdown:.2f}%', 'down')],
            ['Trade count', str(result.trade_count)],
            ['Initial capital', fmt_num(result.equity_curve.iloc[0])],
            ['Final capital', fmt_num(result.equity_curve.iloc[-1])],
            ['Equity curve min', fmt_num(result.equity_curve.min())],
            ['Equity curve max', fmt_num(result.equity_curve.max())],
        ]
        summary_table = html_table(None, summary_rows)

        # --- Per-trade table ---
        trade_rows = []
        for t in result.trades:
            roi = t.return_on_investment
            trade_rows.append([
                t.side,
                (f'{roi:+.2f}%', signed_class(roi)),
                (fmt_num(t.profit_and_loss), signed_class(t.profit_and_loss)),
                str(t.entry_date),
                fmt_num(t.entry_price),
                signal_reason(t.entry_signal),
                str(t.exit_date),
                fmt_num(t.exit_price),
                signal_reason(t.exit_signal),
            ])
        trades_table = html_table(
            ['Side', 'Return', 'P&amp;L', 'Entry Date', 'Entry', 'Entry Reason',
             'Exit Date', 'Exit', 'Exit Reason'],
            trade_rows,
        )

        body = (
            f'<h2>Performance</h2>\n{summary_table}\n'
            f'<h2>Trades</h2>\n{trades_table}'
        )
        index = result.equity_curve.index
        data_range = f"{index[0].strftime('%Y-%m-%d')} ~ {index[-1].strftime('%Y-%m-%d')}"
        html = html_document(
            f'{result.ticker} backtest &mdash; {self.strategy.__class__.__name__}',
            body,
            subtitle=f"Data {data_range} · Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )

        export_dir = os.path.join(BASE_DIR, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(export_dir, f'{result.ticker}_backtest_{timestamp}.html')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f">> Backtest report exported to: {filepath}")
        return filepath


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

        if input("╎ Export HTML report? (y/N) ").strip().lower() == 'y':
            engine.export_backtest_result_html(result)
