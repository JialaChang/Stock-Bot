import logging
import sqlite3
from datetime import datetime, timedelta
from typing import cast
import pandas as pd
import yfinance as yf

from src.database import load_sql


logger = logging.getLogger(__name__)

TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'  # ISO order, so strings compare as times

# Relative change in a stored Adj Close that means Yahoo restated the history
ADJ_DRIFT_TOLERANCE = 1e-4

OHLCV_COLUMNS = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']


def download_ohlcv(tickers: list[str], period: str) -> pd.DataFrame:
    """Download unadjusted OHLCV plus Adj Close for a batch of tickers.

    Returns an empty frame on failure, so one failed batch does not abort the rest.
    """
    try:
        data = yf.download(
            tickers,
            period=period,
            interval="1d",
            group_by='ticker',
            actions=False,
            progress=False,
            auto_adjust=False,
            threads=True,
        )
        return data if data is not None else pd.DataFrame()
    except Exception as e:
        logger.warning(f"Download failed for batch of {len(tickers)} tickers: {e}")
        return pd.DataFrame()


def extract_ticker_frame(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Pull one ticker's rows out of a yfinance download, or an empty frame.

    Branches on the frame's columns, since flat vs MultiIndex depends on the yfinance version.
    """
    if data is None or data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        if ticker not in data.columns.get_level_values(0):
            return pd.DataFrame()
        # The stubs type this as a Series; at runtime it is a DataFrame
        frame = cast(pd.DataFrame, data[ticker])
    else:
        frame = data

    if 'Adj Close' not in frame.columns:
        return pd.DataFrame()

    return frame.dropna(subset=['Adj Close'])


def records_from_frame(ticker: str, frame: pd.DataFrame) -> list[tuple]:
    """Convert a ticker's OHLCV frame into upsert parameter tuples."""
    dates = pd.DatetimeIndex(frame.index).strftime('%Y-%m-%d')
    columns = (frame[name].to_numpy(dtype=float) for name in OHLCV_COLUMNS)
    return list(zip([ticker] * len(frame), dates, *columns))


def upsert_records(conn: sqlite3.Connection, records: list[tuple]) -> None:
    """Bulk-write price rows, updating in place on (ticker, date) conflicts."""
    conn.cursor().executemany(load_sql('upsert_daily_price'), records)


def fetch_all_tickers(conn: sqlite3.Connection) -> list[str]:
    """Every ticker in the stock master table."""
    return [row[0] for row in conn.execute("SELECT ticker FROM stocks")]


def fetch_pending_tickers(conn: sqlite3.Connection, max_age_days: int) -> list[str]:
    """Tickers never backfilled, or last backfilled longer than `max_age_days` ago."""
    cutoff = (datetime.now() - timedelta(days=max_age_days)).strftime(TIMESTAMP_FORMAT)
    return [
        row[0] for row in conn.execute(
            "SELECT ticker FROM stocks WHERE last_backfilled IS NULL OR last_backfilled < ?",
            (cutoff,),
        )
    ]


def mark_backfilled(conn: sqlite3.Connection, tickers: list[str]) -> None:
    """Stamp tickers written successfully. Unstamped ones are retried next run."""
    if not tickers:
        return
    now = datetime.now().strftime(TIMESTAMP_FORMAT)
    conn.cursor().executemany(
        "UPDATE stocks SET last_backfilled = ? WHERE ticker = ?",
        [(now, ticker) for ticker in tickers],
    )


def needs_full_refresh(conn: sqlite3.Connection, ticker: str, frame: pd.DataFrame) -> bool:
    """Whether this ticker needs a full re-fetch rather than a short update.

    * Restated Adj Close: a dividend or split rewrote the whole history, so older
      stored rows are on a stale basis.
    * A gap: the stored history stops before the download window.

    The gap check runs first: with no overlapping dates the drift check has nothing to compare.
    Call this before the upsert, which overwrites the values being compared.
    """
    dates = sorted(index.strftime('%Y-%m-%d') for index in frame.index)
    if not dates:
        return False

    cursor = conn.cursor()
    cursor.execute("SELECT MAX(date) FROM daily_prices WHERE ticker = ?", (ticker,))
    row = cursor.fetchone()
    latest_stored = row[0] if row else None
    if latest_stored is None:
        return False  # Nothing stored yet

    if latest_stored < dates[0]:
        logger.info(
            f"'{ticker}' history ends at {latest_stored} but the download starts at {dates[0]};"
            f"the days in between are missing..."
        )
        return True

    placeholders = ','.join('?' * len(dates))
    cursor.execute(
        f"SELECT date, adjust_close_price FROM daily_prices WHERE ticker = ? AND date IN ({placeholders})",
        (ticker, *dates),
    )
    stored = {row[0]: row[1] for row in cursor.fetchall() if row[1] is not None}

    fresh = {pd.Timestamp(index).strftime('%Y-%m-%d'): float(value) for index, value in frame['Adj Close'].items()} # pyright: ignore[reportArgumentType]
    for date, stored_adj in stored.items():
        fresh_adj = fresh.get(date)
        if fresh_adj is None or stored_adj <= 0:
            continue
        if abs(fresh_adj - stored_adj) / stored_adj > ADJ_DRIFT_TOLERANCE:
            logger.info(
                f"'{ticker}' adjusted close for {date} changed {stored_adj:.6f} -> {fresh_adj:.6f};"
                f"older rows are on a stale basis."
            )
            return True
    return False
