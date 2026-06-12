import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

# 取得根目錄絕對路徑
BASE_DIR = os.path.dirname(os.path.dirname((os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, 'stock_data.db')

def init_database():
    """初始化 SQLite 資料庫綱要與索引"""
    with sqlite3.connect(DB_PATH) as connect:
        cursor = connect.cursor()
        # 股票基本資料表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                ticker TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                market TEXT
            )
        ''')
        # 每日歷史價格表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                open_price REAL,
                high_price REAL,
                low_price REAL,
                close_price REAL,
                adjust_close_price REAL,
                volume REAL,
                FOREIGN KEY (ticker) REFERENCES stocks (ticker),
                UNIQUE(ticker, date)
            )
        ''')
        # 建立複合索引 (Composite Index) 提升查詢效率
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS index_ticker_date 
            ON daily_prices (ticker, date)
        ''')
        connect.commit()
        
    logger.info(f"資料庫已建立於 {DB_PATH}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_database()