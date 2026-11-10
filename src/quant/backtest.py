import math
import pandas as pd
from datetime import date as date_type, datetime

from src.models import BacktestResult, Trade, Position, Signal, Side
from src.quant import compute_indicators, Strategy
from src.quant.errors import InsufficientDataError


INITIAL_CAPITAL = 100_000
STOP_LOSS = 0.15
MIN_BACKTEST_ROWS = 2  # Fewer usable rows than this cannot produce a signal and a fill

# Backtest periods in calendar days
PERIOD_DAYS = {
    "1mo": 30, "2mo": 60, "3mo": 90, "4mo": 120, "5mo": 150, "6mo": 180,
    "7mo": 210, "8mo": 240, "9mo": 270, "10mo": 300, "11mo": 330, "12mo": 360,
    "1y": 365, "2y": 730, "3y": 1095, "4y": 1460, "5y": 1825,
    "6y": 2190, "7y": 2555, "8y": 2920, "9y": 3285, "10y": 3650,
    "max": 36500,
}


def history_window(data: pd.DataFrame, i: int, lookback: int | None) -> pd.DataFrame:
    """At most `lookback` rows ending at bar `i` (None: everything up to `i`).

    Ending at `i + 1` makes lookahead impossible. The start is clamped at 0 because a
    negative start would count from the end.
    """
    lo = 0 if lookback is None else max(0, i + 1 - lookback)
    return data.iloc[lo:i + 1]


