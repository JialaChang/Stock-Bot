import sqlite3
import os
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# 取得根目錄絕對路徑
BASE_DIR = os.path.dirname(os.path.dirname((os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, 'stock_data.db')

def init_database():
    """初始化 SQLite 資料庫表格"""
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


def insert_stock(ticker: str, name: str, market: str) -> None:
    """新增或更新一檔股票基本資料"""
    with sqlite3.connect(DB_PATH) as connect:
        cursor = connect.cursor()
        cursor.execute('''
            INSERT INTO stocks (ticker, name, market) 
            VALUES (?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET 
                name=excluded.name, 
                market=excluded.market
        ''', (ticker, name, market))
        connect.commit()

def delete_stock(ticker: str) -> None:
    """刪除一檔股票基本資料"""
    with sqlite3.connect(DB_PATH) as connect:
        cursor = connect.cursor()
        cursor.execute('''
            DELETE FROM daily_prices WHERE ticker = ?
        ''', (ticker,))
        cursor.execute('''
            DELETE FROM stocks WHERE ticker = ?
        ''', (ticker,))
        connect.commit()

def get_stock(ticker: str) -> Optional[Dict[str, Any]]:
    """查詢單一股票資料"""
    with sqlite3.connect(DB_PATH) as connect:
        connect.row_factory = sqlite3.Row  # 讓查詢結果能像字典一樣透過欄位名稱取值
        cursor = connect.cursor()
        cursor.execute('SELECT * FROM stocks WHERE ticker = ?', (ticker,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_daily_prices(ticker: str, limit: int = 30) -> List[Dict[str, Any]]:
    """取得指定股票的歷史價格"""
    with sqlite3.connect(DB_PATH) as connect:
        connect.row_factory = sqlite3.Row
        cursor = connect.cursor()
        cursor.execute('''
            SELECT date, open_price, high_price, low_price, close_price, volume 
            FROM daily_prices 
            WHERE ticker = ? 
            ORDER BY date DESC LIMIT ?
        ''', (ticker, limit))
        return [dict(row) for row in cursor.fetchall()]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # --- 測試與美化輸出範例 ---
    stock_info = get_stock("2330.TW")
    
    if stock_info:
        print("\n[股票基本資料]")
        for key, value in stock_info.items():
            print(f"{key:<8} : {value}")
            
    prices = get_daily_prices("2330.TW", limit=5)
    if prices:
        print("\n[近期價格]")
        print(f"{'日期':<12} | {'開盤':<6} | {'收盤':<6} | {'成交量':<10}")
        print("-" * 45)
        for p in prices:
            # 若某些資料為 None，也能安全地印出
            open_p = p.get('open_price') or 'N/A'
            close_p = p.get('close_price') or 'N/A'
            vol = p.get('volume') or 'N/A'
            print(f"{p['date']:<14} | {open_p:<8} | {close_p:<8} | {vol:<10}")