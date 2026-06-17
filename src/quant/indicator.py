import pandas as pd
import pandas_ta as pta
from src.models import StockSnapshot

class TechnicalIndicator:
    @staticmethod
    def analyze(ticker: str, name: str, history_data: pd.DataFrame, intraday_data: pd.DataFrame, latest_time) -> StockSnapshot:
        """
        執行基礎技術指標計算與資料整合，並回傳標準化資料模型
        """
        # 完整性校驗 (最少需兩筆以計算漲跌幅)
        if len(history_data) < 2:
            raise ValueError(f"{ticker} 的歷史資料少於兩筆無法處理")

        prices = history_data['Close']
        history_data['RSI'] = pta.rsi(prices, length=14) # pyright: ignore[reportPrivateImportUsage]
        history_data['MA5'] = pta.sma(prices, length=5) # pyright: ignore[reportPrivateImportUsage]
        history_data['MA10'] = pta.sma(prices, length=10) # pyright: ignore[reportPrivateImportUsage]
        history_data['MA20'] = pta.sma(prices, length=20) # pyright: ignore[reportPrivateImportUsage]

        # 盤中有資料時優先採用即時價格，否則退用歷史收盤價
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

        # RSI 需至少 14+1 筆資料才能產生第一個有效值，不足時回傳 NaN
        rsi_value = history_data['RSI'].iloc[-1] if pd.notna(history_data['RSI'].iloc[-1]) else 0.0

        return StockSnapshot(
            ticker=ticker,
            name=name,
            current_price=float(curr_price),
            change_percent=float(change_percent),
            rsi_value=float(rsi_value),
            latest_time=latest_time
        )