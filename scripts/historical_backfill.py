import sys
import os
import sqlite3
import yfinance as yf
import pandas as pd
import time

# 將專案根目錄加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import DB_PATH


def fetch_all_stocks(conn: sqlite3.Connection, min_record: int) -> list:
    """從資料庫的 stocks 資料表中取得所有股票代碼，並篩選出未滿 min_record 筆資料的股票"""
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM stocks")
    rows = cursor.fetchall()
    all_tickers = [row[0] for row in rows]

    # 篩選出大於 min_record 筆資料的股票代碼
    cursor.execute('''
        SELECT ticker FROM daily_prices 
        GROUP BY ticker 
        HAVING COUNT(*) >= ?
    ''', (min_record,))
    completed_tickers = set([row[0] for row in cursor.fetchall()])

    # 排除多於資料
    pending_tickers = [t for t in all_tickers if t not in completed_tickers]
    return pending_tickers


def backfill_history(period: int):
    """從 yahooh finanace 下載所有在資料庫中股票的歷史數據"""
    print(f"[DB] 開始近 {period} 年的股票歷史數據回補...")
    conn = sqlite3.connect(DB_PATH)
    # 外鍵檢查
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    
    try:
        tickers = fetch_all_stocks(conn, 300)
        total_stocks = len(tickers)

        total_success = 0
        # 單次下載批次的數量
        chunk_size = 50
        for i in range(0, total_stocks, chunk_size):
            chunk_tickers = tickers[i : i + chunk_size]
            print(f"[DB] 正在下載批次 {i+1} ~ {min(i + chunk_size, total_stocks)} 檔數據...")
            data = yf.download(
                chunk_tickers, 
                period=f"{period}y", 
                interval="1d", 
                group_by='ticker', 
                actions=False, 
                progress=False, 
                auto_adjust=False, 
                threads=True
            )

            success_count = 0
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
                        print(f"[DB] '{ticker}'  下載失敗或無有效歷史數據...")
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
            print(f"[DB] 批次寫入完成，成功填入 {success_count}/{len(chunk_tickers)} 檔的歷史數據！")
            # 等待幾秒防止被封鎖
            time.sleep(10)
        
        print(f"[DB] 歷史資料回補完成，成功填入 {total_success}/{total_stocks} 檔的歷史數據！")

    except Exception as e:
        print(f"[DB] 歷史回補失敗：{e}")
        conn.rollback()

    finally:
        conn.close()

if __name__ == "__main__":
    backfill_history(10)