class BacktestEngine:
    def __init__(self, strategy: Strategy) -> None:
        self.strategy: Strategy = strategy
        self.cash = float(INITIAL_CAPITAL)
        self.position: Position | None = None
        self.trades: list[Trade] = []
        self.equity: list[float] = []

    def required_history_days(self, period_days: int) -> int:
        """Calendar days to fetch so `period_days` can be backtested in full.

        Warm-up and lookback stack: the lookback rows must already carry indicator
        values, so both are fetched on top of the period.
        """
        lookback_rows = self.strategy.lookback or 1
        preroll_rows = self.strategy.warmup + lookback_rows - 1  # the lookback includes today
        preroll_calendar_days = math.ceil(preroll_rows * 7 / 5)
        return period_days + preroll_calendar_days + 7  # one week of buffer

    def run(self, ticker: str, data: pd.DataFrame, start: date_type | pd.Timestamp | None = None) -> BacktestResult:
        """Run the backtest day by day from `start`.

        Rows before `start` are not backtested but stay reachable by the lookback.
        """
        self.cash = float(INITIAL_CAPITAL)
        self.position = None
        self.trades = []
        self.equity = []
        self.strategy.reset()
        signal = Signal("HOLD", {}, {})

        compute_indicators(ticker, data, self.strategy.required_columns)
        data = data.dropna(subset=self.strategy.required_columns)

        # `data` keeps the rows before `start` for the lookback; `window` is what gets reported.
        start_pos = int(data.index.searchsorted(pd.Timestamp(start))) if start is not None else 0
        window = data.iloc[start_pos:]

        if len(window) < MIN_BACKTEST_ROWS:
            raise InsufficientDataError(
                f"'{ticker}' has only {len(window)} usable rows after the {self.strategy.warmup}-row indicator warm-up. "
                f"Choose a longer backtest period, or backfill more history for this ticker."
            )

        for i in range(start_pos, len(data)):
            row = data.iloc[i]
            date = pd.Timestamp(data.index[i])
            price_open = row['Open']
            price_close = row['Close']

            if signal.action == "ENTER_LONG" and self.position is None:
                self._open_position(date, price_open, signal, "LONG")

            elif signal.action == "EXIT_LONG" and self.position is not None and self.position.side == "LONG":
                self._close_position(ticker, date, price_open, signal)

            elif signal.action == "ENTER_SHORT" and self.position is None:
                self._open_position(date, price_open, signal, "SHORT")

            elif signal.action == "EXIT_SHORT" and self.position is not None and self.position.side == "SHORT":
                self._close_position(ticker, date, price_open, signal)

            elif signal.action == "REVERSE_LONG" and self.position is not None and self.position.side == "SHORT":
                self._close_position(ticker, date, price_open, signal)
                self._open_position(date, price_open, signal, "LONG")

            elif signal.action == "REVERSE_SHORT" and self.position is not None and self.position.side == "LONG":
                self._close_position(ticker, date, price_open, signal)
                self._open_position(date, price_open, signal, "SHORT")

            elif signal.action == "HOLD":
                pass

            # Intraday stop-loss
            if self.position is not None:
                if self.position.side == "LONG" and row['Low'] / self.position.entry_price < (1 - STOP_LOSS):
                    stop_price = self.position.entry_price * (1 - STOP_LOSS)
                    stop_price = min(stop_price, price_open)  # Fill at the open if it gaps below the stop price
                    self._close_position(ticker, date, stop_price, Signal("EXIT_LONG", {"Stop loss": True}, {}))

                elif self.position.side == "SHORT" and row['High'] / self.position.entry_price > (1 + STOP_LOSS):
                    stop_price = self.position.entry_price * (1 + STOP_LOSS)
                    stop_price = max(stop_price, price_open)  # Fill at the open if it gaps above the stop price
                    self._close_position(ticker, date, stop_price, Signal("EXIT_SHORT", {"Stop loss": True}, {}))

            self.equity.append(self._mark_to_market(price_close))

            # Signal on today's close, filled at tomorrow's open
            history = history_window(data, i, self.strategy.lookback)
            signal = self.strategy.signal(history, self.position)

        if self.position is not None:
            exit_signal = Signal("EXIT_LONG" if self.position.side == "LONG" else "EXIT_SHORT",
                                 {"End of backtest": True},
                                 {})
            self._close_position(ticker, pd.Timestamp(window.index[-1]), window['Close'].iloc[-1], exit_signal)

        equity_curve = pd.Series(self.equity, index=window.index)
        return BacktestResult(ticker, self.trades, equity_curve, window)

    def _mark_to_market(self, price: float) -> float:
        """Account value at `price`: settled cash plus or minus what the position is worth."""
        if self.position is None:
            return self.cash
        if self.position.side == "LONG":
            return self.cash + self.position.shares * price
        # A short's proceeds are already in cash; the shares owed back are the liability.
        return self.cash - self.position.shares * price

    def _open_position(self, date: pd.Timestamp, price: float, signal: Signal, side: Side) -> None:
        """Open the largest whole-share position the cash allows. Shorts are unleveraged."""
        if not price > 0:
            return
        shares = int(self.cash // price)
        if shares <= 0:
            return
        self.cash += -shares * price if side == "LONG" else shares * price
        self.position = Position(date.date(), price, signal, side, shares)

    def _close_position(self, ticker: str, date: pd.Timestamp, price: float, exit_signal: Signal) -> None:
        """Close the open position at `price` and record the round-trip trade."""
        if self.position is None:
            return
        self.cash += self.position.shares * price if self.position.side == "LONG" else -self.position.shares * price
        self.trades.append(Trade(ticker,
                                 self.position.entry_date,
                                 self.position.entry_price,
                                 date.date(),
                                 price,
                                 self.position.entry_signal,
                                 exit_signal,
                                 self.position.side,
                                 self.position.shares))
        self.position = None

    def export_backtest_result_html(self, result: BacktestResult) -> str:
        """Write the backtest result to an HTML report and return the file path."""
        from src.utils.html_report import html_document, html_table, fmt_int, fmt_num, write_report

        def signal_reason(sig: Signal) -> str:
            reasons = [name for name, holds in sig.conditions.items() if holds]
            return ', '.join(reasons) if reasons else 'N/A'

        summary_table = html_table(None, [
            [label, (text, cls) if cls else text] for label, text, cls in summary_rows(result)
        ])

        trade_rows = []
        for t in result.trades:
            roi = t.return_on_investment
            trade_rows.append([
                t.side,
                (f'{roi:+.2f}%', _signed_class(roi)),
                (fmt_num(t.profit_and_loss), _signed_class(t.profit_and_loss)),
                fmt_int(t.shares),
                str(t.entry_date),
                fmt_num(t.entry_price),
                signal_reason(t.entry_signal),
                str(t.exit_date),
                fmt_num(t.exit_price),
                signal_reason(t.exit_signal),
            ])
        trades_table = html_table(
            ['Side', 'Return', 'P&L', 'Shares', 'Entry Date', 'Entry', 'Entry Reason',
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
            f'{result.ticker} backtest — {self.strategy.__class__.__name__}',
            body,
            subtitle=f"Data {data_range} · Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )
        filepath = write_report(html, f'{result.ticker}_backtest')

        print(f">> Backtest report exported to: {filepath}")
        return filepath


def _signed_class(v: float) -> str:
    return 'up' if v > 0 else 'down' if v < 0 else 'flat'


def summary_rows(result: BacktestResult) -> list[tuple[str, str, str | None]]:
    """Performance summary as (label, text, css_class) rows, shared by the terminal and HTML."""
    curve = result.equity_curve
    return [
        ('Total return', f'{result.total_return:+.2f}%', _signed_class(result.total_return)),
        ('Win rate', f'{result.win_rate:.2f}%', None),
        ('Max drawdown', f'{result.max_drawdown:.2f}%', 'down'),
        ('Trade count', str(result.trade_count), None),
        ('Initial capital', f'{curve.iloc[0]:,.2f}', None),
        ('Final capital', f'{curve.iloc[-1]:,.2f}', None),
        ('Equity curve min', f'{curve.min():,.2f}', None),
        ('Equity curve max', f'{curve.max():,.2f}', None),
    ]


if __name__ == "__main__":
    from src.cli.cli_backtest import run
    run()
