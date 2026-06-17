import sys
import os
import sqlite3
import twstock
import pandas as pd
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import DB_PATH, init_database

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def import_taiwan_stocks(conn: sqlite3.Connection):
    """從 twstock 套件的靜態列表，抓取所有台灣上市/上櫃市場的股票"""
    logger.info("開始匯入台股資料...")
    cursor = conn.cursor()
    count = 0
    
    for code, info in twstock.codes.items():
        # 過濾不相干金融商品，僅採納標準股票與 ETF
        if info.type in ['股票', 'ETF']:
            if info.market == '上市':
                ticker = f"{code}.TW"
            elif info.market == '上櫃':
                ticker = f"{code}.TWO"
            else:
                continue
            cursor.execute('''
                INSERT INTO stocks (ticker, name, market)
                VALUES (?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name=excluded.name,
                    market=excluded.market
            ''', (ticker, info.name, 'TW'))
            count += 1
            
    conn.commit()
    logger.info(f"成功匯入 {count} 檔台股！")

def import_us_stocks(conn: sqlite3.Connection):
    """從維基百科的公開表格爬取美股三大指數 (S&P 500 / DJIA / NASDAQ 100) 成分股"""
    logger.info("開始匯入美股資料...")
    cursor = conn.cursor()
    total_count = 0

    # 定義目標維基百科網址與 DOM 內表格層級 (Table Index) 的映射配置
    urls = {
        "S&P 500": {
            "url": 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies',
            "table_index": 0,
            "ticker_col": 'Symbol',
            "name_col": 'Security'
        },
        "Dow Jones": {
            "url": 'https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average',
            "table_index": 1,
            "ticker_col": 'Symbol',
            "name_col": 'Company',
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
            logger.info(f"正在爬取 {index_name} 成分股...")
            # 由於維基百科對 Default Bot 會進行攔截，需透過偽造 User-Agent 頭部進行繞過
            tables = pd.read_html(
                config["url"], 
                storage_options={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            data = tables[config["table_index"]]

            # 清洗資料格式：將美股特殊的代碼如 BRK.B 轉成 Yahoo API 相容的 BRK-B
            records = [
                (str(row[config["ticker_col"]]).replace('.', '-'), str(row[config["name_col"]]), 'US')
                for _, row in data.iterrows()
            ]
            
            cursor.executemany('''
                INSERT INTO stocks (ticker, name, market)
                VALUES (?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name=excluded.name,
                    market=excluded.market
            ''', records)
            
            conn.commit()
            count = len(records)
            total_count += count
            logger.info(f"成功從 {index_name} 匯入 {count} 檔股票...")
        
        except Exception as e:
            logger.error(f"{index_name} 匯入失敗：{e}")

    logger.info(f"成功匯入 {total_count} 檔美股！")

def import_global_indices(conn: sqlite3.Connection):
    """硬編碼寫入全球重要大盤指數"""
    logger.info("開始匯入全球重要大盤與核心指數...")
    cursor = conn.cursor()
    
    indices = {
        # 美國與期權指標
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
    
    records = [(ticker, name, 'INDEX') for ticker, name in indices.items()]
    
    cursor.executemany('''
        INSERT INTO stocks (ticker, name, market)
        VALUES (?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            name=excluded.name,
            market=excluded.market
    ''', records)
        
    conn.commit()
    logger.info(f"成功匯入 {len(records)} 檔全球大盤指數！")

if __name__ == "__main__":
    # 檢查資料庫
    init_database()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            import_taiwan_stocks(conn)
            import_us_stocks(conn)
            import_global_indices(conn)
            logger.info("成功完成股票資料匯入！")
    except Exception as e:
        logger.error(f"資料匯入過程發生錯誤: {e}")