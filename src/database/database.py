import sqlite3
import os
import logging
from datetime import datetime
from functools import lru_cache
from typing import Any
from contextlib import contextmanager
from collections.abc import Generator


logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname((os.path.dirname(os.path.abspath(__file__)))))

DB_PATH = os.path.join(BASE_DIR, 'stock_data.db')
SQL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sql')


@lru_cache
def load_sql(name: str) -> str:
    """Load a SQL statement from src/database/sql/<name>.sql."""
    with open(os.path.join(SQL_DIR, f'{name}.sql'), encoding='utf-8') as f:
        return f.read()


@contextmanager
def connect_db() -> Generator[sqlite3.Connection]:
    """Open the project database with foreign keys enforced, closing it on exit."""
    connect = sqlite3.connect(DB_PATH)
    connect.execute("PRAGMA foreign_keys = ON")
    try:
        with connect:    # Commit on success, rollback on error
            yield connect
    finally:
        connect.close()

def init_database():
    """Initialize the SQLite database tables."""
    with connect_db() as connect:
        connect.executescript(load_sql('schema'))

    logger.info(f"Database created at {DB_PATH}")


def insert_stock(ticker: str, name: str, market: str) -> None:
    """Insert or update a single stock's master record."""
    with connect_db() as connect:
        cursor = connect.cursor()
        cursor.execute(load_sql('upsert_stock'), (ticker, name, market))


def delete_stock(ticker: str) -> None:
    """Delete a stock and all its prices."""
    with connect_db() as connect:
        cursor = connect.cursor()
        cursor.execute('''
            DELETE FROM daily_prices WHERE ticker = ?
        ''', (ticker,))
        cursor.execute('''
            DELETE FROM stocks WHERE ticker = ?
        ''', (ticker,))


def get_stock(ticker: str) -> dict[str, Any] | None:
    """Query a single stock's master record."""
    with connect_db() as connect:
        connect.row_factory = sqlite3.Row
        cursor = connect.cursor()
        cursor.execute('SELECT * FROM stocks WHERE ticker = ?', (ticker,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_daily_prices(ticker: str, limit: int = 30) -> list[dict[str, Any]]:
    """Get the `limit` most recent price rows for the given stock, newest first."""
    with connect_db() as connect:
        connect.row_factory = sqlite3.Row
        cursor = connect.cursor()
        cursor.execute(load_sql('select_daily_prices'), (ticker, limit))
        return [dict(row) for row in cursor.fetchall()]


def price_change_classes(prices: list[dict[str, Any]]) -> list[str]:
    """'up' / 'down' / 'flat' per row, against the previous trading day."""
    classes = []
    # Newest first, so the previous trading day is the next row
    for i, p in enumerate(prices):
        close_p = p.get('close_price')
        prev_close = prices[i + 1].get('close_price') if i + 1 < len(prices) else None
        if close_p is not None and prev_close is not None:
            classes.append('up' if close_p > prev_close else 'down' if close_p < prev_close else 'flat')
        else:
            classes.append('flat')
    return classes


def export_prices_html(ticker: str, prices: list[dict[str, Any]]):
    """Write price records to an HTML report under exports/."""
    from src.utils.html_report import html_document, html_table, fmt_num, fmt_int, write_report

    rows = []
    for p, cls in zip(prices, price_change_classes(prices)):
        rows.append([
            p.get('date', ''),
            fmt_num(p.get('open_price')),
            fmt_num(p.get('high_price')),
            fmt_num(p.get('low_price')),
            (fmt_num(p.get('close_price')), cls),
            fmt_num(p.get('adjust_close_price')),
            fmt_int(p.get('volume')),
        ])

    table = html_table(['Date', 'Open', 'High', 'Low', 'Close', 'AdjClose', 'Volume'], rows)
    data_range = f"{prices[-1].get('date', '?')} ~ {prices[0].get('date', '?')}"
    html = html_document(
        f'{ticker} — {len(prices)} records',
        table,
        subtitle=f"Data {data_range} · Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    )
    filepath = write_report(html, f'{ticker}_prices')

    print(f"\n>> {len(prices)} records exported to: {filepath}")


if __name__ == "__main__":
    from src.cli.cli_database import run
    run()
