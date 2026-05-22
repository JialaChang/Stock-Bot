from core import StockDataFetcher, TechnicalAnalyzer, StockVisualizer
import os
import platform
import subprocess


def test_local(ticker):
    print(f"正在測試本地分析...")
    
    # 取得股票資料
    fetcher = StockDataFetcher(ticker)
    stock_name = fetcher.fetch_stock_name()
    stock_ticker = fetcher.ticker
    history_data = fetcher.fetch_historical_data()
    intraday_data = fetcher.fetch_intraday_data()
    latest_time = fetcher.fetch_latest_time()
    
    # 進行分析
    snapshot = TechnicalAnalyzer.analyze(stock_ticker, stock_name, history_data, latest_time)
    
    # 產生並顯示圖表
    chart_buffer = StockVisualizer.generate_chart(stock_ticker, history_data)
    print("正在繪製圖表...")
    
    # 將記憶體中的圖片寫入本地實體檔案
    chart_path = "test_chart.png"
    with open(chart_path, "wb") as f:
        f.write(chart_buffer.getbuffer())
    
    print("圖表已儲存，正在使用系統預設程式開啟...")
    
    # 呼叫作業系統預設的圖片檢視器來開啟檔案
    # macOS
    if platform.system() == 'Darwin':
        subprocess.call(('open', chart_path))
    # Windows
    elif platform.system() == 'Windows':
        os.startfile(chart_path)
    # Linux
    else:
        subprocess.call(('xdg-open', chart_path))

    print("-" * 50)
    print(f"股票名稱: {snapshot.name} ({snapshot.ticker})")
    print(f"最新價格: {snapshot.current_price:.2f}")
    print(f"當日漲跌: {snapshot.change_str}")
    print(f"RSI 指標: {snapshot.rsi_value:.2f}")
    print(f"資料時間: {snapshot.latest_time_str}")


if __name__ == "__main__":
    while True:
        print("-" * 50)
        ticker = input("輸入股票代號（輸入 -1 結束）：")
        print("-" * 50)
        if ticker == "-1":
            print("bye bye~")
            break
        test_local(ticker)