import sqlite3
import os

# 取得絕對目錄
BASE_DIR = os.path.dirname(os.path.dirname((os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, 'stock_data.db')

def init_database():
    # 連線到資料庫
    connect = sqlite3.connect(DB_PATH)
    # 建立游標物件
    cursor = connect.cursor()

    # 建立股票資本資料表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            market TEXT
        )
    ''')

    # 建立每日歷史價格表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL,
            volume REAL,
            FOREIGN KEY (ticker) REFERENCES stocks (ticker)
        )
    ''')

    # 儲存變更並關閉連線
    connect.commit()
    connect.close()
    print(f"[System] 資料庫已建立於 {DB_PATH}")

if __name__ == "__main__":
    init_database()