import pandas as pd
import pandas_ta as pta
from models import StockSnapshot

class TechnicalAnalyzer:
    @staticmethod
    def analyze(ticker: str, name: str, data: pd.DataFrame, latest_time) -> StockSnapshot:
        """執行技術分析並回傳 StockSnapshot 資料模型"""

        # 確保 iloc[-2] 時不會出錯
        if len(data) < 2:
            raise ValueError(f"{ticker} 的歷史資料少於兩筆無法處理")

        # 計算技術指標並直接加入 DataFrame
        prices = data['Close']
        data['RSI'] = pta.rsi(prices, length=14) # pyright: ignore[reportPrivateImportUsage]
        data['MA5'] = pta.sma(prices, length=5) # pyright: ignore[reportPrivateImportUsage]
        data['MA10'] = pta.sma(prices, length=10) # pyright: ignore[reportPrivateImportUsage]
        data['MA20'] = pta.sma(prices, length=20) # pyright: ignore[reportPrivateImportUsage]

        # 計算漲跌幅
        curr_price = prices.iloc[-1]
        prev_price = prices.iloc[-2]
        change_percent = (curr_price - prev_price) / prev_price * 100

        # 提取最新數據
        rsi_value = data['RSI'].iloc[-1]

        # 將計算結果封裝成資料模型 Model 回傳
        return StockSnapshot(
            ticker=ticker,
            name=name,
            current_price=float(curr_price),
            change_percent=float(change_percent),
            rsi_value=float(rsi_value),
            latest_time=latest_time
        )