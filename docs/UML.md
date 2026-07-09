# 系統架構與 UML 類別圖

依專案目錄結構拆成 4 張圖，避免單一巨圖因跨層關聯過多、Mermaid 自動排版變得雜亂難讀。若某類別的完整定義屬於其他圖，會以 `<<見「X」圖>>` 標註，只保留關聯線。

## 1. 資料模型 (Models)

`src/models/` 下的共用資料傳輸物件，被 Quant 與 Bot 層共用。

```mermaid
classDiagram
    direction TB

    class StockSnapshot {
        <<Data Transfer Object>>
        +str ticker
        +str name
        +float current_price
        +float change_percent
        +float rsi_value
        +datetime latest_time
        +str change_str
        +str latest_time_str
    }

    class Signal {
        <<Data Transfer Object>>
        +Literal action: ENTER_LONG|EXIT_LONG|ENTER_SHORT|EXIT_SHORT|HOLD
        +dict~str_bool~ conditions
        +dict~str_float~ values
    }

    class Position {
        <<Data Transfer Object>>
        +date entry_date
        +float entry_price
        +Signal entry_signal
        +Literal side: LONG|SHORT
        +unrealized_pnl_ratio(price_now) float
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
        +Literal side: LONG|SHORT
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

## 2. 技術分析與回測引擎 (Quant)

`src/quant/` 策略介面與回測引擎；`Strategy` 子類別透過 `required_columns` 告知引擎所需指標。

```mermaid
classDiagram
    direction TB

    class indicator {
        <<Module: quant/indicator>>
        +compute_indicators(ticker, history_data, columns) None
        +compute_indicators_for_discord(ticker, name, history_data, intraday_data, latest_time) StockSnapshot
    }
    note for indicator "columns=None 計算全套；否則只算指定欄位"

    class Strategy {
        <<Abstract>>
        +list~str~ required_columns
        +signal(row, position) Signal
    }

    class RSIStrategy {
        +required_columns = ["RSI"]
        +signal(row, position) Signal
    }

    class EMAStrategy {
        +required_columns = ["EMA_5", "EMA_20"]
        +signal(row, position) Signal
    }

    class BacktestEngine {
        +Strategy strategy
        +float cumulative_multiplier
        +Position position
        +list~Trade~ trades
        +list~float~ equity
        +run(ticker, data) BacktestResult
        +print_backtest_result(result) None
    }

    class StockDataFetcher {
        <<見「資料擷取、資料庫與排程腳本」圖>>
    }
    class StockSnapshot {
        <<見「資料模型」圖>>
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

    RSIStrategy --|> Strategy : 繼承
    EMAStrategy --|> Strategy : 繼承
    Strategy ..> Signal : 回傳
    indicator ..> StockSnapshot : 回傳股票快照
    BacktestEngine --> Strategy : 持有
    BacktestEngine --> indicator : 計算指標
    BacktestEngine --> StockDataFetcher : 取得歷史資料
    BacktestEngine ..> Position : 持倉追蹤
    BacktestEngine ..> Trade : 產生
    BacktestEngine ..> BacktestResult : 回傳
```

## 3. Discord 機器人與圖表渲染 (Bot & Utils)

`src/bot/` 斜線指令與 View 元件；`src/utils/visualizer.py` 負責產生圖表 bytes。

```mermaid
classDiagram
    direction TB

    class dc_bot {
        <<Module: bot/dc_bot>>
        +commands.Bot bot
        +on_ready()
        +on_disconnect()
        +analyze_stock(interaction, ticker)
        +backtest_stock(interaction, ticker, strategy, period)
    }

    class dc_bot_view {
        <<Module: bot/dc_bot_view>>
        +send_stock_response(interaction, snapshot, history_bytes, intraday_bytes)
        +send_backtest_response(interaction, result, strategy_label, chart_bytes)
    }

    class DiscordStockChart {
        <<discord.ui.View>>
        +str stock_ticker
        +bytes history_bytes
        +bytes intraday_bytes
        +bool is_history
        +Message message
        +on_timeout()
        +btn_toggle(interaction, button)
    }

    class visualizer {
        <<Module: utils/visualizer>>
        +generate_history_chart(ticker, data, days) BytesIO
        +generate_intraday_chart(ticker, data) BytesIO
        +generate_backtest_chart(ticker, result) BytesIO
    }
    note for visualizer "需要的指標已由 indicator 寫入"

    class StockDataFetcher {
        <<見「資料擷取、資料庫與排程腳本」圖>>
    }
    class indicator {
        <<見「技術分析與回測引擎」圖>>
    }
    class BacktestEngine {
        <<見「技術分析與回測引擎」圖>>
    }
    class BacktestResult {
        <<見「資料模型」圖>>
    }

    dc_bot --> StockDataFetcher : 實例化
    dc_bot --> indicator : 計算指標
    dc_bot --> visualizer : 繪製圖表
    dc_bot --> dc_bot_view : 封裝 View 訊息物件
    dc_bot --> BacktestEngine : 執行回測
    dc_bot_view --> DiscordStockChart : 實例化 View
    dc_bot_view ..> BacktestResult : 讀取回測結果
```

## 4. 資料擷取、資料庫與排程腳本 (Data & Database & Scripts)

`src/data/fetcher.py` 整合 SQLite 與 yfinance；`src/database/` 為底層 CRUD；`scripts/` 為獨立排程腳本。

```mermaid
classDiagram
    direction TB

    class StockDataFetcher {
        -str _raw_ticker
        +str ticker
        +DataFrame historical_data
        +DataFrame intraday_data
        +check_stock_exist() bool
        +fetch_stock_name() str
        +fetch_historical_data(period) DataFrame
        +fetch_intraday_data() DataFrame
        +fetch_latest_time() Timestamp
        +get_data_count() dict
    }

    class database {
        <<Module: database/database>>
        +str DB_PATH
        +init_database()
        +insert_stock(ticker, name, market)
        +delete_stock(ticker)
        +get_stock(ticker) dict
        +get_daily_prices(ticker, limit) list
    }

    class stocks {
        <<Database Table>>
        +ticker TEXT PK
        +name TEXT NOT NULL
        +market TEXT
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
    }

    class daily_updater {
        <<Script>>
        +update_stock_data()
    }

    class historical_backfill {
        <<Script>>
        +backfill_history(period)
    }

    class seed_stocks {
        <<Script>>
        +import_taiwan_stocks(conn)
        +import_us_stocks(conn)
        +import_global_indices(conn)
    }

    StockDataFetcher ..> stocks : 讀取
    StockDataFetcher ..> daily_prices : 讀取
    database ..> stocks : CURD
    database ..> daily_prices : CURD
    daily_updater ..> daily_prices : 寫入
    historical_backfill ..> daily_prices : 寫入
    seed_stocks --> database : 初始化
    seed_stocks ..> stocks : 寫入
    daily_prices --> stocks : FK (ticker)
```
