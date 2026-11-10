import logging
from fastapi import APIRouter, HTTPException

from src.data.snapshot import NoHistoryError, load_stock
from src.quant.errors import InsufficientDataError
from src.api.schemas import SnapshotResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/stock/{ticker}", response_model=SnapshotResponse)
async def get_stock_snapshot(ticker: str):
    try:
        snapshot, _, _ = await load_stock(ticker)
        return SnapshotResponse.model_validate(snapshot)

    except NoHistoryError as e:
        raise HTTPException(status_code=404, detail=(f"Could not retrieve data for '{e.ticker}'. "
                                                     "Check that the ticker is correct, or it may not be in the database yet."))

    except InsufficientDataError as e:
        logger.warning(f"Insufficient data for '{ticker}': {e}")
        raise HTTPException(status_code=422, detail=f"Not enough historical data for '{ticker}'. {e}")

    except Exception as e:
        # The cause may name internal paths, so it is logged but not returned
        logger.error(f"Error building the snapshot for '{ticker}': {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred, please try again later.")
