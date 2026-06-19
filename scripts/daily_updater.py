import sys, os
import sqlite3
import yfinance as yf
import time
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import DB_PATH

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def fetch_all_stocks(conn: sqlite3.Connection) -> list:
    """回傳資料庫中所有股票代碼"""
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM stocks")
    rows = cursor.fetchall()
    return [row[0] for row in rows]

def update_stock_data():
    """批次從 Yahoo Finance 下載最新股價並 Upsert 至本地資料庫"""
    logger.info("啟動股票每日資料更新...")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            tickers = fetch_all_stocks(conn)
            total_stocks = len(tickers)
            logger.info(f"成功自資料庫讀取 {total_stocks} 檔股票並開始下載...")

            total_success = 0
            chunk_size = 100

            # 分批請求以降低記憶體峰值並避免觸發 API Rate Limit
            for i in range(0, total_stocks, chunk_size):
                success_count = 0
                chunk_tickers = tickers[i : i + chunk_size]
                logger.info(f"正在更新批次 {i+1} ~ {min(i+chunk_size, total_stocks)}...")

                # 請求多天數據，規避假日、休市或時區差造成當日回傳空值
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

                for ticker in chunk_tickers:
                    try:
                        if len(chunk_tickers) == 1:
                            stock_data = data
                        else:
                            # 單一股票時 yfinance 回傳扁平欄位；多股票時為 MultiIndex，需顯式選取
                            if ticker not in data.columns.levels[0]: # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
                                continue
                            stock_data = data[ticker] # pyright: ignore[reportOptionalSubscript]

                        stock_data = stock_data.dropna(subset=['Adj Close']) # pyright: ignore[reportOptionalMemberAccess]
                        if stock_data.empty:
                            logger.warning(f"'{ticker}' 下載失敗或無有效最新數據...")
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

                        # ON CONFLICT Upsert：更新欄位值但保留原始 id，避免觸發 FK cascade
                        conn.cursor().executemany('''
                            INSERT INTO daily_prices
                            (ticker, date, open_price, high_price, low_price, close_price, adjust_close_price, volume)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(ticker, date) DO UPDATE SET
                                open_price=excluded.open_price,
                                high_price=excluded.high_price,
                                low_price=excluded.low_price,
                                close_price=excluded.close_price,
                                adjust_close_price=excluded.adjust_close_price,
                                volume=excluded.volume
                        ''', records)
                        
                        success_count += 1
                        total_success += 1

                    except Exception as e:
                        logger.error(f"'{ticker}' 處理失敗：{e}")
                        continue
                    
                conn.commit()
                logger.info(f"批次寫入完成，成功填入 {success_count}/{len(chunk_tickers)} 檔的最新數據！")
                # 批次間限速，避免連續大量請求觸發 yfinance 封鎖
                time.sleep(3)
                
            logger.info(f"每日更新完成，共 {total_success}/{total_stocks} 檔股票成功寫入資料庫！")

    except Exception as e:
        logger.error(f"每日更新失敗：{e}")

if __name__ == "__main__":
    update_stock_data()