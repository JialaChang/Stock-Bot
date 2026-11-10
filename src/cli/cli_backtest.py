import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from rich import box
from rich.table import Table
from rich.text import Text

from src.cli.console import ask, choose, console, run_interactive, warn, CHANGE_STYLES, signed_style
from src.data import StockDataFetcher
from src.models import BacktestResult
from src.quant import (BacktestEngine, PERIOD_DAYS, InsufficientDataError, Strategy,
                       RSIStrategy, EMAStrategy, gated_strategy, voting_strategy)
from src.quant.backtest import summary_rows


StrategyChoice = tuple[str, Callable[[], Strategy]]  # (label, factory)

STRATEGIES: dict[str, StrategyChoice] = {
    "1": ("RSI", RSIStrategy),
    "2": ("EMA", EMAStrategy),
    "3": ("Gated", gated_strategy),
    "4": ("Vote", voting_strategy),
}
ALL_STRATEGIES = "a"
COMMON_PERIODS = ["6mo", "1y", "3y", "5y", "10y"]  # Keys 1-5; the rest via [m]ore
MORE_PERIODS = "m"


def print_result(result: BacktestResult, trades_shown: int = 10) -> None:
    """Print the performance summary and the latest trades."""
    summary = Table(show_header=False, box=None)
    summary.add_column()
    summary.add_column(justify="right")
    for label, text, cls in summary_rows(result):
        summary.add_row(label, Text(text, style=CHANGE_STYLES[cls] if cls else ""))
    console.print(summary)

    trades = result.trades[-trades_shown:]
    if not trades:
        return
    caption = f"Last {len(trades)} of {result.trade_count} trades" if result.trade_count > len(trades) else None
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, caption=caption)
    table.add_column("Side")
    for header in ("Entry", "Price", "Exit", "Price", "Return"):
        table.add_column(header, justify="right")
    for t in trades:
        roi = t.return_on_investment
        table.add_row(t.side, str(t.entry_date), f"{t.entry_price:,.2f}",
                      str(t.exit_date), f"{t.exit_price:,.2f}",
                      Text(f"{roi:+.2f}%", style=signed_style(roi)))
    console.print()
    console.print(table)


def print_comparison(results: list[tuple[str, BacktestEngine, BacktestResult]]) -> None:
    table = Table(box=box.SIMPLE_HEAD, show_edge=False)
    table.add_column("Strategy")
    for header in ("Return", "Win rate", "Max DD", "Trades"):
        table.add_column(header, justify="right")
    for label, _, r in results:
        table.add_row(label,
                      Text(f"{r.total_return:+.2f}%", style=signed_style(r.total_return)),
                      f"{r.win_rate:.2f}%",
                      Text(f"{r.max_drawdown:.2f}%", style=CHANGE_STYLES['down']),
                      str(r.trade_count))
    console.print(table)


def _choose_ticker() -> StockDataFetcher:
    """Ask until the ticker exists in the database."""
    while True:
        raw = ask("Ticker")
        fetcher = StockDataFetcher(raw)
        if fetcher.stock_exists():
            console.print(Text(f"{fetcher.fetch_stock_name()} ({fetcher.ticker})", style="bold"))
            return fetcher
        warn(f"Stock '{raw}' not found, please check the ticker...")


def _choose_strategies() -> list[StrategyChoice]:
    options = {key: label for key, (label, _) in STRATEGIES.items()} | {ALL_STRATEGIES: "all"}
    choice = choose("Strategy", options)
    return list(STRATEGIES.values()) if choice == ALL_STRATEGIES else [STRATEGIES[choice]]


def _choose_period() -> str:
    options = {str(i): period for i, period in enumerate(COMMON_PERIODS, start=1)} | {MORE_PERIODS: "more"}
    choice = choose("Period", options)
    if choice != MORE_PERIODS:
        return options[choice]
    while True:
        period = ask("Enter a period (e.g. 2y, 9mo)").lower()
        if period in PERIOD_DAYS:
            return period
        warn(f"Invalid period, choose from: {'/'.join(PERIOD_DAYS)}")


def _choose_next() -> str:
    return choose("Next", {"t": "ticker", "s": "strategy", "p": "period", "q": "quit"})


def _run_strategies(fetcher: StockDataFetcher, strategies: list[StrategyChoice],
                    period: str) -> list[tuple[str, BacktestEngine, BacktestResult]]:
    period_days = PERIOD_DAYS[period]
    start = datetime.now() - timedelta(days=period_days)
    results = []
    for label, make_strategy in strategies:
        engine = BacktestEngine(make_strategy())
        # Fetched per strategy, so each run sees exactly what a single-strategy run would
        data = fetcher.fetch_historical_data(days=engine.required_history_days(period_days))
        if data.empty:
            warn(f"No historical data found for '{fetcher.ticker}'...")
            return []
        try:
            results.append((label, engine, engine.run(fetcher.ticker, data, start=start)))
        except InsufficientDataError as e:
            warn(f"{label}: {e}")
    return results


def main() -> None:
    """Interactive backtest: pick a ticker, strategies and a period, then print the results."""
    console.rule("Backtest")
    fetcher = _choose_ticker()
    strategies = _choose_strategies()
    period = _choose_period()

    while True:
        labels = ', '.join(label for label, _ in strategies)
        console.print()
        console.rule(Text(f"{fetcher.ticker} · {labels} · {period}"))
        results = _run_strategies(fetcher, strategies, period)
        if len(results) == 1:
            print_result(results[0][2])
        elif results:
            print_comparison(results)

        console.print()
        if results and choose("Export HTML report?", {"y": "yes", "n": "no"}) == "y":
            for _, engine, result in results:
                engine.export_backtest_result_html(result)

        step = _choose_next()
        if step == "q":
            return
        if step == "t":
            fetcher = _choose_ticker()
        if step in ("t", "s"):
            strategies = _choose_strategies()
        if step in ("t", "p"):
            period = _choose_period()


def run() -> None:
    """Entry point, launched from `python src/quant/backtest.py`."""
    logging.basicConfig(level=logging.WARNING)
    run_interactive(main)
