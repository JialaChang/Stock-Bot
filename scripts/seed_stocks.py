import sys
import os
import sqlite3
import twstock
import pandas as pd

# 將專案根目錄加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import DB_PATH, init_database


def import_taiwan_stocks(conn):
    """匯入台股資料，以 twstock 的股票和 ETF 為來源"""
    print("[DB] 開始匯入台股資料...")
    cursor = conn.cursor()
    count = 0
    
    for code, info in twstock.codes.items():
        # 只取股票與 ETF
        if info.type in ['股票', 'ETF']:
            if info.market == '上市':
                ticker = f"{code}.TW"
            elif info.market == '上櫃':
                ticker = f"{code}.TWO"
            else:
                continue
            # 加入資料庫
            cursor.execute('''
                INSERT OR REPLACE INTO stocks (ticker, name, market)
                VALUES (?, ?, ?)
            ''', (ticker, info.name, 'TW'))
            count += 1
            
    conn.commit()
    print(f"[DB] 成功匯入 {count} 檔台股！")


def import_us_stocks(conn):
    """匯入美股資料，以 S&P 500, Dow Jones, Nasdaq 100 為來源"""
    print("[DB] 開始匯入美股資料...")
    cursor = conn.cursor()
    total_count = 0

    # 三個指數在維基百科的網頁表格來源
    urls = {
        "S&P 500": {
            "url": 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies',
            "table_index": 0,        # 網頁中成分股表格的 index
            "ticker_col": 'Symbol',  # 股票代碼
            "name_col": 'Security'   # 股票名稱
        },
        "Dow Jones": {
            "url": 'https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average',
            "table_index": 1,
            "ticker_col": 'Symbol',
            "name_col": 'Company'
        },
        "Nasdaq 100": {
            "url": 'https://en.wikipedia.org/wiki/Nasdaq-100',
            "table_index": 5,
            "ticker_col": 'Ticker',
            "name_col": 'Company'
        }
    }

    for index_name, config in urls.items():
        try:
            print(f"[DB] 正在爬取 {index_name} 成分股...")
            # 加入 User-Agent 偽裝
            tables = pd.read_html(
                config["url"], 
                storage_options={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            data = tables[config["table_index"]]

            count = 0
            # 逐列讀取表格
            for _, row in data.iterrows():
                raw_ticker = str(row[config["ticker_col"]])
                # yfinance 格式處理 -> 將 BRK.B 轉換成 BRK-B
                ticker = raw_ticker.replace('.', '-')
                name = str(row[config["name_col"]])

                # 寫入資料庫
                cursor.execute('''
                        INSERT OR REPLACE INTO stocks (ticker, name, market)
                        VALUES (?, ?, ?)
                    ''', (ticker, name, 'US'))
                count += 1
            
            conn.commit()
            total_count += count
            print(f"[DB] 成功從 {index_name} 匯入 {count} 檔股票...")
        
        except Exception as e:
            print(f"[DB] {index_name} 匯入失敗：{e}")

    print(f"[DB] 成功匯入 {total_count} 檔美股！")


def import_global_indices(conn):
    """匯入全球重要大盤與核心指數"""
    print("[DB] 開始匯入全球重要大盤與核心指數...")
    cursor = conn.cursor()
    
    indices = {
        # 美國指數
        '^GSPC': '標普 500 指數',
        '^DJI': '道瓊工業指數',
        '^IXIC': '那斯達克綜合指數',
        '^SOX': '費城半導體指數',
        '^VIX': '恐慌指數',
        
        # 亞太指數
        '^TWII': '台灣加權指數',
        '^TWOII': '台灣櫃買指數',
        '^HSI': '香港恆生指數',
        '000001.SS': '上證綜合指數',
        '399001.SZ': '深證成指',
        '^KS11': '韓國綜合指數',
        '^N225': '日經 225 指數',

        
        # 歐洲指數
        '^FTSE': '英國富時 100 指數',
        '^GDAXI': '德國 DAX 指數',
        '^FCHI': '法國 CAC 40 指數',
        '^STOXX50E': '歐洲斯托克 50 指數'
    }
    
    count = 0
    for ticker, name in indices.items():
        cursor.execute('''
            INSERT OR REPLACE INTO stocks (ticker, name, market)
            VALUES (?, ?, ?)
        ''', (ticker, name, 'INDEX'))
        count += 1
        
    conn.commit()
    print(f"[DB] 成功匯入 {count} 檔全球大盤指數！")


if __name__ == "__main__":
    # 檢查資料庫
    init_database()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        import_taiwan_stocks(conn)
        import_us_stocks(conn)
        import_global_indices(conn)
        print(f"[DB] 成功完成股票資料匯入！")
    finally:
        conn.close()