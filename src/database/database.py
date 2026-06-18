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
        # 建立複合索引提升查詢效率
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


def _menu_init_database():
    init_database()
    print("資料庫初始化完成。")

def _menu_insert_stock():
    ticker = input("請輸入股票代號（如 2330.TW）: ").strip()
    name   = input("請輸入股票名稱: ").strip()
    market = input("請輸入市場（如 TW / TWO / US）: ").strip()
    insert_stock(ticker, name, market)
    print(f"已新增/更新：{ticker} {name}")

def _menu_delete_stock():
    ticker = input("請輸入要刪除的股票代號: ").strip()
    confirm = input(f"確定要刪除 {ticker} 及其所有歷史價格？(y/N) ").strip().lower()
    if confirm == 'y':
        delete_stock(ticker)
        print(f"已刪除 {ticker}。")
    else:
        print("已取消。")

def _menu_get_stock():
    ticker = input("請輸入股票代號: ").strip()
    info = get_stock(ticker)
    if info:
        print("\n[股票基本資料]")
        for key, value in info.items():
            print(f"  {key:<8} : {value}")
    else:
        print(f"找不到 {ticker}。")

def _menu_get_prices():
    ticker = input("請輸入股票代號: ").strip()
    try:
        limit = int(input("查詢筆數（預設 10）: ").strip() or "10")
    except ValueError:
        limit = 10
    prices = get_daily_prices(ticker, limit=limit)
    if prices:
        print(f"\n[{ticker} 近期 {len(prices)} 筆價格]")
        print(f"{'Date':<12} | {'Open':>8} | {'Close':>8} | {'Volume':>12}")
        print("-" * 50)
        for p in prices:
            open_p  = p.get('open_price')  or 'N/A'
            close_p = p.get('close_price') or 'N/A'
            vol     = p.get('volume')      or 'N/A'
            print(f"{p['date']:<12} | {str(f'{open_p:.2f}'):>8} | {str(f'{close_p:.2f}'):>8} | {str(f'{vol:.0f}'):>12}")
    else:
        print(f"找不到 {ticker} 的價格資料。")

_MENU = [
    ("初始化資料庫",          _menu_init_database),
    ("新增 / 更新股票基本資料", _menu_insert_stock),
    ("刪除股票",              _menu_delete_stock),
    ("查詢股票基本資料",       _menu_get_stock),
    ("查詢歷史價格",           _menu_get_prices),
]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    while True:
        print("\n========== 股票資料庫管理 ==========")
        for i, (label, _) in enumerate(_MENU, start=1):
            print(f"  {i}. {label}")
        print("  0. 離開")
        print("====================================")

        choice = input("請選擇功能: ").strip()
        if choice == "0":
            print("再見！")
            break
        elif choice.isdigit() and 1 <= int(choice) <= len(_MENU):
            print()
            _MENU[int(choice) - 1][1]()
        else:
            print("無效的選項，請重新輸入。")