"""Fetch a ticker's data and assemble its snapshot, shared by `/stock` and the API."""
import asyncio
import logging
from datetime import datetime

import pandas as pd
import pandas_ta as pta

from src.data.fetcher import StockDataFetcher
from src.models.stock import StockSnapshot
from src.quant.errors import InsufficientDataError


logger = logging.getLogger(__name__)


class NoHistoryError(LookupError):
    """The ticker has no daily data in the database."""
    def __init__(self, ticker: str):
        super().__init__(ticker)
        self.ticker = ticker


def build_snapshot(ticker: str, name: str, history_data: pd.DataFrame,
                   intraday_data: pd.DataFrame, latest_time: datetime) -> StockSnapshot:
    """Assemble the current price, change baseline and RSI.

    RSI is computed locally rather than via `compute_indicators`, which would write
    into frames the chart layer still uses.
    """
    if len(history_data) < 2:
        raise InsufficientDataError(f"'{ticker}' has fewer than two historical rows and cannot be processed...")

    prices = history_data['Close']
    rsi = pta.rsi(prices, length=14)  # pyright: ignore[reportPrivateImportUsage, reportCallIssue]

    # Intraday if it traded today, else the last close
    if not intraday_data.empty:
        curr_price = intraday_data['Close'].iloc[-1]
        curr_date = pd.to_datetime(intraday_data.index[-1]).date()
    else:
        curr_price = prices.iloc[-1]
        curr_date = pd.to_datetime(history_data.index[-1]).date()

    # The latest close strictly before today: the baseline for the change %
    past_data = history_data[pd.to_datetime(history_data.index).date < curr_date]
    prev_price = float(past_data['Close'].iloc[-1] if not past_data.empty else prices.iloc[-2])

    def last(series: pd.Series | None) -> float | None:
        """Latest value of a series, or None."""
        if series is None or series.empty:
            return None
        val = series.iloc[-1]
        return float(val) if pd.notna(val) else None

    return StockSnapshot(
        ticker=ticker,
        name=name,
        current_price=float(curr_price),
        previous_close=prev_price,
        rsi_value=last(rsi),
        latest_time=latest_time
    )


async def load_stock(ticker: str) -> tuple[StockSnapshot, pd.DataFrame, pd.DataFrame]:
    """Fetch and build a snapshot; returns the frames too, for the charts.

    Raises `NoHistoryError` without daily data.
    """
    # Blocking calls go to a thread; the constructor hits SQLite too
    fetcher = await asyncio.to_thread(StockDataFetcher, ticker)
    name = await asyncio.to_thread(fetcher.fetch_stock_name)
    history_data, intraday_data = await asyncio.gather(
        asyncio.to_thread(fetcher.fetch_historical_data),
        asyncio.to_thread(fetcher.fetch_intraday_data)
    )

    if history_data.empty:
        logger.warning(f"Failed to retrieve data for '{fetcher.ticker}'...")
        raise NoHistoryError(fetcher.ticker)
    if intraday_data.empty:
        logger.info(f"No intraday data for '{fetcher.ticker}'.")

    snapshot = await asyncio.to_thread(
        build_snapshot, fetcher.ticker, name, history_data, intraday_data, fetcher.latest_time()
    )
    return snapshot, history_data, intraday_data
