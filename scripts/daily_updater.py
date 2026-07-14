import sys, os
import sqlite3
import yfinance as yf
import time
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import DB_PATH, load_sql

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def fetch_all_stocks(conn: sqlite3.Connection) -> list:
    """Return all stock tickers in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM stocks")
    rows = cursor.fetchall()
    return [row[0] for row in rows]

def update_stock_data():
    """Batch-download the latest prices from Yahoo Finance and upsert them into the local database."""
    logger.info("Starting daily stock data update...")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            tickers = fetch_all_stocks(conn)
            total_stocks = len(tickers)
            logger.info(f"Loaded {total_stocks} stocks from the database, starting download...")

            total_success = 0
            chunk_size = 100

            # Request in batches to lower peak memory usage and avoid hitting the API rate limit
            for i in range(0, total_stocks, chunk_size):
                success_count = 0
                chunk_tickers = tickers[i : i + chunk_size]
                logger.info(f"Updating batch {i+1} ~ {min(i+chunk_size, total_stocks)}...")

                # Request several days to work around holidays, market closures, or timezone gaps returning empty for today
                data = yf.download(
                    chunk_tickers,
                    period="5d",
                    interval="1d",
                    group_by='ticker',
                    actions=False,
                    progress=False,
                    auto_adjust=False,
                    threads=True
                )

                for ticker in chunk_tickers:
                    try:
                        if len(chunk_tickers) == 1:
                            stock_data = data
                        else:
                            # For a single stock yfinance returns flat columns; for multiple it returns a MultiIndex that must be selected explicitly
                            if ticker not in data.columns.levels[0]: # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                                continue
                            stock_data = data[ticker] # pyright: ignore[reportOptionalSubscript]

                        stock_data = stock_data.dropna(subset=['Adj Close']) # pyright: ignore[reportOptionalMemberAccess]
                        if stock_data.empty:
                            logger.warning(f"'{ticker}' download failed or has no valid latest data...")
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

                        conn.cursor().executemany(load_sql('upsert_daily_price'), records)

                        success_count += 1
                        total_success += 1

                    except Exception as e:
                        logger.error(f"Failed to process '{ticker}': {e}")
                        continue

                conn.commit()
                logger.info(f"Batch write complete, wrote latest data for {success_count}/{len(chunk_tickers)} stocks!")
                # Rate-limit between batches to avoid getting blocked by yfinance from too many consecutive requests
                time.sleep(3)

            logger.info(f"Daily update complete, wrote {total_success}/{total_stocks} stocks to the database!")

    except Exception as e:
        logger.error(f"Daily update failed: {e}")

if __name__ == "__main__":
    update_stock_data()
