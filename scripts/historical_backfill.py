import sys
import os
import sqlite3
import yfinance as yf
import pandas as pd

# 將專案根目錄加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database.database import DB_PATH

def fetch_all_stocks(conn: sqlite3.Connection) -> list:
    """從資料庫的 stocks 資料表中取得所有股票代碼"""
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM stocks")
    rows = cursor.fetchall()
    # fetchall() 回傳的是 tuple 列表，如 [('AAPL',), ('TSLA',)]
    # 透過 row[0] 轉換成字串列表
    return [row[0] for row in rows]

def backfill_history():
    pass