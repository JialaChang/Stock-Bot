# 架構與模組說明

各模組職責與 Discord 指令資料流。完整類別關聯見 [UML.md](./UML.md)。

---

## 模組說明

### `StockDataFetcher` (`src/data/fetcher.py`)

整合三個資料源的查詢門面：
- **SQLite**：歷史日線與股票名稱
- **yfinance**：當日 1 分鐘盤中資料
- **twstock**：台股代碼與市場別（上市 / 上櫃）對照

### `compute_indicators` / `compute_indicators_for_discord` (`src/quant/indicator.py`)

刻意分離的兩個函式，對應不同情境：

| 函式 | 用途 | 回傳 |
|------|------|------|
| `compute_indicators(ticker, data, columns)` | 回測用：依 `columns` 原地寫入指標，`None` 代表全算 | `None` |
| `compute_indicators_for_discord()` | Discord 用：算 Embed 所需指標與現價漲跌幅 | `StockSnapshot` |

### `visualizer.py` (`src/utils/visualizer.py`)

生成 in-memory PNG：
- `generate_history_chart`：日線 K 線 + MA5/10/20 + 成交量
- `generate_intraday_chart`：盤中折線，以開盤價為界紅漲綠跌
- `generate_backtest_chart`：K 線 + 多空進出場標記 + 權益曲線

### `dc_bot_view.py` (`src/bot/dc_bot_view.py`)

- `DiscordStockChart`：持有圖表 bytes 的 `View`，按鈕切換日線 / 分時圖，逾時 5 分鐘清理
- `send_stock_response`：股票資訊 Embed + 可切換圖表 View
- `send_backtest_response`：回測績效 Embed（報酬率／勝率／最大回撤／交易次數）+ 回測圖

### `BacktestEngine` (`src/quant/backtest.py`)

逐日迭代 OHLCV 的回測引擎，與策略解耦（初始化時注入 `Strategy`）：
- 只計算並 `dropna` 策略宣告的 `required_columns`
- **pending signal**：訊號於當日收盤產生，隔日開盤成交
- 以 `cumulative_multiplier` 累積收益倍率，支援做多 / 做空
- 結束時未平倉部位以最後一日收盤強制平倉，回傳 `BacktestResult`

```
每日迴圈：
  1. 執行昨日 pending signal → 今日開盤成交
  2. 盤中止損（當日即時，跳空則以開盤價成交）
  3. 以今日收盤記錄 equity
  4. 依今日收盤產生明日 pending signal
```

### `Strategy` (`src/quant/strategy.py`)

抽象基底，子類實作 `signal()` 並宣告 `required_columns`：

| 類別 | `required_columns` | 策略 |
|------|--------------------|------|
| `RSIStrategy` | `["RSI"]` | RSI 超買 / 超賣 |
| `EMAStrategy` | `["EMA_5", "EMA_20"]` | EMA5/20 黃金 / 死亡交叉 |

### `Signal` / `Position` / `Trade` / `BacktestResult` (`src/models/trade.py`)

| 類別 | 說明 |
|------|------|
| `Signal` | 策略訊號：`action`、`conditions`、觸發時 `values` |
| `Position` | 進場快照（日期／價格／方向）；`unrealized_pnl_ratio()` 回傳浮動損益倍率 |
| `Trade` | 單筆交易；屬性 `profit_and_loss`、`return_on_investment`、`is_profit` |
| `BacktestResult` | 回測彙總（`trades`／`equity_curve`／`data`）；屬性 `total_return`、`win_rate`、`max_drawdown`、`trade_count` |

---

## Discord 指令資料流

### `/stock`

```
使用者輸入 ticker
    → StockDataFetcher._format_ticker()   # 補齊 .TW / .TWO 後綴
    → asyncio.gather()                    # 並發：SQLite 歷史 + yfinance 盤中
    → compute_indicators_for_discord()    # RSI(14)、MA5/10/20、漲跌幅 → StockSnapshot
    → asyncio.gather()                    # 並發：歷史 K 線圖 + 盤中分時圖
    → send_stock_response()               # 組裝 Embed 送出
    → DiscordStockChart View              # Embed + 可切換按鈕（5 分鐘逾時）
```

### `/backtest`

```
使用者輸入 ticker、strategy、period
    → StockDataFetcher.fetch_historical_data(period)  # 歷史 OHLCV
    → BacktestEngine.run(ticker, data)                # 逐日回測 → BacktestResult
    → generate_backtest_chart()                       # K 線 + 進出場標記 + 權益曲線
    → send_backtest_response()                        # 績效 Embed 附圖送出
```
