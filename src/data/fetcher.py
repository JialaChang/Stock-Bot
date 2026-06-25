import sys, os
import yfinance as yf
import pandas as pd
import twstock
import pytz
import logging
import sqlite3
from datetime import datetime, timedelta

# 將專案根目錄加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.database import DB_PATH

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)

TW_CODES = twstock.codes

class StockDataFetcher:
    """整合 SQLite / yfinance / twstock 三個資料源的股票查詢服務"""
    def __init__(self, ticker: str):
        self._raw_ticker = ticker
        self.ticker = self._format_ticker(ticker)
        self.historical_data = None
        self.intraday_data = None

    def _format_ticker(self, ticker: str) -> str:
        """將使用者輸入補齊為 Yahoo Finance 格式，查找優先序：本地 DB → twstock → 原始輸入"""
        try:
            # 剝離可能的後綴
            base_code = ticker.split(".")[0]
            
            # 優先從資料庫中尋找是否有對應的完整代碼
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ticker FROM stocks
                    WHERE ticker = ? OR ticker = ? OR ticker = ?
                    LIMIT 1
                ''', (ticker, f"{base_code}.TW", f"{base_code}.TWO"))
                result = cursor.fetchone()
                if result:
                    return result[0]

            # 若資料庫查無此代碼，則使用 twstock 查詢
            if base_code in TW_CODES:
                market = TW_CODES[base_code].market
                return f"{base_code}.TW" if market == '上市' else f"{base_code}.TWO"
            return ticker

        except Exception as e:
            logger.warning(f"處理 '{ticker}' 代碼失敗：{e}")
            return ticker

    def check_stock_exist(self) -> bool:
        """確認股票是否存在於資料庫"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM stocks WHERE ticker = ? LIMIT 1", (self.ticker,))
                return cursor.fetchone() is not None

        except Exception as e:
            logger.error(f"檢查股票是否存在失敗：{e}")
            return False

    def fetch_stock_name(self) -> str:
        """從本地資料庫查詢股票名稱"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM stocks WHERE ticker = ?", (self.ticker,))
                result = cursor.fetchone()

            if result:
                return result[0]
                        
            return self.ticker

        except Exception as e:
            logger.warning(f"獲取 '{self.ticker}' 名稱失敗：{e}")
            return self.ticker

    def fetch_historical_data(self, period: str = "12mo") -> pd.DataFrame:
        """從 SQLite 查詢歷史日線資料，並套用除權息調整"""
        try:
            days_map = {
                "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365,
                "2y": 730, "3y": 1095, "5y": 1825, "10y": 3650,
                "max": 36500
            }
            days = days_map.get(period, 240)
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            query = '''
                SELECT
                    date,
                    open_price AS Open,
                    high_price AS High,
                    low_price AS Low,
                    close_price AS Close,
                    adjust_close_price AS AdjClose,
                    volume AS Volume
                FROM daily_prices
                WHERE ticker = ? AND date >= ?
                ORDER BY date ASC
            '''

            with sqlite3.connect(DB_PATH) as conn:
                self.historical_data = pd.read_sql_query(
                    query,
                    conn,
                    params=(self.ticker, cutoff_date),
                    parse_dates=['date'],
                    index_col='date'
                )

            if self.historical_data.empty:
                logger.info(f"資料庫中無 '{self.ticker}' 的歷史資料...")
            else:
                # 以 AdjClose/Close 比率回推開高低價，消除除權息造成的圖表跳空缺口
                adj_ratio = self.historical_data['AdjClose'] / self.historical_data['Close']
                self.historical_data['Open'] = self.historical_data['Open'] * adj_ratio
                self.historical_data['High'] = self.historical_data['High'] * adj_ratio
                self.historical_data['Low'] = self.historical_data['Low'] * adj_ratio
                self.historical_data['Close'] = self.historical_data['AdjClose']

                logger.info(f"成功從資料庫查詢 '{self.ticker}' 的 {len(self.historical_data)} 筆歷史資料！")

            return self.historical_data

        except Exception as e:
            logger.error(f"'{self.ticker}' 歷史資料查詢失敗：{e}")
            return pd.DataFrame()

    def fetch_intraday_data(self) -> pd.DataFrame:
        """透過 yfinance 取得當日 1 分鐘級盤中資料"""
        try:
            stock = yf.Ticker(self.ticker)
            data = stock.history(period="1d", interval="1m", actions=False)
            
            if data.empty:
                logger.warning(f"'{self.ticker}' 資料下載失敗...")
                return data
            
            # 捨棄 Dividends / Stock Splits 等非 OHLCV 欄位
            core_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            data = data[core_cols]

            # 移除任何含有 NaN 的行
            self.intraday_data = data.dropna()

            if not self.intraday_data.empty:
                logger.info(f"成功下載 '{self.ticker}' 的 {len(self.intraday_data)} 筆盤中資料！")

            return self.intraday_data

        except Exception as e:
            logger.error(f"'{self.ticker}' 資料下載發生錯誤：{e}")
            return pd.DataFrame()

    def fetch_latest_time(self) -> pd.Timestamp:
        """回傳最新資料時間戳 (Asia/Taipei)，優先序：盤中 > 歷史 > 系統時間"""
        if self.intraday_data is not None and not self.intraday_data.empty:
            latest_time = self.intraday_data.index[-1]
        elif self.historical_data is not None and not self.historical_data.empty:
            latest_time = self.historical_data.index[-1]
        else:
            latest_time = pd.Timestamp.now(tz=pytz.timezone('Asia/Taipei'))

        if latest_time.tz is None:
            latest_time = latest_time.tz_localize('UTC')

        return latest_time.astimezone(pytz.timezone('Asia/Taipei'))

    def get_data_count(self) -> dict:
        """回傳該股票在資料庫中的記錄數與日期範圍"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*), MIN(date), MAX(date) FROM daily_prices WHERE ticker = ?",
                    (self.ticker,)
                )
                result = cursor.fetchone()

            if result and result[0] > 0:
                return {
                    "total_records": result[0],
                    "earliest_date": result[1],
                    "latest_date": result[2]
                }
        except Exception as e:
            logger.error(f"獲取 '{self.ticker}' 資料統計失敗: {e}")
            
        return {"total_records": 0, "earliest_date": None, "latest_date": None}

    def _debug_info(self) -> dict:
        hist_data = self.fetch_historical_data()
        intra_data = self.fetch_intraday_data()
        data_count = self.get_data_count()
        
        return {
            "股票代號": self.ticker,
            "股票名稱": self.fetch_stock_name(),
            "存在於資料庫": self.check_stock_exist(),
            "資料庫總筆數": data_count["total_records"],
            "資料庫日期範圍": f"{data_count['earliest_date']} ~ {data_count['latest_date']}",
            "歷史資料筆數": len(hist_data),
            "盤中資料筆數": len(intra_data),
        }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        print("-" * 50)
        ticker = input("Enter the ticker (-1 to exit): ")
        print("-" * 50)
        if ticker == "-1":
            break
        s = StockDataFetcher(ticker)
        debug_report = s._debug_info()
        for key, value in debug_report.items():
            print(f"╎ {key}: {value}")