import sqlite3
import os
import logging
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


if __name__ == "__main__":
    from src.cli.cli_database import run
    run()
