# Stock Bot

![Python Version](https://img.shields.io/badge/python-3.13%2B-blue)
![Managed by uv](https://img.shields.io/badge/managed%20by-uv-purple)
![License](https://img.shields.io/badge/license-MIT-green)

Discord 股票查詢機器人，支援台股、美股與全球主要指數，提供技術分析指標（RSI、MA）與 K 線圖  
希望未來能擴充成兼具指標與技術分析，並套用機器學習的量化交易專案  

<div>
  <a href="https://discord.com/oauth2/authorize?client_id=1494994206425612399">
    <img src="https://img.shields.io/badge/邀請機器人到伺服器-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="邀請機器人">
  </a>

  <img src="./docs/image.png" width="300" alt="圖表頁面">
</div>

---

## 技術架構

```
stock-bot/
├── src/
│   ├── bot/          # Presentation：Discord 斜線指令 & UI 元件
│   ├── data/         # Data Access：SQLite 查詢 & yfinance 下載
│   ├── quant/        # Business Logic：RSI、MA 指標計算
│   ├── database/     # SQLite schema 初始化與 CRUD
│   ├── models/       # 共用資料類別（StockSnapshot）
│   └── utils/        # 圖表生成（mplfinance / matplotlib）
├── scripts/
│   ├── seed_stocks.py           # 匯入台美股與全球指數基本清單
│   ├── historical_backfill.py   # 批次回補歷史 K 線至資料庫
│   └── daily_updater.py         # 每日盤後自動更新股價
└── main.py           # 啟動入口
```

### Discord `/stock` 指令資料流

```
使用者輸入 ticker
    → StockDataFetcher._format_ticker()   # 補齊 .TW / .TWO 後綴
    → asyncio.gather()                    # 並發：SQLite 歷史資料 + yfinance 盤中資料
    → compute_indicators()                  # 計算 RSI(14)、MA5/10/20、漲跌幅
    → asyncio.gather()                    # 並發：生成歷史 K 線圖 + 盤中分時圖
    → DiscordStockChart View              # 回傳 Embed + 可切換按鈕（5 分鐘逾時）
```

---

## 快速開始

### 環境需求

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 套件管理器

### 安裝

```bash
# 安裝依賴
uv sync

# 建立 .env（參考下方欄位說明）
cp .env.example .env
```

`.env` 變數欄位：

| 變數 | 說明 |
|------|------|
| `DISCORD_TOKEN` | Discord Bot Token（從 [Discord Developer Portal](https://discord.com/developers/applications) 取得） |
| `GUILD` | （選填）測試伺服器 ID，設定後斜線指令立即生效，省去全域同步的 1 小時等待 |

### 初始化資料庫

首次執行或新增股票時需執行：

```bash
python scripts/seed_stocks.py          # 寫入股票基本清單
python scripts/historical_backfill.py  # 回補歷史 K 線（需一段時間）
```

### 啟動機器人

```bash
python main.py
```

### 每日更新（建議使用工具排程）

```bash
python scripts/daily_updater.py
```

---

## Discord 指令說明

| 指令 | 說明 |
|------|------|
| `/stock <ticker>` | 查詢股票資訊、技術指標與 K 線圖 |

輸入格式範例：

| 輸入 | 自動解析為 | 說明 |
|------|-----------|------|
| `2330` | `2330.TW` | 台積電（台股上市） |
| `6488` | `6488.TWO` | 環球晶（台股上櫃） |
| `AAPL` | `AAPL` | 蘋果（美股） |
| `BRK.B` | `BRK-B` | 波克夏 B 股（Yahoo Finance 格式轉換） |
| `^GSPC` | `^GSPC` | S&P 500 指數 |

---

## 支援市場

### 台灣股票

- **上市（TSE）**：輸入純代碼，自動補齊 `.TW`
- **上櫃（TPEX）**：輸入純代碼，自動補齊 `.TWO`

### 美國股票

- 直接輸入代碼（`AAPL`、`TSLA`、`NVDA` 等）
- 含小數點代碼（如 `BRK.B`）自動轉換為 Yahoo Finance 格式 `BRK-B`

### 全球主要指數

| 代碼 | 指數 |
|------|------|
| `^GSPC` | S&P 500 |
| `^DJI` | 道瓊工業 |
| `^IXIC` | 那斯達克 |
| `^SOX` | 費城半導體 |
| `^TWII` | 台灣加權 |
| `^HSI` | 恆生 |
| `^N225` | 日經 225 |
| `000001.SS` | 上證綜合 |
| `^FTSE` | 英國富時 100 |
| `^GDAXI` | 德國 DAX |
| `^VIX` | 恐慌指數 |

---

## 資料庫結構

```sql
-- 股票基本資料
stocks (
    ticker  TEXT PRIMARY KEY,
    name    TEXT,
    market  TEXT
)

-- 歷史日線（OHLCV）
daily_prices (
    id                  INTEGER PRIMARY KEY,
    ticker              TEXT REFERENCES stocks(ticker),
    date                TEXT,
    open_price          REAL,
    high_price          REAL,
    low_price           REAL,
    close_price         REAL,
    adjust_close_price  REAL,  -- 除權息調整後收盤價
    volume              REAL,
    UNIQUE(ticker, date)
)
```

> **除權息調整**：查詢歷史資料時，系統以 `AdjClose / Close` 的比率回推開高低價，消除配息或股票分割造成的圖表跳空缺口。

---

## 模組說明

### `StockDataFetcher` (`src/data/fetcher.py`)

整合三個資料源的查詢門面：
- **SQLite**：歷史日線、股票名稱（本地快取）
- **yfinance**：當日 1 分鐘盤中資料
- **twstock**：台股代碼與市場別對照（上市 / 上櫃）

### `compute_indicators` (`src/quant/indicator.py`)

計算技術指標並封裝至 `StockSnapshot`：
- **RSI(14)**：相對強弱指標，>70 超買，<30 超賣
- **MA5 / MA10 / MA20**：簡單移動平均線
- **漲跌幅**：以前一交易日收盤價為基準（而非歷史陣列的前一筆）

### `generate_history_chart` / `generate_intraday_chart` (`src/utils/visualizer.py`)

生成 in-memory PNG 圖表：
- **歷史日線圖**：K 線 + MA5/10/20 + 成交量
- **盤中分時圖**：相對開盤價紅漲綠跌分色折線

### `DiscordStockChart` (`src/bot/dc_bot_view.py`)

持有圖表 bytes 的 Discord `View` 元件，提供按鈕切換日線圖 / 分時圖，逾時 5 分鐘自動清理。