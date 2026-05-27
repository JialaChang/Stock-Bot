import sys
import os
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

# 隱藏 yfinance 預設的終端機警告訊息
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

TW_CODES = twstock.codes


class StockDataFetcher:
    def __init__(self, ticker: str):
        self._raw_ticker = ticker
        self.ticker = self._format_ticker(ticker)
        self.historical_data = None
        self.intraday_data = None
    

    def _format_ticker(self, ticker: str):
        """處理股票代碼後綴，讓台股可以直接輸入代號不用後綴"""
        try:
            stock_code = ticker.split(".TW")[0]
            if stock_code in TW_CODES:
                if TW_CODES[stock_code].market == '上市':
                    return f"{stock_code}.TW"
                elif TW_CODES[stock_code].market == '上櫃':
                    return f"{stock_code}.TWO"
            return ticker
        except Exception as e:
            print(f"[System] 處理 '{ticker}' 代碼失敗：{e}")
            return ticker


    def _get_database_connection(self) -> sqlite3.Connection:
        """獲取資料庫連線"""
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


    def check_stock_exist(self) -> bool:
        """檢查股票是否存在資料庫"""
        try:
            conn = self._get_database_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM stocks WHERE ticker = ? LIMIT 1", (self.ticker,))
            result = cursor.fetchone() is not None
            cursor.close()
            conn.close()
            return result
        except Exception:
            return False


    def fetch_stock_name(self) -> str:
        """獲取股票名稱"""
        try:
            # 從資料庫獲取名稱
            conn = self._get_database_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM stocks WHERE ticker = ?", (self.ticker,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if result:
                return result[0]
            
            # 從 twstock 獲取台股名稱
            stock_code = self.ticker.split(".TW")[0].split(".TWO")[0]
            if stock_code in TW_CODES:
                return TW_CODES[stock_code].name
            
            return self.ticker

        except Exception as e:
            print(f"[System] 獲取 '{self.ticker}' 名稱失敗：{e}")
            return self.ticker


    def fetch_historical_data(self, period: str = "12mo") -> pd.DataFrame:
        """從資料庫取得歷史日線數據"""
        try:
            days_map = {
                "1mo": 30, "3mo": 90, "6mo": 180, "12mo": 365,
                "2y": 730, "3y": 1095, "5y": 1825, "10y": 3650,
                "max": 36500
            }
            days = days_map.get(period, 240)

            conn = self._get_database_connection()
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # 查找資料庫
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

            self.historical_data = pd.read_sql_query(
                query,
                conn,
                params=(self.ticker, cutoff_date),
                parse_dates=['date'],
                index_col='date'
            )

            conn.close()

            if self.historical_data.empty:
                print(f"[System] 資料庫中無 '{self.ticker}' 的歷史資料...")
            else:
                # 透過比例調整開高低收
                adj_ratio = self.historical_data['AdjClose'] / self.historical_data['Close']
                self.historical_data['Open'] = self.historical_data['Open'] * adj_ratio
                self.historical_data['High'] = self.historical_data['High'] * adj_ratio
                self.historical_data['Low'] = self.historical_data['Low'] * adj_ratio
                self.historical_data['Close'] = self.historical_data['AdjClose']
                
                print(f"[System] 成功從資料庫查詢 '{self.ticker}' 的 {len(self.historical_data)} 筆歷史資料！")
            
            return self.historical_data
        
        except Exception as e:
            print(f"[System] '{self.ticker}' 歷史資料查詢失敗：{e}")
            return pd.DataFrame()

                   
    def fetch_intraday_data(self) -> pd.DataFrame:
        """從 yahoo 下載最新的盤中數據"""
        try:
            stock = yf.Ticker(self.ticker)
            data = stock.history(period="1d", interval="1m", actions=False)
            
            # 如果沒抓到資料直接回傳空表格
            if data.empty:
                print(f"[System] '{self.ticker}' 資料下載失敗...")
                return data
            
            # 只保留開高低收跟成交量
            core_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            data = data[core_cols]
            
            # 清洗空缺數據
            self.intraday_data = data.dropna()

            if not self.intraday_data.empty:
                print(f"[System] 成功下載 '{self.ticker}' 的 {len(self.intraday_data)} 筆盤中資料！")

            return self.intraday_data

        except Exception as e:
            print(f"[System] '{self.ticker}' 資料下載發生錯誤：{e}")
            return pd.DataFrame()
    

    def fetch_latest_time(self) -> pd.Timestamp:
        """獲取最新資料時間並轉為台灣時間"""
        # 從盤中資料取得時間
        if self.intraday_data is not None and not self.intraday_data.empty:
            latest_time = self.intraday_data.index[-1]
        # 從歷史日線資料取得時間
        elif self.historical_data is not None:
            latest_time = self.historical_data.index[-1]
        # 回傳現在時間
        else:
            latest_time = pd.Timestamp.now(tz=pytz.timezone('Asia/Taipei'))

        # 確保有時區資訊
        if latest_time.tz is None:
                latest_time = latest_time.tz_localize('UTC')

        return latest_time.astimezone(pytz.timezone('Asia/Taipei'))
    

    def get_data_count(self) -> dict:
        """獲取該股票的資料統計"""
        conn = self._get_database_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM daily_prices WHERE ticker = ?",
            (self.ticker,)
        )

        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return {
                "total_records": result[0],
                "earliest_date": result[1],
                "latest_date": result[2]
            }
        
        return {"total_records": 0, "earliest_date": None, "latest_date": None}
        

    def _debug_info(self) -> dict:
        """"just for debug :>"""
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
    

# debug test
if __name__ == "__main__":
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