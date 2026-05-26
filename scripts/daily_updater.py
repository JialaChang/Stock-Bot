import sys
import os
import sqlite3
from datetime import datetime
import yfinance as yf
import pandas as pd
import time

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
    print(f"[DB] 啟動股票每日資料更新...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        tickers = fetch_all_stocks(conn)
        total_stocks = len(tickers)
        print(f"[DB] 成功自資料庫讀取 {total_stocks} 檔股票並開始下載...")

        total_success = 0
        # 單次下載批次的數量
        chunk_size = 100
        for i in range(0, total_stocks, chunk_size):
            success_count = 0
            chunk_tickers = tickers[i : i + chunk_size]
            print(f"[DB] 正在更新批次 {i+1} ~ {min(i+chunk_size, total_stocks)}...")
            # 抓多天的避免休市沒資料
            data = yf.download(
                chunk_tickers, 
                period="5d", 
                interval="1d", 
                group_by='ticker', 
                actions=False, 
                progress=False, 
                auto_adjust=False, 
                threads=True
            )

            # 解析數據並寫入資料庫
            for ticker in chunk_tickers:
                try:
                    # 若單批次數量只有一檔
                    if len(chunk_tickers) == 1:
                        stock_data = data
                    else:
                        if ticker not in data.columns.levels[0]: # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                            continue
                        stock_data = data[ticker] # pyright: ignore[reportOptionalSubscript]

                    stock_data = stock_data.dropna(subset=['Adj Close']) # pyright: ignore[reportOptionalMemberAccess]
                    if stock_data.empty:
                        print(f"[DB] '{ticker}'  下載失敗或無有效最新數據...")
                        continue
                
                    records = []
                    for date, row in stock_data.iterrows():
                        records.append((
                            ticker,
                            date.strftime('%Y-%m-%d'), # pyright: ignore[reportAttributeAccessIssue]
                            float(row['Open']),
                            float(row['High']),
                            float(row['Low']),
                            float(row['Close']),
                            float(row['Adj Close']),
                            float(row['Volume'])
                        ))

                    cursor.executemany('''
                        INSERT OR REPLACE INTO daily_prices
                        (ticker, date, open_price, high_price, low_price, close_price, adjust_close_price, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', records)
                    success_count += 1
                    total_success += 1

                except Exception as e:
                    print(f"[DB] '{ticker}' 處理失敗：{e}")
                    continue
                
            conn.commit()
            print(f"[DB] 批次寫入完成，成功填入 {success_count}/{len(chunk_tickers)} 檔的最新數據！")
            # 等待幾秒防止被封鎖
            time.sleep(3)
            
        print(f"[DB] 每日更新完成，共 {total_success}/{total_stocks} 檔股票成功寫入資料庫！")

    except Exception as e:
        print(f"[DB] 每日更新失敗：{e}")
        conn.rollback()

    finally:
        conn.close()

if __name__ == "__main__":
    update_stock_data()