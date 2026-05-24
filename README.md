# 📈 Discord Stock Bot

![Python Version](https://img.shields.io/badge/python-3.13%2B-blue)
![Managed by uv](https://img.shields.io/badge/managed%20by-uv-purple)
![License](https://img.shields.io/badge/license-MIT-green)

在 Discord 中實時查詢股票資訊和技術分析

<div>
  
  [![邀請機器人](https://img.shields.io/badge/邀請機器人到伺服器-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1494994206425612399)
  
  <img src="./docs/image.png" width="500" alt="圖表頁面">
</div>

## 功能特性

- **多市場支持**：支援台灣股票（台股）和美國股票（美股）
- **實時股票數據**：通過 Yahoo Finance 獲取最新股票報價
- **技術分析**：
  - RSI（相對強度指數）
  - 移動平均線（MA5、MA10、MA20）
  - 日內和歷史走勢分析
- **專業圖表**：生成 K 線圖配合技術指標
- **Discord 整合**：無縫集成到 Discord 伺服器，直接在聊天中查詢
- **非同步處理**：快速響應，不阻塞機器人操作

## 專案結構

```
stock-bot/
├── src/
│   ├── dc_bot.py          # Discord 機器人主程式
│   ├── dc_bot_view.py     # Discord UI 元件（按鈕、選單等）
│   ├── main.py            # 本地測試和開發入口
│   ├── core/              # 核心功能模塊
│   │   ├── __init__.py
│   │   ├── fetcher.py     # 股票數據獲取
│   │   ├── analyzer.py    # 技術分析引擎
│   │   └── visualizer.py  # 圖表生成
│   └── models/            # 數據模型
│       ├── __init__.py
│       └── stock.py       # 股票數據模型
├── docs/                  # 文檔和資源
│   └── image.png         # 演示圖片
├── pyproject.toml        # 項目配置
├── README.md             # 本檔案
└── .env                  # 環境變數（需自行建立）
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

## 安全性考慮

- 使用 `.env` 檔案管理敏感信息（Token、伺服器 ID）
- 確保不將 `.env` 檔案提交到版本控制系統
- 定期更新依賴包以修補安全漏洞

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