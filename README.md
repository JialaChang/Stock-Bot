# 📈 Stock Bot

![Python Version](https://img.shields.io/badge/python-3.13%2B-blue)
![Managed by uv](https://img.shields.io/badge/managed%20by-uv-purple)
![License](https://img.shields.io/badge/license-MIT-green)

基於模組化架構的台美股量化分析系統，結合自動化歷史數據管線，並提供 Discord 實時互動介面。

<div>
  
  [![邀請機器人](https://img.shields.io/badge/邀請機器人到伺服器-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1494994206425612399)
  
  <img src="./docs/image.png" width="500" alt="圖表頁面">
</div>

## 功能特性

- **穩健的數據管線 (Data Pipeline)**：內建智慧型斷點續傳機制，自動抓取並清洗 Yahoo Finance 歷史與盤中報價，完美處理上市櫃後綴與時區差異。
- **本地端高效儲存**：採用 SQLite 建構輕量且高效的歷史價格庫，降低 API 依賴並大幅提升回測與圖表渲染速度。
- **業務邏輯分離 (Separation of Concerns)**：將爬蟲獲取、技術指標運算 (MA, RSI) 與 Discord 介面徹底解耦，極大化程式碼可讀性與擴充彈性。
- **動態視覺化引擎**：基於 Matplotlib 封裝的高解析度繪圖模組，自動疊加 K 線圖、均線與買賣量能。
- **非同步事件驅動**：Discord 表現層採用全非同步處理，確保多使用者同時查詢時不阻塞系統核心運作。

## 專案結構

```
stock-bot/
├── src/                     # 系統核心程式碼
│   ├── bot/                 # 表現層 (Presentation Layer)：負責與外部服務及使用者互動
│   │   ├── dc_bot.py        # Discord 機器人主程式與事件監聽
│   │   └── dc_bot_view.py   # Discord 互動介面 (UI 元件與按鈕邏輯)
│   │
│   ├── data/                # 數據層 (Data Layer)：負責外部 API 串接與原始資料獲取
│   │   └── fetcher.py       # 歷史報價與盤中資料抓取模組 (如 yfinance 封裝)
│   │
│   ├── quant/               # 業務邏輯層 (Business Logic Layer)：量化分析與運算核心
│   │   ├── analyzer.py      # 行情分析模組 (負責統整資料並呼叫指標計算)
│   │   └── indicators.py    # 獨立的技術指標公式庫 (如 MA, RSI, MACD 計算)
│   │
│   ├── database/            # 儲存層 (Data Access Layer)：資料庫連線與操作
│   │   └── database.py      # SQLite 連線管理與 SQL 查詢語法封裝
│   │
│   ├── models/              # 資料模型 (Data Models)：定義系統共用的資料結構
│   │   └── stock.py         # 股票與價格的物件實體定義 (Data Class/Pydantic)
│   │
│   └── utils/               # 工具模組 (Utilities)：跨層級共用的輔助功能
│       └── visualizer.py    # 圖表繪製與視覺化輸出模組 (Matplotlib)
│
├── scripts/                    # 自動化任務腳本：獨立於主程式運作的批次作業
│   ├── seed_stocks.py          # 建立與初始化股票、指數基本名單
│   ├── historical_backfill.py  # 批次下載與回補歷史 K 線資料
│   └── daily_updater.py        # 每日盤後股價更新與維護作業
│
├── docs/                    # 專案文件與靜態資源
│   └── image.png            # 系統運作展示或架構說明圖
│
├── pyproject.toml           # 專案依賴套件與環境設定檔
├── README.md                # 專案主說明文件
├── main.py                  # 系統主進入點 (Entry Point)：負責初始化服務並啟動機器人
└── .env                     # 環境變數設定檔 (存放 Token 等敏感機密，不加入版本控制)
```

## 模塊說明

### StockDataFetcher (`core/fetcher.py`)
負責從數據源獲取股票數據：
- 自動處理股票代碼後綴（台股無需添加 `.TW`）
- 獲取歷史數據和日內數據
- 獲取股票名稱和最新交易時間

### TechnicalAnalyzer (`core/analyzer.py`)
執行技術分析：
- 計算 RSI（相對強度指數）
- 計算移動平均線（5、10、20 日期）
- 計算漲跌幅百分比
- 返回 StockSnapshot 數據模型

### StockVisualizer (`core/visualizer.py`)
生成專業股票圖表：
- K 線圖
- 移動平均線疊加
- 交易量視覺化
- 輸出為 PNG 格式

## 支援的股票市場

### 台灣股票 (Taiwan Stock Exchange)
- 輸入股票代碼即可（如 `2330`）
- 機器人自動添加 `.TW` 後綴
- 支援所有在台股上市的公司

### 美國股票 (NASDAQ / NYSE)
- 輸入完整股票代碼（如 `AAPL`、`GOOGL`）
- 支援所有美國上市公司

### 其他市場
- 輸入完整後綴（如 `0001.HK` 用於香港股票）