"""Backfill 10 years of prices for the seeded stocks. Run after seed_stocks; safe to rerun."""
import time
import logging

from src.database import connect_db
from src.data.sync import download_ohlcv, extract_ticker_frame, records_from_frame, upsert_records, fetch_all_tickers, fetch_pending_tickers, mark_backfilled


logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

CHUNK_SIZE = 50
BACKFILL_YEARS = 10
REFRESH_AFTER_DAYS = 180  # Safety net: redo a backfill this long after the last one
MIN_BATCH_INTERVAL = 10  # Seconds between the starts of two consecutive downloads


def backfill_history(period: int, tickers: list[str] | None = None, force: bool = False):
    """Fetch `period` years of history for tickers not backfilled recently.

    Skipping goes by `stocks.last_backfilled`, since a row count cannot tell a finished
    ticker from a newly listed one. `tickers` re-fetches exactly those; `force` re-fetches all.
    """
    logger.info(f"Starting historical backfill for the past {period} years...")

    try:
        with connect_db() as conn:
            if tickers is None:
                tickers = fetch_all_tickers(conn) if force else fetch_pending_tickers(conn, REFRESH_AFTER_DAYS)
            total_stocks = len(tickers)
            total_success = 0

            for i in range(0, total_stocks, CHUNK_SIZE):
                batch_started = time.monotonic()
                chunk_tickers = tickers[i : i + CHUNK_SIZE]
                logger.info(f"Downloading batch {i+1} ~ {min(i + CHUNK_SIZE, total_stocks)}...")

                data = download_ohlcv(chunk_tickers, period=f"{period}y")

                written = []
                for ticker in chunk_tickers:
                    try:
                        frame = extract_ticker_frame(data, ticker)
                        if frame.empty:
                            logger.warning(f"'{ticker}' download failed or has no valid historical data...")
                            continue

                        upsert_records(conn, records_from_frame(ticker, frame))
                        written.append(ticker)
                        total_success += 1

                    except Exception as e:
                        logger.error(f"Failed to process '{ticker}': {e}")
                        continue

                # Same transaction as the prices, so a stamp never lands without them
                mark_backfilled(conn, written)
                conn.commit()
                logger.info(f"Batch write complete, wrote historical data for {len(written)}/{len(chunk_tickers)} stocks!")
                if i + CHUNK_SIZE < total_stocks:
                    time.sleep(max(0, MIN_BATCH_INTERVAL - (time.monotonic() - batch_started)))

            logger.info(f"Historical backfill complete, wrote historical data for {total_success}/{total_stocks} stocks!")

    except Exception as e:
        logger.error(f"Historical backfill failed: {e}")

if __name__ == "__main__":
    backfill_history(BACKFILL_YEARS)
