# 架構與模組說明

說明各模組的職責、重要的設計決策，以及指令的資料流。類別關係請見 [UML.md](./UML.md)，安裝與執行請見 [README](../README.md)。

---

## 資料層

### `StockDataFetcher` (`src/data/fetcher.py`)

整合三個資料來源：SQLite 的歷史日線與股票名稱、yfinance 的當日 1 分鐘資料，以及 twstock 的台股市場別對照。

`_format_ticker` 先把輸入轉成大寫，再依序查資料庫、twstock，都找不到就用原始輸入。查資料庫時會同時試原字串、加 `.TW`、加 `.TWO`，以及把點號換成連字號（`BRK.B` → `BRK-B`）。

`fetch_historical_data` 以 `AdjClose / Close` 的比例換算 OHLC，消除除權息與分割造成的跳空。收盤價缺值或不是正數的列沒有可用的比例，整列維持原值，以免只調整收盤價而跑到當日高低價之外。

### `sync.py` (`src/data/sync.py`)

負責把 yfinance 下載的資料批次寫入 SQLite，兩支回補腳本共用。

`needs_full_refresh` 判斷一檔股票是否需要重抓完整歷史，有兩種情況：Yahoo 因除息或分割改寫了 `Adj Close`，或資料庫裡的歷史在下載區間之前就中斷了。必須先檢查中斷，因為兩邊沒有重疊的日期時，無法比對 `Adj Close`。這個函式也必須在寫入前呼叫，否則要比對的舊值已經被覆蓋。

### 排程腳本 (`scripts/`)

- `seed_stocks.py`：建立或更新台股、美股與全球指數清單。
- `historical_backfill.py`：回補歷史 K 線，`force=True` 會全部重補。
- `daily_updater.py`：每日更新行情，需要重抓的股票交給 `historical_backfill.py`。

---

## 儲存層

### `database.py` + `sql/` (`src/database/`)

封裝 SQLite CRUD，較長或多處共用的 SQL 放在 `sql/*.sql`。所有連線都要透過 `connect_db()` 建立，因為外鍵檢查（`PRAGMA foreign_keys = ON`）必須每條連線各自開啟。

`connect_db()` 是 context manager，離開區塊時會結束交易並關閉連線。sqlite3 連線本身的 `with` 只會 commit 或 rollback，不會關閉連線。

資料表的重要約束：

- `stocks.last_backfilled` 記錄最後一次成功回補的時間，更新股票資料時不會清掉它。
- `daily_prices` 的 `UNIQUE(ticker, date)` 保證每檔股票每天只有一列，寫入時以此判斷衝突。
- 價格寫入用 `ON CONFLICT ... DO UPDATE` 而不是 `INSERT OR REPLACE`，因為後者會先刪除舊列，原本的 `id` 會跟著改變。

---

## 分析層

### 指標 (`src/quant/indicator.py`)

`compute_indicators(ticker, data, columns)` 是唯一入口，直接把指定指標寫入 DataFrame；`columns=None` 代表計算全部。

`MACD_z` 是 DIF 除以它自己近 60 列的標準差，讓不同股價的股票可以互相比較。計算時不減去平均值，因為零線本身就是有意義的趨勢基準。

### 規則 (`src/quant/rule.py`)

規則只回報目前偏向哪一邊：-1 偏空、+1 偏多、0 沒有意見。規則不知道目前的部位，也不決定是否反手。每條規則宣告 `name`、`required_columns`、`warmup` 與 `lookback`，跨 K 棒累積的狀態在 `reset()` 中清除。

| 角色 | 規則 | 形式 | 用途 |
|------|------|------|------|
| 趨勢 | `SMATrend`、`MACDZeroLine` | 連續值 | 判斷趨勢方向與強度 |
| 進場 | `RSIReversal`、`StochCross`、`EMACross` | 事件 | 決定進場時機 |
| 出場 | `BollingerBand`、`MACDSignalCross` | 事件 | 提供出場理由 |
| 包裝 | `Decay` | 同內層 | 讓事件訊號逐漸減弱 |

趨勢規則回傳連續值而不是只有多空兩種，搭配組合策略在零附近設的緩衝帶，價格在均線附近小幅波動時，閘門才不會反覆切換。

