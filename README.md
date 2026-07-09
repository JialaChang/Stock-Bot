# Stock Bot

![Python Version](https://img.shields.io/badge/python-3.13%2B-blue)
![Managed by uv](https://img.shields.io/badge/managed%20by-uv-purple)
![License](https://img.shields.io/badge/license-MIT-green)

量化交易回測框架，用於驗證和評估股票交易策略。支援**雙向交易**（做多/做空）、**自訂策略**開發、**止損機制**與完整的績效評估指標（報酬率、勝率、最大回撤）。

核心特性：
- **累積倍率資產追蹤**：避免複利計算誤差，精確模擬資金曲線
- **策略與引擎解耦**：輕鬆開發新策略，無需修改回測邏輯
- **完整交易紀錄**：每筆交易的進出場時機、價格、信號條件、損益明細

附贈 **Discord 查詢機器人**，快速查看股票技術指標、K 線圖與市場數據（支援台股、美股、全球指數）  

<div>
  
  [![邀請機器人](https://img.shields.io/badge/邀請機器人到伺服器-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1494994206425612399)
  
  <img src="./docs/image.png" width="300" alt="圖表頁面">
</div>

---

## 技術架構

```
stock-bot/
├── src/
│   ├── bot/          # Discord 斜線指令 & UI 元件
│   ├── data/         # 股票資料查詢與下載
│   ├── quant/        # 技術指標計算 & 回測引擎
│   ├── database/     # 資料庫初始化與 CRUD
│   ├── models/       # 共用資料類別
│   └── utils/        # 圖表生成
├── scripts/
│   ├── seed_stocks.py           # 匯入台美股與全球指數基本清單
│   ├── historical_backfill.py   # 回補歷史 K 線至資料庫
│   └── daily_updater.py         # 更新每日數據至資料庫
└── main.py           # 啟動入口
```

完整類別關聯與方法簽章請見 [docs/UML.md](./docs/UML.md)

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

```bash
python scripts/seed_stocks.py          # 寫入股票基本清單
python scripts/historical_backfill.py  # 回補歷史 K 線（需一段時間）
```

### 每日更新資料庫（建議使用工具排程）

```bash
python scripts/daily_updater.py
```

### 啟動 Discord 機器人

```bash
python src/bot/dc_bot.py
```

### 執行回測

```bash
python src/quant/backtest.py
```

### 操作資料庫

```bash
python src/database/database.py
```

---

## Discord 指令說明

| 指令 | 說明 |
|------|------|
| `/stock <ticker>` | 查詢股票資訊、技術指標與 K 線圖 |
| `/backtest <ticker> <strategy> <period>` | 對指定股票執行策略回測，回傳績效指標與圖表（K 線 + 進出場標記 + 權益曲線） |

輸入格式範例：

| 輸入 | 自動解析為 | 說明 |
|------|-----------|------|
| `2330` | `2330.TW` | 台積電（台股上市） |
| `6488` | `6488.TWO` | 環球晶（台股上櫃） |
| `AAPL` | `AAPL` | 蘋果（美股） |
| `BRK.B` | `BRK-B` | 波克夏 B 股（Yahoo Finance 格式轉換） |
| `^GSPC` | `^GSPC` | S&P 500 指數 |

### Discord `/stock` 指令資料流

```
使用者輸入 ticker
    → StockDataFetcher._format_ticker()   # 補齊 .TW / .TWO 後綴
    → asyncio.gather()                    # 並發：SQLite 歷史資料 + yfinance 盤中資料
    → compute_indicators_for_discord()    # 計算 RSI(14)、MA5/10/20、漲跌幅，回傳 StockSnapshot
    → asyncio.gather()                    # 並發：生成歷史 K 線圖 + 盤中分時圖
    → send_stock_response()               # 組裝 Embed 並送出
    → DiscordStockChart View              # 回傳 Embed + 可切換按鈕（5 分鐘逾時）
```

### Discord `/backtest` 指令資料流

```
使用者輸入 ticker、strategy、period
    → StockDataFetcher.fetch_historical_data(period)  # 取得歷史 OHLCV
    → BacktestEngine.run(ticker, data)                # 依策略逐日回測，回傳 BacktestResult
    → generate_backtest_chart()                       # 繪製 K 線 + 進出場標記 + 權益曲線
    → send_backtest_response()                        # 組裝績效指標 Embed 並附圖送出
```

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
| `^VIX` | 恐慌指數 |

---

## 模組說明

### `StockDataFetcher` (`src/data/fetcher.py`)

整合三個資料源的查詢門面：
- **SQLite**：歷史日線、股票名稱（本地快取）
- **yfinance**：當日 1 分鐘盤中資料
- **twstock**：台股代碼與市場別對照（上市 / 上櫃）

### `compute_indicators` / `compute_indicators_for_discord` (`src/quant/indicator.py`)

兩個函式刻意分離，對應不同的使用情境：

| 函式 | 用途 | 回傳 |
|------|------|------|
| `compute_indicators(ticker, data, columns)` | 量化回測：依 `columns` 清單按需計算指標並原地寫入 DataFrame；`columns=None` 代表計算全套 | `None` |
| `compute_indicators_for_discord()` | Discord 展示：計算 Embed 所需的指標，整合盤中現價與漲跌幅，回傳資料載體 | `StockSnapshot` |

### `generate_history_chart` / `generate_intraday_chart` / `generate_backtest_chart` (`src/utils/visualizer.py`)

生成 in-memory PNG 圖表：
- **歷史日線圖**：K 線 + MA5/10/20 + 成交量
- **盤中分時圖**：相對開盤價紅漲綠跌分色折線
- **回測結果圖**：K 線 + 多空進出場標記 + 權益曲線

### `DiscordStockChart` (`src/bot/dc_bot_view.py`)

持有圖表 bytes 的 Discord `View` 元件，提供按鈕切換日線圖 / 分時圖，逾時 5 分鐘自動清理。

### `send_stock_response` / `send_backtest_response` (`src/bot/dc_bot_view.py`)

組裝並送出 Discord Embed：
- `send_stock_response`：股票資訊 Embed + 可切換圖表 View
- `send_backtest_response`：回測績效指標（總報酬率／勝率／最大回撤／交易次數）Embed + 回測圖表

### `BacktestEngine` (`src/quant/backtest.py`)

逐日迭代歷史 OHLCV 資料的回測引擎：
- 初始化時接收一個 `Strategy` 實例，引擎與策略邏輯完全解耦
- 讀取策略的 `required_columns`，只計算必要指標，`dropna` 也只針對這些欄位（避免因其他指標的 warm-up 期丟掉多餘資料）
- 以 **pending signal** 模式逐根 K 棒執行策略
- 支援做多與做空：透過 `cumulative_multiplier` 追蹤累積收益倍率，避免複利誤差
- 回測結束若仍有未平倉部位，以最後一日收盤價強制平倉並計入交易紀錄
- 回傳 `BacktestResult`，包含交易明細、資產曲線、總報酬率、勝率、最大回撤

```
每日迴圈：
  1. 執行昨日收盤產生的 pending signal → 今日開盤價成交
  2. 盤中止損檢查（同日即時執行，不走 pending）：成交價 = 止損價，若開盤已跳空則以開盤價成交
  3. 今日收盤估算浮動損益，記錄 equity
  4. Strategy.signal() 依今日收盤指標產生訊號（作為明日 pending）

回測結束：未平倉部位 → 最後一日收盤強制平倉
```

### `Strategy` (`src/quant/strategy.py`)

| 類別 | `required_columns` | 說明 |
|------|--------------------|------|
| `Strategy` | `[]`（抽象預設） | 抽象基底類別，子類別必須實作 `signal()`，並宣告 `required_columns` 告知引擎所需指標 |
| `RSIStrategy` | `["RSI"]` | RSI 超買/ 超賣策略 |
| `EMAStrategy` | `["EMA_5", "EMA_20"]` | EMA5/20 黃金交叉、死亡交叉策略 |

### `Signal` / `Position` / `Trade` / `BacktestResult` (`src/models/trade.py`)

| 類別 | 說明 |
|------|------|
| `Signal` | 策略訊號載體：`action`（ENTER_LONG / EXIT_LONG / ENTER_SHORT / EXIT_SHORT / HOLD）、`conditions`（各子條件是否成立）、`values`（觸發時的指標快照） |
| `Position` | 持倉中的進場快照：進場日期、價格、進場 Signal、倉位方向（LONG/SHORT），供引擎計算浮動損益與建立 Trade；方法 `unrealized_pnl_ratio()` 回傳當前浮動損益倍率 |
| `Trade` | 單筆交易紀錄：進出場日期、價格、股數、倉位方向、進出場訊號，計算屬性含 `profit_and_loss`、`return_on_investment`、`is_profit` |
| `BacktestResult` | 回測彙總：持有 `trades` 列表、`equity_curve` 與原始 `data`（OHLCV），計算屬性含 `total_return`、`win_rate`、`max_drawdown`、`trade_count` |