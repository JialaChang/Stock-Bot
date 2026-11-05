# 模組相依關係

依目錄分成 7 張圖，呈現類別與模組之間的相依方向。行為說明請見 [ARCHITECTURE.md](./ARCHITECTURE.md)。

出現在其他圖的類別標為 `<<見「X」圖>>`，只畫出關聯線。

## 1. 資料模型 (`src/models/`)

```mermaid
classDiagram
    direction TB

    class StockSnapshot {
        <<Data Transfer Object>>
        +str ticker
        +str name
        +float current_price
        +float previous_close
        +float_or_None rsi_value
        +datetime latest_time
        +float change_percent
        +str change_str
        +str rsi_str
        +str latest_time_str
    }

    class Signal {
        <<Data Transfer Object>>
        +Literal action
        +dict~str_bool~ conditions
        +dict~str_float~ values
    }

    class Position {
        <<Data Transfer Object>>
        +date entry_date
        +float entry_price
        +Signal entry_signal
        +Literal side
        +int shares
    }

    class Trade {
        <<Data Transfer Object>>
        +str ticker
        +date entry_date
        +float entry_price
        +date exit_date
        +float exit_price
        +Signal entry_signal
        +Signal exit_signal
        +Literal side
        +int shares
        +float profit_and_loss
        +float return_on_investment
        +bool is_profit
    }

    class BacktestResult {
        <<Data Transfer Object>>
        +str ticker
        +list~Trade~ trades
        +Series equity_curve
        +DataFrame data
        +float total_return
        +float win_rate
        +float max_drawdown
        +int trade_count
    }

    Trade --> Signal : 包含 entry/exit
    Position --> Signal : 包含 entry
    BacktestResult --> Trade : 包含 list
```

## 2. 規則層 (`src/quant/rule.py`)

規則只回報偏向哪一邊，不知道目前的部位；`CompositeStrategy` 依角色把規則分組。

```mermaid
classDiagram
    direction TB

    class Rule {
        <<Abstract>>
        +str name
        +list~str~ required_columns
        +int warmup
        +int_or_None lookback
        +reset() None
        +bias(history) float
    }

    class CrossRule {
        <<Abstract>>
        +str fast_column
        +str slow_column
        +int_or_None precision
        +reset() None
    }

    class _CrossTracker {
        +reset() None
        +seed(fast, slow) None
        +update(fast, slow) int
    }

    class SMATrend {
        +int length
        +float band
        +bias(history) float
    }

    class MACDZeroLine {
        +float full
        +bias(history) float
    }

    class RSIReversal {
        +float oversold
        +float overbought
        +bias(history) float
    }

    class StochCross {
        +float low
        +float high
        +bias(history) float
    }

    class EMACross {
        +bias(history) float
    }

    class BollingerBand {
        +bias(history) float
    }

    class MACDSignalCross {
        +bias(history) float
    }

    class Decay {
        +float half_life
        +float floor
        +reset() None
        +bias(history) float
    }

    CrossRule --|> Rule
    SMATrend --|> Rule
    MACDZeroLine --|> Rule
    RSIReversal --|> Rule
    BollingerBand --|> Rule
    Decay --|> Rule
    StochCross --|> CrossRule
    EMACross --|> CrossRule
    MACDSignalCross --|> CrossRule
    CrossRule --> _CrossTracker : 持有
    Decay --> Rule : 包裝並轉發宣告
```

| 分組 | 規則 |
|------|------|
| 趨勢 | `SMATrend`、`MACDZeroLine` |
| 進場 | `RSIReversal`、`StochCross`、`EMACross` |
| 出場 | `BollingerBand`、`MACDSignalCross` |

`Decay` 不屬於任何分組，而是包住事件規則後再放進分組；`gated_strategy()` 用它包裝 `StochCross`、`EMACross` 與 `MACDSignalCross`。

## 3. 技術分析與回測引擎 (`src/quant/`)

