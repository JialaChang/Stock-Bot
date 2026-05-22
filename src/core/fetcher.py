import yfinance as yf
import pandas as pd
import twstock
import pytz

TW_CODES = twstock.codes


class StockDataFetcher:
    def __init__(self, ticker: str):
        self._raw_ticker = ticker
        self.ticker = self._format_ticker(ticker)
        self.historical_data = None
        self.intraday_data = None
    

    def _format_ticker(self, ticker: str):
        """處理股票代碼後綴"""
        # 讓台股可以直接輸入代號不用後綴
        try:
            stock_code = ticker.split(".TW")[0]
            if stock_code in TW_CODES and not ticker.endswith(".TW"):
                return f"{stock_code}.TW"
            return ticker
        except Exception:
            return ticker


    def fetch_stock_name(self) -> str:
        """獲取股票名稱"""
        # 如果在台股名單使用中文名稱
        stock_code = self.ticker.split(".TW")[0]
        if stock_code in TW_CODES:
            return TW_CODES[stock_code].name
        return self.ticker
    

    def _download_and_clean(self, period: str, interval: str) -> pd.DataFrame:
        """核心下載資料並清洗"""
        try:
            data = yf.download(self.ticker, period=period, interval=interval, auto_adjust=True, progress=False)
            # 如果資料為空回傳一個空的 dataframe 防止型別錯誤
            if data is None or data.empty:
                return pd.DataFrame()

            # 處理多重索引
            # 若同時下載多檔股票會回傳多重索引欄位
            if isinstance(data.columns, pd.MultiIndex):
                data = data.xs(self.ticker, level=1, axis=1)
            # 確保回傳 DataFrame 而非 Series
            if isinstance(data, pd.Series):
                data = data.to_frame()
                
            # 清除空缺資料 (NaN)
            data.dropna(subset=['Close'], inplace=True)
            return data

        except Exception as e:
            # 攔截斷線或 API 錯誤
            print(f"[Warning] 網路或 API 錯誤：{e}")
            return pd.DataFrame()


    def fetch_historical_data(self, period: str = "12mo", force_refresh: bool = False) -> pd.DataFrame:
        """下載歷史指定期間的資料"""
        # 檢查資料快取
        if self.historical_data is not None and not force_refresh:
            return self.historical_data

        self.fetch_intraday_data(force_refresh=force_refresh)
        self.historical_data = self._download_and_clean(period=period, interval="1d")
        return self.historical_data


    def fetch_intraday_data(self, force_refresh: bool = False) -> pd.DataFrame:
        """下載最新一天的資料"""
        if self.intraday_data is not None and not force_refresh:
            return self.intraday_data

        self.intraday_data = self._download_and_clean(period="1d", interval="1m")
        return self.intraday_data
    

    def fetch_latest_time(self) -> pd.Timestamp:
        """獲取最新資料時間並轉為台灣時間"""
        # 從盤中資料取得時間
        if self.intraday_data is not None:
            latest_time = self.intraday_data.index[-1]
            if latest_time.tz is None:
                latest_time = latest_time.tz_localize('UTC')
            return latest_time.astimezone(pytz.timezone('Asia/Taipei'))
        # 從歷史日線資料取得時間
        if self.historical_data is not None:
            latest_time = self.historical_data.index[-1]
            if latest_time.tz is None:
                latest_time = latest_time.tz_localize('UTC')
            return latest_time.astimezone(pytz.timezone('Asia/Taipei'))  
        # 若都沒有則回傳當前時間防止錯誤
        return pd.Timestamp.now(tz=pytz.timezone('Asia/Taipei'))


    def debug_info(self) -> dict:
        """just for debug :>"""
        hist_data = self.fetch_historical_data()
        intra_data = self.fetch_intraday_data()
        return {
            "股票代號": self.ticker,
            "股票名稱": self.fetch_stock_name(),
            "歷史資料筆數": len(hist_data),
            "盤中資料筆數": len(intra_data),
            "歷史資料欄位": list(hist_data.columns) if not hist_data.empty else [],
        }


# debug test
if __name__ == "__main__":
    while True:
        print("-" * 50)
        ticker = input("Enter the ticker (-1 to exit): ")
        print("-" * 50)
        if ticker == "-1":
            break
        s = StockDataFetcher(ticker)
        debug_report = s.debug_info()
        for key, value in debug_report.items():
            print(f"╎ {key}: {value}")