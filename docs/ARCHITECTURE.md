# 架構與模組說明

各模組的職責與設計決策。類別關係見 [UML.md](./UML.md)，安裝與執行見 [README](../README.md)。

---

## 資料層 (`src/data/`、`scripts/`)

**`fetcher.py`**：讀取 SQLite 的日線與名稱、yfinance 的當日分線、twstock 的台股市場別。

- 代碼依序查資料庫、twstock，都找不到就用原始輸入；資料庫會試原字串、`.TW`、`.TWO` 與點換連字號（`BRK.B` → `BRK-B`）。
- 日線以 `AdjClose / Close` 換算 OHLC，消除除權息與分割的跳空；收盤價缺值或非正數的列維持原值。

**`snapshot.py`**：`/stock` 與 API 共用的取資料流程。`load_stock` 回傳快照與兩份資料（Bot 畫圖用）；沒有日線時拋出 `NoHistoryError`，由兩邊各自轉成訊息或 404。

**`sync.py`**：兩支回補腳本共用的寫入流程。`needs_full_refresh` 在兩種情況要求重抓完整歷史：Yahoo 改寫了 `Adj Close`，或資料庫的歷史在下載區間前就中斷。必須先檢查中斷（沒有重疊日期就無從比對），且必須在寫入前呼叫（寫入會蓋掉要比對的舊值）。

**排程腳本**：`seed_stocks.py` 建立股票清單；`historical_backfill.py` 回補歷史；`daily_updater.py` 每日更新，需要重抓的交給回補腳本。

---

## 儲存層 (`src/database/`)

- 連線一律透過 `connect_db()`：外鍵檢查要每條連線各自開啟，離開區塊時也會關閉連線（sqlite3 自己的 `with` 不會關）。
- 較長或共用的 SQL 放在 `sql/*.sql`。
- 更新股票資料時不會清掉 `stocks.last_backfilled`，否則所有股票都會被當成沒回補過而全部重抓。
- 價格寫入用 `ON CONFLICT ... DO UPDATE`，不用 `INSERT OR REPLACE`，後者會刪掉舊列、改變 `id`。

---

## 分析層 (`src/quant/`)

**指標**：`compute_indicators` 是唯一入口，直接寫入 DataFrame。`MACD_z` 是 DIF 除以近 60 列標準差，讓不同價位的股票可以比較；不減平均值，因為零線本身就是趨勢基準。

**規則**：只回報偏向（-1 / 0 / +1），不知道部位，也不決定反手。

| 角色 | 規則 | 形式 |
|------|------|------|
| 趨勢 | `SMATrend`、`MACDZeroLine` | 連續值 |
| 進場 | `RSIReversal`、`StochCross`、`EMACross` | 事件 |
| 出場 | `BollingerBand`、`MACDSignalCross` | 事件 |
| 包裝 | `Decay` | 同內層 |

- 趨勢規則回傳連續值，搭配閘門的緩衝帶，價格在均線附近小幅波動時不會反覆切換。
- `CrossRule` 記住兩線上次明確分開時的上下關係，碰線後又回到原側不算交叉。`precision` 只用於以價格報價的線；MACD 會隨股價縮放，不能四捨五入。
- `Decay` 只包裝事件規則，每條規則只包一次並共用同一個實例，否則每根 K 棒會算兩次。

**策略**：子類別實作 `signal(history, position)`；能一次算完的欄位放在 `compute_indicators`。`CompositeStrategy` 把規則分成 `trend`（閘門，決定可開倉方向）、`entry`（進場時機）、`exit`（出場）三組，閘門用 `trend_enter` / `trend_exit` 兩個門檻防止來回切換。沒設定趨勢規則時兩個方向都能開倉；有設定但趨勢不明確時兩邊都不開。分組存的是規則的索引，同一條規則放在兩組，每根 K 棒仍只算一次。`gated_strategy()` 以 `SMATrend(200)` 作閘門；`voting_strategy()` 是等權投票的比較基準。

---

## 回測引擎 (`src/quant/backtest.py`)

只接收呼叫端準備好的 DataFrame。每天依序：

1. 前一天收盤的訊號，今天開盤成交。
2. 檢查盤中停損；跳空越過停損價時以開盤價成交。
3. 以收盤價記錄權益。
4. 依今天收盤產生明天的訊號。

- 策略拿到的歷史最多到當天，結構上看不到未來；但可以往回看到 `start` 之前，暖身資料不佔用回測區間。
- 帳戶是現金加最多一筆整股部位，可做多或做空；零頭留在現金，連一股都買不起就不成交。所有 `profit_and_loss` 加總剛好等於最終權益減初始資金。
- 回測區間只在 `PERIOD_DAYS` 定義，Bot 從中挑選選項。

---

## 前端

Bot、API 與終端工具都是同一套服務之上的前端，彼此不互相依賴。

**Discord Bot (`src/bot/`)**：會阻塞的操作都用 `asyncio.to_thread` 放到執行緒，互不相依的用 `asyncio.gather` 並行。`/stock` 只有日線為空才算失敗；沒有盤中資料時，分時按鈕停用。訊息 5 分鐘後清除。

**HTTP API (`src/api/`)**：

| 狀態碼 | 情境 |
|--------|------|
| `404` | 查不到日線（`NoHistoryError`） |
| `422` | 資料太短（`InsufficientDataError`） |
| `500` | 其他例外；原因只寫進日誌 |

- `HTTPException` 只在 `except` 裡拋出；若在 `try` 裡拋，要先加 `except HTTPException: raise`，否則會變成 500。
- 回應模型用 `model_validate(obj)` 依屬性讀值，`@property` 的 `change_percent` 才會帶出。只回傳數值，格式交給前端。
- 每個路由保留 `response_model`，前端型別從 `/openapi.json` 產生。路由都在 `/api` 底下，前端只需一條代理規則。

**終端工具 (`src/cli/`)**：由 `backtest.py`、`database.py` 的 `__main__` 啟動；`console.py` 提供 `rich` 輸出與單鍵選單。

**圖表與報表 (`src/utils/`)**：

- `visualizer.py`：PNG 圖表。均線先用完整歷史計算再切片，否則圖表開頭的均線是錯的；盤中圖以前收為基準、紅漲綠跌。
- `html_page.py`：HTML 頁面、表格與跳脫。呼叫端只傳純文字，`body` 只接受 `html_table` 的輸出；檔名會過濾，輸出一定在 `exports/`。
- `reports.py`：回測與價格報表，以及終端共用的漲跌判斷。引擎與資料庫層不含顯示程式。

---

## 測試

完全離線：記憶體 SQLite 與合成 OHLCV，不連 yfinance，也不讀本機資料庫。涵蓋回測成交與停損、防止看到未來資料、規則與組合策略、資料同步、資料庫連線、代碼正規化、報表跳脫與終端選單。執行方式見 [README](../README.md#測試)。
