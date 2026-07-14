import sys, os
import sqlite3
import yfinance as yf
import time
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import DB_PATH

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def fetch_all_stocks(conn: sqlite3.Connection, min_record: int) -> list:
    """State filter: compare existing historical row counts and return only the tickers that still need backfilling."""
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM stocks")
    rows = cursor.fetchall()
    all_tickers = [row[0] for row in rows]

    # Use GROUP BY to find tickers that already meet the threshold
    cursor.execute('''
        SELECT ticker FROM daily_prices
        GROUP BY ticker
        HAVING COUNT(*) >= ?
    ''', (min_record,))
    completed_tickers = set([row[0] for row in cursor.fetchall()])

    # Take the set difference: drop tickers that don't need backfilling
    pending_tickers = [t for t in all_tickers if t not in completed_tickers]
    return pending_tickers

def backfill_history(period: int):
    """Historical backfill script: fetch long-period history once when the DB is first built or new tickers are added."""
    logger.info(f"Starting historical backfill for the past {period} years...")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys = ON")

            tickers = fetch_all_stocks(conn, 300)
            total_stocks = len(tickers)
            total_success = 0
            chunk_size = 50

            for i in range(0, total_stocks, chunk_size):
                chunk_tickers = tickers[i : i + chunk_size]
                logger.info(f"Downloading batch {i+1} ~ {min(i + chunk_size, total_stocks)}...")

                data = yf.download(
                    chunk_tickers,
                    period=f"{period}y",
                    interval="1d",
                    group_by='ticker',
                    actions=False,
                    progress=False,
                    auto_adjust=False,
                    threads=True
                )

                success_count = 0
                for ticker in chunk_tickers:
                    try:
                        if len(chunk_tickers) == 1:
                            stock_data = data
                        else:
                            if ticker not in data.columns.levels[0]: # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                                continue
                            stock_data = data[ticker] # pyright: ignore[reportOptionalSubscript]

                        stock_data = stock_data.dropna(subset=['Adj Close']) # pyright: ignore[reportOptionalMemberAccess]
                        if stock_data.empty:
                            logger.warning(f"'{ticker}' download failed or has no valid historical data...")
                            continue

                        records = [
                            (
                                ticker,
                                date.strftime('%Y-%m-%d'), # pyright: ignore[reportAttributeAccessIssue]
                                float(row['Open']),
                                float(row['High']),
                                float(row['Low']),
                                float(row['Close']),
                                float(row['Adj Close']),
                                float(row['Volume'])
                            ) for date, row in stock_data.iterrows()
                        ]

                        # Use executemany for an efficient bulk parameterized write
                        conn.cursor().executemany('''
                            INSERT INTO daily_prices
                            (ticker, date, open_price, high_price, low_price, close_price, adjust_close_price, volume)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(ticker, date) DO UPDATE SET
                                open_price=excluded.open_price,
                                high_price=excluded.high_price,
                                low_price=excluded.low_price,
                                close_price=excluded.close_price,
                                adjust_close_price=excluded.adjust_close_price,
                                volume=excluded.volume
                        ''', records)
                        success_count += 1
                        total_success += 1

                    except Exception as e:
                        logger.error(f"Failed to process '{ticker}': {e}")
                        continue

                conn.commit()
                logger.info(f"Batch write complete, wrote historical data for {success_count}/{len(chunk_tickers)} stocks!")
                # Long-period payloads are large, so use a longer sleep to avoid the YF server refusing connections
                time.sleep(10)

            logger.info(f"Historical backfill complete, wrote historical data for {total_success}/{total_stocks} stocks!")

    except Exception as e:
        logger.error(f"Historical backfill failed: {e}")

if __name__ == "__main__":
    backfill_history(10)
