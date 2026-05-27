import pandas as pd
import pandas_ta as pta
from src.models import StockSnapshot

class TechnicalAnalyzer:
    @staticmethod
    def analyze(ticker: str, name: str, history_data: pd.DataFrame, intraday_data: pd.DataFrame, latest_time) -> StockSnapshot:
        """執行技術分析並回傳 StockSnapshot 資料模型"""

        # 確保 iloc[-2] 時不會出錯
        if len(history_data) < 2:
            raise ValueError(f"{ticker} 的歷史資料少於兩筆無法處理")

        # 計算技術指標並直接加入 DataFrame
        prices = history_data['Close']
        history_data['RSI'] = pta.rsi(prices, length=14) # pyright: ignore[reportPrivateImportUsage]
        history_data['MA5'] = pta.sma(prices, length=5) # pyright: ignore[reportPrivateImportUsage]
        history_data['MA10'] = pta.sma(prices, length=10) # pyright: ignore[reportPrivateImportUsage]
        history_data['MA20'] = pta.sma(prices, length=20) # pyright: ignore[reportPrivateImportUsage]

        # 計算漲跌幅
        if not intraday_data.empty:
            curr_price = intraday_data['Close'].iloc[-1]
            curr_date = pd.to_datetime(intraday_data.index[-1]).date()
        else:
            curr_price = prices.iloc[-1]
            curr_date = pd.to_datetime(history_data.index[-1]).date()
            
        # 從歷史資料中找出日期早於最新日期的最後一筆資料
        past_data = history_data[pd.to_datetime(history_data.index).date < curr_date]
        if not past_data.empty:
            prev_price = past_data['Close'].iloc[-1]
        else:
            # 若找不到更早的日期則退回拿倒數第二筆
            prev_price = prices.iloc[-2]
            
        change_percent = (curr_price - prev_price) / prev_price * 100

        # 提取最新數據
        rsi_value = history_data['RSI'].iloc[-1] if pd.notna(history_data['RSI'].iloc[-1]) else 0.0

        # 將計算結果封裝成資料模型 Model 回傳
        return StockSnapshot(
            ticker=ticker,
            name=name,
            current_price=float(curr_price),
            change_percent=float(change_percent),
            rsi_value=float(rsi_value),
            latest_time=latest_time
        )