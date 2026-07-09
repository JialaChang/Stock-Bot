import mplfinance as mpf
import pandas as pd
import io
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from datetime import date

from src.models import BacktestResult

# 關閉 GUI 互動模式，強制將 Matplotlib 渲染後端設為 'Agg'，適用於伺服器端純生成圖片
matplotlib.use('Agg')

_MARKET_COLORS = mpf.make_marketcolors(
    up='red',
    down='green',
    edge='inherit',
    wick='inherit',
    volume='#87ceeb',
)
_MPF_STYLE = mpf.make_mpf_style(marketcolors=_MARKET_COLORS, gridstyle='--')


def generate_history_chart(ticker: str, data: pd.DataFrame, days: int = 61) -> io.BytesIO:
    """生成歷史日線 K 線圖（含均線與成交量），回傳 in-memory PNG"""
    plot_data = data.iloc[-days:]

    addplot = [
        mpf.make_addplot(plot_data['SMA_5'], color="#FFA41C", width=1, label='5MA'),
        mpf.make_addplot(plot_data['SMA_10'], color="#05B3F3", width=1, label='10MA'),
        mpf.make_addplot(plot_data['SMA_20'], color="#A137E4", width=1, label='20MA')
    ]

    # 宣告記憶體流，避免將圖片寫入實體硬碟
    buffer = io.BytesIO()

    mpf.plot(
        plot_data,
        type='candle',
        addplot=addplot,
        style=_MPF_STYLE,
        title=f"\n{ticker}",
        show_nontrading=False,
        datetime_format='%m/%d',
        tight_layout=True,
        xrotation=0,
        volume=True,
        volume_alpha=0.3,
        panel_ratios=(4, 1),
        savefig=buffer
    )
    buffer.seek(0)  # 重設讀取指標，供呼叫端從頭讀取
    plt.close('all')
    return buffer


def generate_intraday_chart(ticker: str, data: pd.DataFrame) -> io.BytesIO:
    """生成盤中分時折線圖，以開盤價為基準紅漲綠跌分色"""
    open_price = data['Open'].iloc[0]

    above_open = data['Close'].where(data['Close'] >= open_price)
    below_open = data['Close'].where(data['Close'] < open_price)

    # 開盤價虛線作為漲跌分界參考線
    ref_line = pd.Series(open_price, index=data.index)
    addplot = [mpf.make_addplot(ref_line, color='#a0a0a0', linestyle='dotted', width=2)]

    if above_open.notna().any():
        addplot.append(mpf.make_addplot(above_open, color='#e74c3c', width=1))
    if below_open.notna().any():
        addplot.append(mpf.make_addplot(below_open, color='#2ecc71', width=1))

    fills = [
        dict(y1=data['Close'].values, y2=open_price, where=(data['Close'] >= open_price).values, color='#e74c3c', alpha=0.1),
        dict(y1=data['Close'].values, y2=open_price, where=(data['Close'] < open_price).values, color='#2ecc71', alpha=0.1)
    ]

    buffer = io.BytesIO()

    mpf.plot(
        data,
        type='line',
        linecolor='#555555',
        addplot=addplot,
        fill_between=fills,
        style=_MPF_STYLE,
        title=f"\n{ticker}",
        datetime_format='%H:%M',
        tight_layout=True,
        xrotation=0,
        volume=True,
        volume_alpha=0.3,
        panel_ratios=(4, 1),
        savefig=buffer
    )

    buffer.seek(0)
    plt.close('all')
    return buffer

def generate_backtest_chart(ticker: str, result: BacktestResult) -> io.BytesIO:
    """生成回測結果圖：K線 + 進出場標記 + 權益曲線"""
    data = result.data

    long_entries = [(t.entry_date, t.entry_price) for t in result.trades if t.side == "LONG"]
    long_exits = [(t.exit_date, t.exit_price) for t in result.trades if t.side == "LONG"]
    short_entries = [(t.entry_date, t.entry_price) for t in result.trades if t.side == "SHORT"]
    short_exits = [(t.exit_date, t.exit_price) for t in result.trades if t.side == "SHORT"]

    marker_long_entries = _build_marker_series(data, long_entries)
    marker_long_exits = _build_marker_series(data, long_exits)
    marker_short_entries = _build_marker_series(data, short_entries)
    marker_short_exits = _build_marker_series(data, short_exits)

    addplot = [
        mpf.make_addplot(result.equity_curve, panel=1, color='#3498db', ylabel='Equity', width=1.2),
    ]
    if marker_long_entries.notna().any():
        addplot.append(mpf.make_addplot(marker_long_entries, type='scatter', markersize=80, marker='^', color="#e73ce7"))
    if marker_long_exits.notna().any():
        addplot.append(mpf.make_addplot(marker_long_exits, type='scatter', markersize=80, marker='v', color='#e73ce7'))
    if marker_short_entries.notna().any():
        addplot.append(mpf.make_addplot(marker_short_entries, type='scatter', markersize=80, marker='^', color="#2eccbf"))
    if marker_short_exits.notna().any():
        addplot.append(mpf.make_addplot(marker_short_exits, type='scatter', markersize=80, marker='v', color='#2eccbf'))

    buffer = io.BytesIO()

    mpf.plot(
        data,
        type='candle',
        addplot=addplot,
        style=_MPF_STYLE,
        title=f"\n{ticker}",
        show_nontrading=False,
        datetime_format='%m/%d',
        tight_layout=True,
        xrotation=0,
        panel_ratios=(4, 2),
        savefig=buffer
    )
    
    buffer.seek(0)
    plt.close('all')
    return buffer


def _build_marker_series(data: pd.DataFrame, points: list[tuple[date, float]]) -> pd.Series:
    """將 (日期, 價格) 列表轉成與 data.index 等長的標記序列，非交易日為 NaN"""
    marker = pd.Series(data=np.nan, index=data.index)
    for d, price in points:
        marker.loc[pd.Timestamp(d)] = price # pyright: ignore[reportCallIssue, reportArgumentType]
    return marker