`CrossRule` 用 `_CrossTracker` 記住兩條線上次明確分開時誰在上面，因此兩線碰在一起後又回到原本那一側，不會被誤判成交叉。`precision` 只適用於以價格跳動單位報價的線；MACD 線會隨股價縮放，不應四捨五入。

`Decay(rule, half_life, floor)` 只用來包裝事件規則，不要包裝會持續表態的規則（例如 RSI 超賣）。內層規則沒有發聲的每根 K 棒，保留的意見乘以 `0.5 ** (1 / half_life)`，低於 `floor` 就歸零，以免微弱的殘留訊號出現在報表的理由中。每條規則只包裝一次，並共用同一個包裝實例，否則內層規則每根 K 棒會被計算兩次。

### 策略 (`src/quant/strategy.py`)

`Strategy` 宣告需要的指標、暖身列數與可見歷史長度，子類別實作 `signal(history, position)`。能用欄位一次算完的指標放在 `compute_indicators`，策略只處理需要逐根 K 棒或依部位判斷的邏輯。

`CompositeStrategy` 把規則分成三組：

| 分組 | 作用 |
|------|------|
| `trend` | 閘門：決定可以開倉的方向，另一個方向一律擋下 |
| `entry` | 觸發：決定何時進場 |
| `exit` | 出場：分數偏向持倉的反方向時離場 |

閘門用 `trend_enter` / `trend_exit` 兩個門檻切換，分數在兩者之間時維持原狀；進出場則分別看 `entry_threshold` / `exit_threshold`。沒有設定趨勢規則時，兩個方向都可以開倉；有設定但趨勢還不明確時，兩個方向都不開。分組裡存的是規則的索引而不是規則本身，所以同一條規則放在兩組，每根 K 棒仍只計算一次。

`gated_strategy()` 以 `SMATrend(200)` 作閘門，用 RSI、KD、EMA 事件觸發進場；`voting_strategy()` 是等權投票，作為比較基準。

---

## 回測與模型

### `BacktestEngine` (`src/quant/backtest.py`)

引擎只接收呼叫端準備好的 DataFrame，不直接讀取資料來源。每天的處理順序：

1. 前一天收盤產生的訊號，在今天開盤成交。
2. 檢查盤中停損；跳空越過停損價時以開盤價成交。
3. 以今天收盤價記錄權益。
4. 依今天收盤產生下一個交易日的訊號。

`run()` 先計算策略需要的指標、移除無效列，再從 `start` 切出回測區間。策略拿到的 `history_window` 最多只到當天，所以不可能看到未來的資料；但可以往回看到 `start` 之前的資料。暖身所需的額外資料由 `required_history_days(period_days)` 計算，不佔用指定區間；資料不足時拋出 `InsufficientDataError`。

帳戶由現金和最多一筆整股部位組成，可做多或做空。零頭留在現金裡，連一股都買不起就不成交。權益以 `cash ± shares × price` 計算，所有 `Trade.profit_and_loss` 加總後剛好等於最終權益減去初始資金。回測區間只在 `PERIOD_DAYS` 定義，Discord 指令從中挑選部分選項。

### 模型 (`src/models/`)

- `Signal`：交易動作、觸發條件與當時的指標值；`conditions` 的鍵是顯示在報表上的文字。
- `Position`：目前持倉的進場日期、價格、方向、股數與進場訊號。
- `Trade`：一筆完整的進出場，包含損益與報酬率。
- `BacktestResult`：交易清單、權益曲線，以及總報酬率、勝率、最大回撤等統計。

---

## 呈現層

### 圖表與報表

`visualizer.py` 以 `Agg` backend 產生日線、盤中與回測的 PNG。均線先用完整歷史計算再切片；盤中圖以前一日收盤為基準，紅漲綠跌，與台股慣例相同。

`html_report.py` 提供共用的 HTML 頁面、表格與數字格式化。表頭、儲存格、標題與副標題的 HTML 跳脫都由這一層處理，呼叫端只傳純文字；`body` 只接受 `html_table` 產生的內容。`write_report` 會過濾檔名，確保輸出一定留在 `exports/` 裡。