```mermaid
classDiagram
    direction TB

    class indicator {
        <<Module: quant/indicator>>
        +int MACD_Z_WINDOW
        +compute_indicators(ticker, data, columns) None
    }

    class Strategy {
        <<Abstract>>
        +list~str~ required_columns
        +int warmup
        +int_or_None lookback
        +reset() None
        +signal(history, position) Signal
    }

    class RSIStrategy {
        +signal(history, position) Signal
    }

    class EMAStrategy {
        +reset() None
        +signal(history, position) Signal
    }

    class CompositeStrategy {
        +float trend_enter
        +float trend_exit
        +float entry_threshold
        +float exit_threshold
        +reset() None
        +signal(history, position) Signal
    }

    class strategy_module {
        <<Module: quant/strategy>>
        +gated_strategy() CompositeStrategy
        +voting_strategy() CompositeStrategy
    }

    class backtest_module {
        <<Module: quant/backtest>>
        +dict~str_int~ PERIOD_DAYS
        +int INITIAL_CAPITAL
        +float STOP_LOSS
        +history_window(data, i, lookback) DataFrame
    }

    class BacktestEngine {
        +Strategy strategy
        +float cash
        +Position position
        +list~Trade~ trades
        +list~float~ equity
        +required_history_days(period_days) int
        +run(ticker, data, start) BacktestResult
        +print_backtest_result(result) None
        +export_backtest_result_html(result) str
    }

    class InsufficientDataError {
        <<Exception: quant/errors>>
    }

    class html_report {
        <<見「Bot 與輸出工具」圖>>
    }
    class Rule {
        <<見「規則層」圖>>
    }
    class EMACross {
        <<見「規則層」圖>>
    }
    class Signal {
        <<見「資料模型」圖>>
    }
    class Position {
        <<見「資料模型」圖>>
    }
    class Trade {
        <<見「資料模型」圖>>
    }
    class BacktestResult {
        <<見「資料模型」圖>>
    }

    RSIStrategy --|> Strategy
    EMAStrategy --|> Strategy
    CompositeStrategy --|> Strategy
    EMAStrategy --> EMACross : 持有
    CompositeStrategy --> Rule : 依角色分組持有
    strategy_module ..> CompositeStrategy : 預設組合
    Strategy ..> Signal : 回傳
    indicator ..> InsufficientDataError : 拋出
    BacktestEngine --> Strategy : 持有
    BacktestEngine --> indicator : 計算指標
    BacktestEngine --> backtest_module : 讀取常數 / 切歷史區間
    BacktestEngine --> html_report : 匯出報表
    BacktestEngine ..> Position : 追蹤
    BacktestEngine ..> Trade : 產生
    BacktestEngine ..> BacktestResult : 回傳
    BacktestEngine ..> InsufficientDataError : 拋出
```

引擎不依賴任何資料來源，`run()` 接收呼叫端準備好的 DataFrame。

## 4. Bot 與輸出工具 (`src/bot/`、`src/utils/`)

`html_report` 和 Discord 無關，使用它的是 `BacktestEngine` 與 `database`；放在這張圖只是因為它也在 `src/utils/`。

```mermaid
classDiagram
    direction TB

    class dc_bot {
        <<Module: bot/dc_bot>>
        +commands.Bot bot
        +dict~str_type~ STRATEGIES
        +list~str~ BOT_PERIODS
        +stock_command(interaction, ticker)
        +backtest_stock(interaction, ticker, strategy, period)
    }

    class dc_bot_view {
        <<Module: bot/dc_bot_view>>
        +display_name(name, ticker) str
        +build_snapshot(ticker, name, history_data, intraday_data, latest_time) StockSnapshot
        +send_stock_response(interaction, snapshot, history_bytes, intraday_bytes)
        +send_backtest_response(interaction, result, stock_name, strategy_label, chart_bytes)
    }

    class ChartToggleView {
        <<discord.ui.View>>
        +bytes history_bytes
        +bytes_or_None intraday_bytes
        +bool is_history
        +on_timeout()
        +btn_toggle(interaction, button)
    }

    class visualizer {
        <<Module: utils/visualizer>>
        +generate_history_chart(ticker, data, days) BytesIO
        +generate_intraday_chart(ticker, data, baseline) BytesIO
        +generate_backtest_chart(ticker, result) BytesIO
    }

    class html_report {
        <<Module: utils/html_report>>
        +html_document(title, body, subtitle) str
        +html_table(headers, rows) str
        +fmt_num(v, decimals) str
        +fmt_int(v) str
        +write_report(html_text, name) str
    }

    class StockDataFetcher {
        <<見「資料存取與排程腳本」圖>>
    }
    class strategy_module {
        <<見「技術分析與回測引擎」圖>>
    }
    class indicator {
        <<見「技術分析與回測引擎」圖>>
    }
    class BacktestEngine {
        <<見「技術分析與回測引擎」圖>>
    }
    class InsufficientDataError {
        <<見「技術分析與回測引擎」圖>>
    }
    class StockSnapshot {
        <<見「資料模型」圖>>
    }
    class BacktestResult {
        <<見「資料模型」圖>>
    }

    dc_bot --> StockDataFetcher : 實例化
    dc_bot --> visualizer : 繪製圖表
    visualizer --> indicator : 計算均線
    dc_bot --> dc_bot_view : 組裝快照 / 送出回覆
    dc_bot --> BacktestEngine : 執行回測
    dc_bot --> strategy_module : STRATEGIES 對照表
    dc_bot_view --> ChartToggleView : 實例化
    dc_bot_view ..> StockSnapshot : 組裝與回傳
    dc_bot_view ..> BacktestResult : 讀取
    dc_bot_view ..> InsufficientDataError : 拋出
```

`visualizer` 在資料副本上用 `indicator` 計算均線，不會改到呼叫端的資料；Embed 需要的 RSI 則由 `build_snapshot` 自己計算。

## 5. HTTP API (`src/api/`)

`routes` 直接使用 `dc_bot_view.build_snapshot`，因此依賴 `bot`；API 和 Bot 共用同一套快照組裝邏輯。

