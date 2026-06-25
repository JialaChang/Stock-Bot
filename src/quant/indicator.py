import pandas as pd
import pandas_ta as pta
from src.models import StockSnapshot

def compute_indicators(ticker: str, data: pd.DataFrame, columns: list[str] | None = None) -> None:
    """
    量化回測用途：將技術指標原地寫入傳入的資料。\n
    columns 指定需要哪些欄位；None 代表全部計算。
    """
    if len(data) < 2:
        raise ValueError(f"{ticker} 的歷史資料少於兩筆無法處理")

    close = data['Close']
    high = data['High']
    low = data['Low']

    need = set(columns) if columns is not None else None

    def should(*cols: str) -> bool:
        return need is None or bool(need & set(cols))

    # ── RSI ───────────────────────────────────────────────────
    # 衡量近期漲跌幅的相對強弱，輸出 0–100
    # > 70 超買，< 30 超賣
    if should('RSI'):
        data['RSI'] = pta.rsi(close, length=14) # pyright: ignore[reportPrivateImportUsage]

    # ── SMA 均線 ───────────────────────────────────────────────
    # 簡單移動平均，平滑短期噪音，反映趨勢方向
    # MA5 短線、MA10 中線、MA20 月線、MA60 季線
    if should('SMA_5'):
        data['SMA_5'] = pta.sma(close, length=5) # pyright: ignore[reportPrivateImportUsage]
    if should('SMA_10'):
        data['SMA_10'] = pta.sma(close, length=10) # pyright: ignore[reportPrivateImportUsage]
    if should('SMA_20'):
        data['SMA_20'] = pta.sma(close, length=20) # pyright: ignore[reportPrivateImportUsage]
    if should('SMA_60'):
        data['SMA_60'] = pta.sma(close, length=60) # pyright: ignore[reportPrivateImportUsage]

    # ── EMA 均線 ───────────────────────────────────────────────
    # 指數移動平均，對近期價格賦予更高權重，對市場波動反應更靈敏
    if should('EMA_5'):
        data['EMA_5'] = pta.ema(close, length=5) # pyright: ignore[reportPrivateImportUsage]
    if should('EMA_10'):
        data['EMA_10'] = pta.ema(close, length=10) # pyright: ignore[reportPrivateImportUsage]
    if should('EMA_20'):
        data['EMA_20'] = pta.ema(close, length=20) # pyright: ignore[reportPrivateImportUsage]
    if should('EMA_60'):
        data['EMA_60'] = pta.ema(close, length=60) # pyright: ignore[reportPrivateImportUsage]

    # ── MACD ───────────────────────────────────────────────────
    # 兩條 EMA 的差值，衡量動能強弱與方向轉換
    # DIF Line = EMA(12) - EMA(26)
    # DEM Line = EMA(MACD, 9)
    # OSC (histogram) = DEM - DIF
    # 黃金交叉（DIF 上穿 DEM）買入訊號，死亡交叉（DIF 下穿 DEM）賣出訊號
    # 零軸上方交叉強度優於零軸下方，OSC 柱由負轉正代表動能翻多
    if should('MACD_dif', 'MACD_dem', 'MACD_osc'):
        macd_df = pta.macd(close, fast=12, slow=26, signal=9) # pyright: ignore[reportPrivateImportUsage]
        data['MACD_dif'] = macd_df['MACD_12_26_9']
        data['MACD_dem'] = macd_df['MACDs_12_26_9']
        data['MACD_osc'] = macd_df['MACDh_12_26_9']

    # ── Stochastic Oscialltor (KD 指標) ─────────────────────────
    # 收盤價在近 9 天高低範圍內的相對位置
    # K > 80 超買，K < 20 超賣
    # 黃金交叉（K 上穿 D）在低檔才有效，死亡交叉在高檔才有效
    if should('STOCH_K', 'STOCH_D'):
        stoch_df = pta.stoch(high, low, close, k=9, d=3, smooth_k=3) # pyright: ignore[reportPrivateImportUsage]
        data['STOCH_K'] = stoch_df['STOCHk_9_3_3']
        data['STOCH_D'] = stoch_df['STOCHd_9_3_3']

    # ── Bollinger Bands ─────────────────────────────────────────
    # 中軌 = SMA(20)，上下軌各加減 2 個標準差
    # 觸碰下軌潛在反彈，觸碰上軌潛在回落
    # 帶寬收窄代表即將出現大波動
    if should('BB_U', 'BB_M', 'BB_L', 'BB_W'):
        bb_df = pta.bbands(close, length=20, std=2) # pyright: ignore[reportArgumentType, reportPrivateImportUsage]
        data['BB_U'] = bb_df['BBU_20_2.0_2.0']
        data['BB_M'] = bb_df['BBM_20_2.0_2.0']
        data['BB_L'] = bb_df['BBL_20_2.0_2.0']
        data['BB_W'] = bb_df['BBB_20_2.0_2.0']


def compute_indicators_for_discord(ticker: str, name: str, history_data: pd.DataFrame, intraday_data: pd.DataFrame, latest_time) -> StockSnapshot:
    """
    Discord 展示用途：計算 Embed 所需的最小指標集，並組裝成 StockSnapshot 回傳
    """
    if len(history_data) < 2:
        raise ValueError(f"{ticker} 的歷史資料少於兩筆無法處理")

    prices = history_data['Close']
    history_data['RSI'] = pta.rsi(prices, length=14) # pyright: ignore[reportPrivateImportUsage]
    history_data['SMA_5'] = pta.sma(prices, length=5) # pyright: ignore[reportPrivateImportUsage]
    history_data['SMA_10'] = pta.sma(prices, length=10) # pyright: ignore[reportPrivateImportUsage]
    history_data['SMA_20'] = pta.sma(prices, length=20) # pyright: ignore[reportPrivateImportUsage]

    # ── 當前價格與漲跌幅 ──────────────────────────────────────────
    if not intraday_data.empty:
        curr_price = intraday_data['Close'].iloc[-1]
        curr_date = pd.to_datetime(intraday_data.index[-1]).date()
    else:
        curr_price = prices.iloc[-1]
        curr_date = pd.to_datetime(history_data.index[-1]).date()
    
    # 尋找參考基準價：過濾出早於今日的最新一筆收盤價
    past_data = history_data[pd.to_datetime(history_data.index).date < curr_date]
    prev_price = past_data['Close'].iloc[-1] if not past_data.empty else prices.iloc[-2]
    change_percent = (curr_price - prev_price) / prev_price * 100

    # ── 取最新一筆，缺資料時回傳 0.0 ──────────────────────────────
    def last(col):
        if col not in history_data.columns:
            return 0.0
        val = history_data[col].iloc[-1]
        return float(val) if pd.notna(val) else 0.0

    return StockSnapshot(
        ticker=ticker,
        name=name,
        current_price=float(curr_price),
        change_percent=float(change_percent),
        rsi_value=last('RSI'),
        latest_time=latest_time
    )