import mplfinance as mpf
import pandas as pd
import io
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from datetime import date

from src.models import BacktestResult


matplotlib.use('Agg')  # Headless

_MARKET_COLORS = mpf.make_marketcolors(
    up='red',
    down='green',
    edge='inherit',
    wick='inherit',
    volume='#87ceeb',
)
_MPF_STYLE = mpf.make_mpf_style(marketcolors=_MARKET_COLORS, gridstyle='--')

# Beyond this many bars candles are about a pixel wide, so draw a line instead
_MAX_CANDLES = 600

# Daily chart overlays: column -> (color, label)
_HISTORY_CHART_IND = {
    'SMA_5': ("#FFA41C", '5MA'),
    'SMA_10': ("#05B3F3", '10MA'),
    'SMA_20': ("#A137E4", '20MA'),
}

# Backtest trade markers: (side, is_entry, marker, color)
_TRADE_MARKERS = [
    ("LONG", True, '^', '#e73ce7'),
    ("LONG", False, 'v', '#e73ce7'),
    ("SHORT", True, '^', '#2eccbf'),
    ("SHORT", False, 'v', '#2eccbf'),
]


def _render(data: pd.DataFrame, **plot_kwargs) -> io.BytesIO:
    """Plot `data` with the shared style and return the PNG in memory."""
    buffer = io.BytesIO()
    mpf.plot(data, style=_MPF_STYLE, tight_layout=True, xrotation=0, savefig=buffer, **plot_kwargs)
    buffer.seek(0)
    plt.close('all')
    return buffer


def generate_history_chart(ticker: str, data: pd.DataFrame, days: int = 61) -> io.BytesIO:
    """Daily candlestick chart with moving averages and volume, as an in-memory PNG."""
    from src.quant.indicator import compute_indicators

    # Compute over the full history, then slice
    frame = data.copy()
    compute_indicators(ticker, frame, list(_HISTORY_CHART_IND))
    plot_data = frame.iloc[-days:]

    addplot = [
        mpf.make_addplot(plot_data[col], color=color, width=1, label=label)
        for col, (color, label) in _HISTORY_CHART_IND.items()
    ]

    return _render(
        plot_data,
        type='candle',
        addplot=addplot,
        title=f"\n{ticker}",
        show_nontrading=False,
        datetime_format='%m/%d',
        volume=True,
        volume_alpha=0.3,
        panel_ratios=(4, 1),
    )


def generate_intraday_chart(ticker: str, data: pd.DataFrame, baseline: float) -> io.BytesIO:
    """Intraday line chart, red above and green below `baseline` (the previous close)."""
    above = data['Close'].where(data['Close'] >= baseline)
    below = data['Close'].where(data['Close'] < baseline)

    ref_line = pd.Series(baseline, index=data.index)
    addplot = [mpf.make_addplot(ref_line, color='#a0a0a0', linestyle='dotted', width=2)]

    if above.notna().any():
        addplot.append(mpf.make_addplot(above, color='#e74c3c', width=1))
    if below.notna().any():
        addplot.append(mpf.make_addplot(below, color='#2ecc71', width=1))

    fills = [
        dict(y1=data['Close'].values, y2=baseline, where=(data['Close'] >= baseline).values, color='#e74c3c', alpha=0.1),
        dict(y1=data['Close'].values, y2=baseline, where=(data['Close'] < baseline).values, color='#2ecc71', alpha=0.1)
    ]

    return _render(
        data,
        type='line',
        linecolor='#555555',
        addplot=addplot,
        fill_between=fills,
        title=f"\n{ticker}",
        datetime_format='%H:%M',
        volume=True,
        volume_alpha=0.3,
        panel_ratios=(4, 1),
    )


def generate_backtest_chart(ticker: str, result: BacktestResult) -> io.BytesIO:
    """Backtest chart: price, entry/exit markers and equity curve."""
    data = result.data

    addplot = [
        mpf.make_addplot(result.equity_curve, panel=1, color='#3498db', ylabel='Equity', width=1.2),
    ]
    for side, is_entry, marker, color in _TRADE_MARKERS:
        points = [(t.entry_date, t.entry_price) if is_entry else (t.exit_date, t.exit_price)
                  for t in result.trades if t.side == side]
        series = _build_marker_series(data, points)
        if series.notna().any():
            addplot.append(mpf.make_addplot(series, type='scatter', markersize=40, marker=marker, color=color))

    return _render(
        data,
        type='candle' if len(data) <= _MAX_CANDLES else 'line',
        addplot=addplot,
        title=f"\n{ticker}",
        show_nontrading=False,
        datetime_format='%m/%d',
        panel_ratios=(4, 2),
    )


def _build_marker_series(data: pd.DataFrame, points: list[tuple[date, float]]) -> pd.Series:
    """(date, price) points as a series aligned to `data.index`, NaN elsewhere."""
    marker = pd.Series(data=np.nan, index=data.index)
    for d, price in points:
        marker.loc[pd.Timestamp(d)] = price # pyright: ignore[reportCallIssue, reportArgumentType]
    return marker
