import sys
import os
import sqlite3
import yfinance as yf
import time
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import DB_PATH

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def fetch_all_stocks(conn: sqlite3.Connection, min_record: int) -> list:
    """狀態篩選：對比已有歷史資料筆數，僅回傳尚未達標需回補的股票 (ticker) 清單"""
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM stocks")
    rows = cursor.fetchall()
    all_tickers = [row[0] for row in rows]

    # 利用 GROUP BY 聚合找出已經滿足門檻的標的
    cursor.execute('''
        SELECT ticker FROM daily_prices 
        GROUP BY ticker 
        HAVING COUNT(*) >= ?
    ''', (min_record,))
    completed_tickers = set([row[0] for row in cursor.fetchall()])

    # 取差集：過濾掉不需要回補的標的
    pending_tickers = [t for t in all_tickers if t not in completed_tickers]
    return pending_tickers

def backfill_history(period: int):
    """歷史資料回補腳本：在資料庫初始建立或擴增標的時，一次性抓取長週期的歷史數據"""
    logger.info(f"開始近 {period} 年的股票歷史數據回補...")
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            
            tickers = fetch_all_stocks(conn, 300)
            total_stocks = len(tickers)
            total_success = 0
            chunk_size = 50
            
            for i in range(0, total_stocks, chunk_size):
                chunk_tickers = tickers[i : i + chunk_size]
                logger.info(f"正在下載批次 {i+1} ~ {min(i + chunk_size, total_stocks)} 檔數據...")
                
                # 調用 Yahoo Finance API 獲取長週期的全量歷史數據
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
                for ticker in chunk_tickers:
                    try:
                        if len(chunk_tickers) == 1:
                            stock_data = data
                        else:
                            if ticker not in data.columns.levels[0]: # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                                continue
                            stock_data = data[ticker] # pyright: ignore[reportOptionalSubscript]
                        
                        stock_data = stock_data.dropna(subset=['Adj Close']) # pyright: ignore[reportOptionalMemberAccess]
                        if stock_data.empty:
                            logger.warning(f"'{ticker}' 下載失敗或無有效歷史數據...")
                            continue

                        records = [
                            (
                                ticker,
                                date.strftime('%Y-%m-%d'), # pyright: ignore[reportAttributeAccessIssue]
                                float(row['Open']),
                                float(row['High']),
                                float(row['Low']),
                                float(row['Close']),
                                float(row['Adj Close']),
                                float(row['Volume'])
                            ) for date, row in stock_data.iterrows()
                        ]
                        
                        # 利用 executemany 執行高效的批量綁定寫入
                        conn.cursor().executemany('''
                            INSERT OR REPLACE INTO daily_prices
                            (ticker, date, open_price, high_price, low_price, close_price, adjust_close_price, volume)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', records)
                        success_count += 1
                        total_success += 1

                    except Exception as e:
                        logger.error(f"'{ticker}' 處理失敗：{e}")
                        continue
                
                conn.commit()
                logger.info(f"批次寫入完成，成功填入 {success_count}/{len(chunk_tickers)} 檔的歷史數據！")
                # 長週期數據 Payload 較大，放寬 Sleep 避免 YF 伺服器拒絕連線
                time.sleep(10)
            
            logger.info(f"歷史資料回補完成，成功填入 {total_success}/{total_stocks} 檔的歷史數據！")

    except Exception as e:
        logger.error(f"歷史資料回補失敗：{e}")

if __name__ == "__main__":
    backfill_history(10)