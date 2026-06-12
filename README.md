# Stock Bot

![Python Version](https://img.shields.io/badge/python-3.13%2B-blue)
![Managed by uv](https://img.shields.io/badge/managed%20by-uv-purple)
![License](https://img.shields.io/badge/license-MIT-green)

<div>
  
  [![邀請機器人](https://img.shields.io/badge/邀請機器人到伺服器-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1494994206425612399)
  
  <img src="./docs/image.png" width="300" alt="圖表頁面">
</div>

## 專案結構

```
stock-bot/
├── src/                           # 系統核心程式碼
│   │
│   ├── bot/                       # 表現層 (Presentation Layer)
│   │   ├── __init__.py
│   │   ├── dc_bot.py              # Discord 機器人主程式與事件監聽
│   │   └── dc_bot_view.py         # Discord 互動介面 (UI 元件與按鈕邏輯)
│   │
│   ├── data/                      # 數據層 (Data Layer)
│   │   ├── __init__.py
│   │   └── fetcher.py             # Yahoo Finance 歷史與盤中資料抓取模組
│   │
│   ├── quant/                     # 業務邏輯層 (Business Logic Layer)
│   │   ├── __init__.py
│   │   └── indicator.py            # 技術指標計算 (RSI, MA 等)
│   │
│   ├── database/                  # 儲存層 (Data Access Layer)
│   │   ├── __init__.py
│   │   └── database.py            # SQLite 資料庫建立與操作
│   │
│   ├── models/                    # 資料模型 (Data Models)
│   │   ├── __init__.py
│   │   └── stock.py               # StockSnapshot 資料類別定義
│   │
│   └── utils/                     # 工具模組 (Utilities)
│       ├── __init__.py
│       └── visualizer.py          # K線圖與分時走勢圖繪製模組
│
├── scripts/                       # 自動化任務腳本：獨立於主程式運作的批次作業
│   ├── seed_stocks.py             # 匯入台美股與全球指數基本名單到資料庫
│   ├── historical_backfill.py     # 批次下載與回補歷史 K 線資料
│   └── daily_updater.py           # 每日盤後股價更新與維護作業
│
├── docs/                          # 專案文件與靜態資源
│   └── image.png                  # 系統運作展示或架構說明圖
│
├── stock_data.db                  # SQLite 資料庫檔案 (初次執行自動生成)
├── pyproject.toml                 # 專案依賴套件與環境設定檔
├── README.md                      # 專案主說明文件
├── UML.md                         # 專案 UML 架構 
├── main.py                        # 系統主進入點：負責啟動 Discord 機器人
└── .env                           # 環境變數設定檔 (存放 Token 等敏感機密)
```

## 模組說明

### StockDataFetcher (`src/data/fetcher.py`)
負責從 Yahoo Finance 獲取股票資料：
- 自動處理股票代碼後綴（台股無需添加 `.TW`）
- 獲取歷史資料和盤中資料
- 獲取股票名稱和最新交易時間
- 自動時區轉換 (UTC → 台灣時間)

### TechnicalIdicator (`src/quant/indicator.py`)
執行技術分析：
- 計算 RSI（相對強度指數）
- 計算移動平均線（5、10、20 日期）
- 計算漲跌幅百分比
- 返回 StockSnapshot 資料模型

### StockVisualizer (`src/utils/visualizer.py`)
生成專業股票圖表：
- 歷史日線圖：K 線圖 + 均線 + 成交量
- 盤中分時圖：分鐘級走勢 + 開盤價參考線
- 輸出為 PNG 格式，可直接供 Discord 上傳

### DiscordStockChart (`src/bot/dc_bot_view.py`)
Discord 訊息互動介面：
- 提供按鈕在歷史日線圖和盤中分時圖之間切換
- 自動超時機制（5 分鐘後自動清理）
- 非同步事件處理

## 支援的股票市場

### 台灣股票 (Taiwan Stock Exchange / TPEX)
- **上市股票** (TSE)：輸入股票代碼即可，機器人自動添加 `.TW` 後綴
  - 例：`2330` → `2330.TW`（台積電）
- **上櫃股票** (TPEX)：輸入股票代碼即可，機器人自動添加 `.TWO` 後綴
  - 例：`1101` → `1101.TWO`（寶碩）
- 支援所有在台灣上市／上櫃的公司與 ETF

### 美國股票 (NASDAQ / NYSE)
- 輸入完整股票代碼（如 `AAPL`、`GOOGL`、`TSLA`）
- 支援所有美國上市公司
- 特殊格式：若股票包含小數點（如 `BRK.B`），系統自動轉換為 `BRK-B` 格式

### 全球主要指數
- 美國：`^GSPC` (S&P 500)、`^DJI` (道瓊工業)、`^IXIC` (那斯達克)、`^SOX` (費城半導體)
- 亞太：`^TWII` (台灣加權)、`^HSI` (恆生)、`^N225` (日經 225)、`000001.SS` (上證綜合)
- 歐洲：`^FTSE` (英國富時 100)、`^GDAXI` (德國 DAX)、`^FCHI` (法國 CAC 40)
- 特殊：`^VIX` (恐慌指數)