### 終端互動工具 (`src/cli/`)

互動式回測與資料庫工具，由 `src/quant/backtest.py`、`src/database/database.py` 的 `__main__` 啟動。`console.py` 提供共用的 `rich` 輸出與單鍵選單。

### `dc_bot_view.py` (`src/bot/dc_bot_view.py`)

`build_snapshot` 整理歷史與盤中資料，算出 Embed 需要的 RSI 與前一日收盤；有盤中資料時現價取最後一筆，否則取最後收盤價。`ChartToggleView` 負責切換日線圖與分時圖，5 分鐘後清除訊息。`send_*` 函式負責組合 Embed 與圖表附件。

---

## Discord 指令資料流

會阻塞的操作（SQLite、yfinance、指標計算與繪圖）都透過 `asyncio.to_thread` 放到執行緒，互不相依的工作用 `asyncio.gather` 同時執行。

### `/stock`

```
輸入 ticker
  → StockDataFetcher 正規化代碼
  → 並行取得歷史與盤中資料
  → build_snapshot 組合價格、RSI 與前收
  → 並行產生日線與分時圖
  → send_stock_response 回覆 Embed
```

只有歷史資料為空才算查詢失敗；沒有盤中資料時仍會回覆日線與指標，只是分時切換按鈕會停用。

### `/backtest`

```
輸入 ticker、strategy、period
  → 從 PERIOD_DAYS 取得區間長度
  → 額外取得指標暖身資料
  → BacktestEngine.run(ticker, data, start)
  → 產生回測圖並回覆績效 Embed
```

資料不足時，直接把 `InsufficientDataError` 的訊息回覆給使用者。

---

## HTTP API (`src/api/`)

`main.py` 建立應用程式並加上 CORS 與路由，`routes.py` 定義端點，`schemas.py` 定義回應模型。底下使用的服務和 Discord 指令相同。

| 狀態碼 | 情境 |
|--------|------|
| `404` | 查不到歷史資料 |
| `422` | `InsufficientDataError`：代碼存在，但歷史資料太短 |
| `500` | 其他例外；原因只寫進日誌，以免洩漏內部路徑 |

`except HTTPException` 必須放在 `except Exception` 前面，否則前面拋出的 404 會被攔下，變成 500。

回應模型設定了 `from_attributes=True`，用 `model_validate(obj)` 依屬性讀值，這樣 `@property` 的 `change_percent` 也會被帶出；直接回傳 dataclass 會漏掉它。回應只提供數值，不含 `change_str` 這類格式化字串，顯示格式由前端決定。

每個路由都保留 `response_model`，即使函式已經回傳模型，因為 `/openapi.json` 靠它產生，前端型別又是從這份規格產生的。所有路由都在 `/api` 底下，與 FastAPI 自己的 `/docs`、`/openapi.json` 分開，前端只要設定一條代理規則；透過代理時瀏覽器視為同源，不需要 CORS。

### `GET /api/stock/{ticker}`

```
輸入 ticker
  → StockDataFetcher 正規化代碼
  → 並行取得歷史與盤中資料
  → build_snapshot 組合價格、RSI 與前收
  → SnapshotResponse.model_validate 轉為 JSON
```

---

## 測試

測試完全離線：使用記憶體內的 SQLite 與合成的 OHLCV，不連線 yfinance，也不讀取本機資料庫。涵蓋範圍：

- 回測：隔日開盤成交、反手、停損、整股部位與權益曲線。
- 指標暖身、歷史視窗、防止看到未來資料，以及策略狀態重設。
- 規則：方向判斷、交叉事件、意見衰減，以及宣告的欄位與暖身是否正確。
- 組合策略：閘門否決、門檻切換、進出場門檻、跨組計算與預設組合。
- 資料同步：歷史中斷、`Adj Close` 改寫與回補時間戳。
- 資料庫連線：commit 與 rollback、離開後關閉、外鍵生效。
- 代碼正規化、OHLC 調整、報表跳脫與匯出檔名安全。
- 終端工具：單鍵選單的選項格式與重問、價格漲跌判斷、資料落後的交易日數。

執行方式請見 [README](../README.md#測試)。