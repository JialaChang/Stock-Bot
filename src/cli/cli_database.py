import logging
from datetime import date

import numpy as np
from rich import box
from rich.table import Table
from rich.text import Text

from src.cli.console import ask, choose, console, run_interactive, success, warn, CHANGE_STYLES, signed_style
from src.data import StockDataFetcher
from src.database.database import (delete_stock, export_prices_html, get_daily_prices, get_stock,
                                   init_database, insert_stock, price_change_classes)
from src.models.stock import format_change
from src.utils.html_report import fmt_num, fmt_int


STALE_AFTER_TRADING_DAYS = 5
YEAR_TRADING_DAYS = 252


def trading_days_behind(last_date: str, today: date) -> int:
    """Weekdays from `last_date` up to `today`; holidays are not excluded."""
    return int(np.busday_count(last_date, today))


def _ask_ticker(prompt: str) -> str:
    """Read a ticker and resolve it the way the bot does (2330 -> 2330.TW)."""
    return StockDataFetcher(ask(prompt)).ticker


def _menu_init_database():
    init_database()
    success("Database initialization complete.")


def _menu_insert_stock():
    ticker = ask("Enter ticker (e.g. 2330.TW)").upper()
    name = ask("Enter stock name")
    market = ask("Enter market (TW / US / INDEX)")
    insert_stock(ticker, name, market)
    success(f"Inserted/Updated: {ticker} {name}")


def _menu_delete_stock():
    ticker = _ask_ticker("Enter the ticker to delete")
    info = get_stock(ticker)
    if info is None:
        warn(f"No master record found for {ticker}...")
        return
    if choose(f"Delete {ticker} ({info['name']}) and all its historical prices?", {"y": "yes", "n": "no"}) == "y":
        delete_stock(ticker)
        success(f"Deleted {ticker}!")
    else:
        console.print("Cancelled...")


def _key_value_table(rows) -> Table:
    table = Table(show_header=False, box=None)
    table.add_column(style="bold")
    table.add_column()
    for key, value in rows:
        table.add_row(key, value if isinstance(value, Text) else str(value))
    return table


def _menu_get_stock():
    fetcher = StockDataFetcher(ask("Enter ticker"))
    info = get_stock(fetcher.ticker)
    if not info:
        warn(f"No master record found for {fetcher.ticker}...")
        return
    console.print()
    coverage = fetcher.get_data_range()
    if coverage["total_records"] == 0:
        console.print(_key_value_table(info.items()))
        console.print()
        warn("No price data in the database yet...")
        return

    first, last = coverage["earliest_date"], coverage["latest_date"]
    behind = trading_days_behind(last, date.today())
    date_range = Text(f"{first} ~ {last}")
    if behind > STALE_AFTER_TRADING_DAYS:
        date_range.append(f"  ({behind} trading days behind)", style="yellow")

    prices = get_daily_prices(fetcher.ticker, limit=YEAR_TRADING_DAYS)
    closes = [p['adjust_close_price'] if p.get('adjust_close_price') is not None else p.get('close_price')
              for p in prices]
    closes = [c for c in closes if c is not None]
    rows = [*info.items(), ("", ""),
            ("records", f"{coverage['total_records']:,}"), ("date range", date_range)]
    if closes:
        last_close = Text(f"{closes[0]:,.2f}")
        if len(closes) > 1 and closes[1] > 0:
            change = (closes[0] - closes[1]) / closes[1] * 100
            last_close.append(f"  {format_change(change)}", style=signed_style(change))
        rows += [("last close", last_close), ("52-week range", f"{min(closes):,.2f} ~ {max(closes):,.2f}")]
    console.print(_key_value_table(rows))


def _menu_get_prices():
    ticker = _ask_ticker("Enter ticker")
    try:
        limit = int(ask("Number of records"))
    except ValueError:
        limit = 0
    if limit <= 0:  # SQLite treats a negative LIMIT as no limit at all
        warn("Number of records must be a positive whole number...")
        return
    prices = get_daily_prices(ticker, limit=limit)
    if not prices:
        warn(f"No price data found for {ticker}...")
        return

    if len(prices) > 50:
        export_prices_html(ticker, prices)
        return

    table = Table(title=f"{ticker} latest {len(prices)} prices", box=box.SIMPLE_HEAD, show_edge=False)
    table.add_column("Date")
    for header in ("Open", "Close", "AdjClose", "Volume"):
        table.add_column(header, justify="right")
    for p, cls in zip(prices, price_change_classes(prices)):
        table.add_row(p['date'],
                      fmt_num(p.get('open_price')),
                      Text(fmt_num(p.get('close_price')), style=CHANGE_STYLES[cls]),
                      fmt_num(p.get('adjust_close_price')),
                      fmt_int(p.get('volume')))
    console.print()
    console.print(table)


MENU = [
    ("Initialize database", _menu_init_database),
    ("Insert / Update stock master record", _menu_insert_stock),
    ("Delete stock", _menu_delete_stock),
    ("Query stock master record", _menu_get_stock),
    ("Query historical prices", _menu_get_prices),
]


def main() -> None:
    """Interactive menu over the database CRUD helpers."""
    options = {str(i): label for i, (label, _) in enumerate(MENU, start=1)} | {"0": "Exit"}
    while True:
        console.rule("Stock Database Manager")
        for key, label in options.items():
            console.print(f"  {key}. {label}")

        choice = choose("Choose an option", options, show_options=False)
        if choice == "0":
            return
        MENU[int(choice) - 1][1]()
        console.print()


def run() -> None:
    """Entry point, launched from `python src/database/database.py`."""
    logging.basicConfig(level=logging.INFO)
    run_interactive(main)
