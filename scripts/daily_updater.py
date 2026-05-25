import sys
import os
import sqlite3
from datetime import datetime
import yfinance as yf
import pandas as pd

# 將專案根目錄加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import DB_PATH


def fetch_all_stocks(conn: sqlite3.Connection) -> list:
    """從資料庫的 stocks 資料表中取得所有股票代碼"""
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM stocks")
    rows = cursor.fetchall()
    # fetchall() 回傳的是 tuple 列表，如 [('AAPL',), ('TSLA',)]
    # 透過 row[0] 轉換成字串列表
    return [row[0] for row in rows]


def update_stock_data():
    """從 yahoo finanace 下載所有在資料庫中股票的最新數據"""
    print(f"[DB] 啟動股票資料更新...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        tickers = fetch_all_stocks(conn)
        total_stocks = len(tickers)
        print(f"[DB] 成功自資料庫讀取 {total_stocks} 檔股票並開始下載...")
        # 抓多天的避免休市沒資料
        data = yf.download(
            tickers, 
            period="5d", 
            interval="1d", 
            group_by='ticker', 
            actions=False, 
            progress=False, 
            auto_adjust=True, 
            threads=True
        )
        print(f"[DB] 資料下載成功，開始填入資料庫...")

        sucess_count = 0
        # 解析數據並寫入資料庫
        for ticker in tickers:
            try:
                # levels[0] 即是股票代碼
                if ticker not in data.columns.levels[0]: # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                    continue
                stock_data = data[ticker] # pyright: ignore[reportOptionalSubscript]

                # 清洗掉休市或空缺的數據
                stock_data = stock_data.dropna(subset=['Close'])
                if stock_data.empty:
                    continue
                # 取得數據時間
                latest_time = stock_data.index[-1].strftime('%Y-%m-%d')
                # 取得開高低收量
                latest_data = stock_data.iloc[-1]
                open_price = float(latest_data['Open'])
                high_price = float(latest_data['High'])
                low_price =  float(latest_data['Low'])
                close_price = float(latest_data['Close'])
                volume = float(latest_data['Volume'])

                # 寫入資料庫
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_prices 
                    (ticker, date, open_price, high_price, low_price, close_price, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (ticker, latest_time, open_price, high_price, low_price, close_price, volume))
                sucess_count += 1

            except Exception as e:
                print(f"[DB] 股票 {ticker} 處理失敗：{e}")
                continue
            
        conn.commit()
        print(f"[DB] 每日更新完成，共 {sucess_count} / {total_stocks} 檔股票成功寫入資料庫！")

    except Exception as e:
        print(f"[DB] 每日更新失敗：{e}")
        conn.rollback()

    finally:
        conn.close()


if __name__ == "__main__":
    update_stock_data()