```mermaid
classDiagram
    direction TB

    class main {
        <<Module: api/main>>
        +FastAPI app
    }

    class routes {
        <<Module: api/routes>>
        +APIRouter router
        +get_stock_snapshot(ticker) SnapshotResponse
    }

    class SnapshotResponse {
        <<pydantic.BaseModel>>
        +str ticker
        +str name
        +float current_price
        +float previous_close
        +float_or_None rsi_value
        +datetime latest_time
        +float change_percent
    }

    class StockDataFetcher {
        <<見「資料存取與排程腳本」圖>>
    }
    class dc_bot_view {
        <<見「Bot 與輸出工具」圖>>
    }
    class InsufficientDataError {
        <<見「技術分析與回測引擎」圖>>
    }
    class StockSnapshot {
        <<見「資料模型」圖>>
    }

    main --> routes : 掛載路由
    routes --> StockDataFetcher : 實例化
    routes --> dc_bot_view : 組裝快照
    routes ..> StockSnapshot : 讀取
    routes ..> SnapshotResponse : 轉換與回傳
    routes ..> InsufficientDataError : 捕捉並轉為 422
```

`SnapshotResponse` 只取 `StockSnapshot` 的數值欄位與 `change_percent`，不含 `change_str` 這類格式化字串。

## 6. 儲存層 (`src/database/`)

```mermaid
classDiagram
    direction TB

    class database {
        <<Module: database/database>>
        +str DB_PATH
        +connect_db() ContextManager~Connection~
        +load_sql(name) str
        +init_database()
        +insert_stock(ticker, name, market)
        +delete_stock(ticker)
        +get_stock(ticker) dict
        +get_daily_prices(ticker, limit) list
    }

    class sql_files {
        <<SQL Files: database/sql>>
        schema.sql
        upsert_stock.sql
        upsert_daily_price.sql
        select_daily_prices.sql
        select_historical_prices.sql
    }

    class stocks {
        <<Database Table>>
        +ticker TEXT PK
        +name TEXT NOT NULL
        +market TEXT
        +last_backfilled TEXT
    }

    class daily_prices {
        <<Database Table>>
        +id INTEGER PK AUTOINCREMENT
        +ticker TEXT FK
        +date TEXT NOT NULL
        +open_price REAL
        +high_price REAL
        +low_price REAL
        +close_price REAL
        +adjust_close_price REAL
        +volume REAL
        UNIQUE ticker + date
    }

    class html_report {
        <<見「Bot 與輸出工具」圖>>
    }

    database --> sql_files : 載入
    database --> html_report : 匯出價格報表
    database ..> stocks : CRUD
    database ..> daily_prices : CRUD
    daily_prices --> stocks : FK (ticker)
```

## 7. 資料存取與排程腳本 (`src/data/`、`scripts/`)

`fetcher` 負責讀取，`sync` 負責寫入行情。兩支回補腳本透過 `sync` 寫入，`seed_stocks` 則直接寫入股票清單。

```mermaid
classDiagram
    direction TB

    class StockDataFetcher {
        +str ticker
        +DataFrame historical_data
        +DataFrame intraday_data
        +stock_exists() bool
        +fetch_stock_name() str
        +fetch_historical_data(days) DataFrame
        +fetch_intraday_data() DataFrame
        +latest_time() Timestamp
        +get_data_range() dict
        -_format_ticker(ticker) str
    }

    class sync {
        <<Module: data/sync>>
        +download_ohlcv(tickers, period) DataFrame
        +extract_ticker_frame(data, ticker) DataFrame
        +records_from_frame(ticker, frame) list
        +upsert_records(conn, records) None
        +fetch_all_tickers(conn) list
        +fetch_pending_tickers(conn, max_age_days) list
        +mark_backfilled(conn, tickers) None
        +needs_full_refresh(conn, ticker, frame) bool
    }

    class daily_updater {
        <<Script>>
        +update_stock_data() list~str~
    }

    class historical_backfill {
        <<Script>>
        +backfill_history(period, tickers, force)
    }

    class seed_stocks {
        <<Script>>
        +import_taiwan_stocks(conn)
        +import_us_stocks(conn)
        +import_global_indices(conn)
    }

    class twstock {
        <<External>>
    }
    class yfinance {
        <<External>>
    }
    class database {
        <<見「儲存層」圖>>
    }
    class stocks {
        <<見「儲存層」圖>>
    }
    class daily_prices {
        <<見「儲存層」圖>>
    }

    StockDataFetcher --> database : connect_db() / load_sql()
    StockDataFetcher --> twstock : 台股市場別對照
    StockDataFetcher --> yfinance : 盤中資料
    StockDataFetcher ..> stocks : 讀取
    StockDataFetcher ..> daily_prices : 讀取
    sync --> database : load_sql()
    sync --> yfinance : 批次下載
    sync ..> stocks : 讀寫 last_backfilled
    sync ..> daily_prices : 寫入
    daily_updater --> sync
    daily_updater --> historical_backfill : 觸發完整重抓
    daily_updater --> database : connect_db()
    historical_backfill --> sync
    historical_backfill --> database : connect_db()
    seed_stocks --> database : 初始化 / 寫入
    seed_stocks --> twstock : 台股清單
    seed_stocks ..> stocks : 寫入
```
