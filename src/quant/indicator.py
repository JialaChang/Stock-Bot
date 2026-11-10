# pyright: reportCallIssue=false, reportPrivateImportUsage=false, reportArgumentType=false
import pandas as pd
import pandas_ta as pta

from src.quant.errors import InsufficientDataError


MACD_Z_WINDOW = 60  # Rows the MACD line's scale is measured over
MA_LENGTHS = (5, 10, 20, 60, 120, 200, 240)


def compute_indicators(ticker: str, data: pd.DataFrame, columns: list[str] | None = None) -> None:
    """Write indicators into `data` in place. `columns=None` computes all of them."""
    if len(data) < 2:
        raise InsufficientDataError(f"'{ticker}' has fewer than two historical rows and cannot be processed...")

    close = data['Close']
    high = data['High']
    low = data['Low']

    need = set(columns) if columns is not None else None

    def should(*cols: str) -> bool:
        return need is None or bool(need & set(cols))

    # ── RSI ───────────────────────────────────────────────────
    if should('RSI'):
        data['RSI'] = pta.rsi(close, length=14)

    # ── SMA / EMA ─────────────────────────────────────────────
    for n in MA_LENGTHS:
        if should(f'SMA_{n}'):
            data[f'SMA_{n}'] = pta.sma(close, length=n)
    for n in MA_LENGTHS:
        if should(f'EMA_{n}'):
            data[f'EMA_{n}'] = pta.ema(close, length=n)

    # ── MACD ──────────────────────────────────────────────────
    # DIF = EMA(12) - EMA(26), DEM = EMA(DIF, 9), OSC = DIF - DEM.
    # Z is DIF in its own rolling standard deviations, not mean-centred: zero is the reference.
    if should('MACD_dif', 'MACD_dem', 'MACD_osc', 'MACD_z'):
        macd_df = pta.macd(close, fast=12, slow=26, signal=9)
        data['MACD_dif'] = macd_df['MACD_12_26_9']
        data['MACD_dem'] = macd_df['MACDs_12_26_9']
        data['MACD_osc'] = macd_df['MACDh_12_26_9']
        scale = data['MACD_dif'].rolling(MACD_Z_WINDOW).std()
        # A flat stretch has zero scale; `== 0` leaves the warm-up NaNs alone.
        data['MACD_z'] = (data['MACD_dif'] / scale).mask(scale == 0, 0.0)

    # ── Stochastic (KD) ───────────────────────────────────────
    if should('STOCH_K', 'STOCH_D'):
        stoch_df = pta.stoch(high, low, close, k=9, d=3, smooth_k=3)
        data['STOCH_K'] = stoch_df['STOCHk_9_3_3']
        data['STOCH_D'] = stoch_df['STOCHd_9_3_3']

    # ── Bollinger Bands ───────────────────────────────────────
    if should('BB_U', 'BB_M', 'BB_L', 'BB_W'):
        bb_df = pta.bbands(close, length=20, std=2)
        data['BB_U'] = bb_df['BBU_20_2.0_2.0']
        data['BB_M'] = bb_df['BBM_20_2.0_2.0']
        data['BB_L'] = bb_df['BBL_20_2.0_2.0']
        data['BB_W'] = bb_df['BBB_20_2.0_2.0']
