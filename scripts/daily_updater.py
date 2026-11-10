"""Incremental daily price update; schedule externally (e.g. cron) after market close."""
import time
import logging

from src.database.database import connect_db
from src.data.sync import download_ohlcv, extract_ticker_frame, records_from_frame, upsert_records, needs_full_refresh, fetch_all_tickers


logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

CHUNK_SIZE = 100
BACKFILL_YEARS = 10
MIN_BATCH_INTERVAL = 3  # Seconds between the starts of two consecutive downloads


def update_stock_data() -> list[str]:
    """Download the latest prices and upsert them. Returns tickers needing a full re-fetch."""
    logger.info("Starting daily stock data update...")
    stale_tickers: list[str] = []

    try:
        with connect_db() as conn:
            tickers = fetch_all_tickers(conn)
            total_stocks = len(tickers)
            logger.info(f"Loaded {total_stocks} stocks from the database, starting download...")

            total_success = 0

            for i in range(0, total_stocks, CHUNK_SIZE):
                batch_started = time.monotonic()
                success_count = 0
                chunk_tickers = tickers[i : i + CHUNK_SIZE]
                logger.info(f"Updating batch {i+1} ~ {min(i+CHUNK_SIZE, total_stocks)}...")

                # Several days, so holidays and timezone gaps still return data
                data = download_ohlcv(chunk_tickers, period="5d")

                for ticker in chunk_tickers:
                    try:
                        frame = extract_ticker_frame(data, ticker)
                        if frame.empty:
                            logger.warning(f"'{ticker}' download failed or has no valid latest data...")
                            continue

                        # Before the upsert, which overwrites the values compared
                        if needs_full_refresh(conn, ticker, frame):
                            stale_tickers.append(ticker)

                        upsert_records(conn, records_from_frame(ticker, frame))

                        success_count += 1
                        total_success += 1

                    except Exception as e:
                        logger.error(f"Failed to process '{ticker}': {e}")
                        continue

                conn.commit()
                logger.info(f"Batch write complete, wrote latest data for {success_count}/{len(chunk_tickers)} stocks!")
                if i + CHUNK_SIZE < total_stocks:
                    time.sleep(max(0, MIN_BATCH_INTERVAL - (time.monotonic() - batch_started)))

            logger.info(f"Daily update complete, wrote {total_success}/{total_stocks} stocks to the database!")

    except Exception as e:
        logger.error(f"Daily update failed: {e}")

    return stale_tickers


if __name__ == "__main__":
    stale = update_stock_data()

    if stale:
        from scripts.historical_backfill import backfill_history

        logger.info(f"{len(stale)} stocks have a stale or incomplete history, re-fetching in full...")
        backfill_history(BACKFILL_YEARS, tickers=stale)
