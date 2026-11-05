import asyncio
import logging
from fastapi import APIRouter, HTTPException

from src.data import StockDataFetcher
from src.bot import build_snapshot
from src.quant import InsufficientDataError
from src.api import SnapshotResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

@router.get("/stock/{ticker}", response_model=SnapshotResponse)
async def get_stock_snapshot(ticker: str):
    try:
        # Blocking calls go to a thread; the constructor hits SQLite too
        fetcher = await asyncio.to_thread(StockDataFetcher, ticker)
        stock_name = await asyncio.to_thread(fetcher.fetch_stock_name)
        stock_ticker = fetcher.ticker

        history_data, intraday_data = await asyncio.gather(
            asyncio.to_thread(fetcher.fetch_historical_data),
            asyncio.to_thread(fetcher.fetch_intraday_data)
        )

        if history_data.empty:
            logger.warning(f"Failed to retrieve data for '{stock_ticker}'...")
            raise HTTPException(status_code=404, detail=(f"Could not retrieve data for '{stock_ticker}'. "
                                                         "Check that the ticker is correct, or it may not be in the database yet."))
        if intraday_data.empty:
            logger.info(f"No intraday data for '{stock_ticker}', showing the daily chart only.")

        latest_time = fetcher.latest_time()

        snapshot = await asyncio.to_thread(
            build_snapshot, stock_ticker, stock_name, history_data, intraday_data, latest_time
        )
        return SnapshotResponse.model_validate(snapshot)

    # Before the catch-all, which would turn the 404 into a 500
    except HTTPException:
        raise

    except InsufficientDataError as e:
        logger.warning(f"Insufficient data for '{ticker}': {e}")
        raise HTTPException(status_code=422, detail=f"Not enough historical data for '{ticker}'. {e}")

    except Exception as e:
        # The cause may name internal paths, so it is logged but not returned
        logger.error(f"Error building the snapshot for '{ticker}': {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred, please try again later.")