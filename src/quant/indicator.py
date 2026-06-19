import pandas as pd
import pandas_ta as pta
from src.models import StockSnapshot

def compute_indicators(ticker: str, name: str, history_data: pd.DataFrame, intraday_data: pd.DataFrame, latest_time) -> StockSnapshot:
    """
    執行基礎技術指標計算與資料整合，並回傳標準化資料模型
    """
    if len(history_data) < 2:
        raise ValueError(f"{ticker} 的歷史資料少於兩筆無法處理")
    
    close = history_data['Close']
    high = history_data['High']
    low = history_data['Low']

    # ── RSI ───────────────────────────────────────────────────
    # 衡量近期漲跌幅的相對強弱，輸出 0–100
    # > 70 超買，< 30 超賣
    history_data['RSI'] = pta.rsi(close, length=14) # pyright: ignore[reportPrivateImportUsage]

    # ── SMA 均線 ───────────────────────────────────────────────
    # 簡單移動平均，平滑短期噪音，反映趨勢方向
    # MA5 短線、MA10 中線、MA20 月線、MA60 季線
    history_data['SMA_5'] = pta.sma(close, length=5) # pyright: ignore[reportPrivateImportUsage]
    history_data['SMA_10'] = pta.sma(close, length=10) # pyright: ignore[reportPrivateImportUsage]
    history_data['SMA_20'] = pta.sma(close, length=20) # pyright: ignore[reportPrivateImportUsage]
    history_data['SMA_60'] = pta.sma(close, length=60) # pyright: ignore[reportPrivateImportUsage]

    # ── EMA 均線 ───────────────────────────────────────────────
    history_data['EMA_5'] = pta.ema(close, length=5) # pyright: ignore[reportPrivateImportUsage]
    history_data['EMA_10'] = pta.ema(close, length=10) # pyright: ignore[reportPrivateImportUsage]
    history_data['EMA_20'] = pta.ema(close, length=20) # pyright: ignore[reportPrivateImportUsage]
    history_data['EMA_60'] = pta.sma(close, length=60) # pyright: ignore[reportPrivateImportUsage]

    # ── MACD ───────────────────────────────────────────────────
    # 兩條 EMA 的差值，衡量動能強弱與方向轉換
    # DIF Line = EMA(12) - EMA(26)
    # DEM Line = EMA(MACD, 9)
    # OSC (histogram) = MACD - Signal (正=動能增強，負=動能減弱)
    macd_df = pta.macd(close, fast=12, slow=26, signal=9) # pyright: ignore[reportPrivateImportUsage]
    history_data['MACD_dif'] = macd_df['MACD_12_26_9']
    history_data['MACD_dem'] = macd_df['MACDs_12_26_9']
    history_data['MACD_osc'] = macd_df['MACDh_12_26_9']

    # ── Stochastic Oscialltor (KD 指標) ─────────────────────────
    # 收盤價在近 9 天高低範圍內的相對位置
    # K > 80 超買，K < 20 超賣
    # 黃金交叉（K 上穿 D）在低檔才有效，死亡交叉在高檔才有效
    # 需要 High / Low 欄位
    stoch_df = pta.stoch(high, low, close, k=9, d=3, smooth_k=3) # pyright: ignore[reportPrivateImportUsage]
    history_data['STOCH_K'] = stoch_df['STOCHk_9_3_3']
    history_data['STOCH_D'] = stoch_df['STOCHd_9_3_3']

    # ── Bollinger Bands ─────────────────────────────────────────
    # 中軌 = SMA(20)，上下軌各加減 2 個標準差
    # 觸碰下軌潛在反彈，觸碰上軌潛在回落
    # 帶寬收窄代表即將出現大波動
    bb_df = pta.bbands(close, length=20, std=2) # pyright: ignore[reportArgumentType, reportPrivateImportUsage]
    history_data['BB_U'] = bb_df['BBU_20_2.0']
    history_data['BB_M'] = bb_df['BBM_20_2.0']
    history_data['BB_L'] = bb_df['BBL_20_2.0']
    history_data['BB_W'] = bb_df['BBB_20_2.0']

    # ── 當前價格與漲跌幅 ──────────────────────────────────────────
    if not intraday_data.empty:
        curr_price = intraday_data['Close'].iloc[-1]
        curr_date = pd.to_datetime(intraday_data.index[-1]).date()
    else:
        curr_price = close.iloc[-1]
        curr_date = pd.to_datetime(history_data.index[-1]).date()
    
    # 尋找參考基準價：過濾出早於今日的最新一筆收盤價
    past_data = history_data[pd.to_datetime(history_data.index).date < curr_date]
    prev_price = past_data['Close'].iloc[-1] if not past_data.empty else close.iloc[-2]
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

        # RSI
        rsi_value=last('RSI'),

        # MACD
        # macd_dif=last('MACD_dif'),
        # macd_dem=last('MACD_dem'),
        # macd_osc=last('MACD_osc'),

        # # KD
        # stoch_k=last('STOCH_K'),
        # stoch_d=last('STOCH_D'),

        # # Bollinger Bands
        # bb_upper=last('BB_U'),
        # bb_middle=last('BB_M'),
        # bb_lower=last('BB_L'),
        # bb_width=last('BB_W'),

        latest_time=latest_time,
    )