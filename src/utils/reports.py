"""The project's HTML reports and the up/down classes shared with the terminal."""
from datetime import datetime
from typing import Any, Literal

from src.models.trade import BacktestResult, Signal
from src.utils.html_page import html_document, html_table, fmt_num, fmt_int, write_report


Change = Literal['up', 'down', 'flat']


def change_class(value: float) -> Change:
    return 'up' if value > 0 else 'down' if value < 0 else 'flat'


def price_change_classes(prices: list[dict[str, Any]]) -> list[Change]:
    """Class per row against the previous trading day; rows arrive newest first."""
    classes: list[Change] = []
    for i, p in enumerate(prices):
        close_p = p.get('close_price')
        prev_close = prices[i + 1].get('close_price') if i + 1 < len(prices) else None
        if close_p is not None and prev_close is not None:
            classes.append(change_class(close_p - prev_close))
        else:
            classes.append('flat')
    return classes


def summary_rows(result: BacktestResult) -> list[tuple[str, str, Change | None]]:
    """Performance summary as (label, text, class) rows, shared by the terminal and HTML."""
    curve = result.equity_curve
    return [
        ('Total return', f'{result.total_return:+.2f}%', change_class(result.total_return)),
        ('Win rate', f'{result.win_rate:.2f}%', None),
        ('Max drawdown', f'{result.max_drawdown:.2f}%', 'down'),
        ('Trade count', str(result.trade_count), None),
        ('Initial capital', f'{curve.iloc[0]:,.2f}', None),
        ('Final capital', f'{curve.iloc[-1]:,.2f}', None),
        ('Equity curve min', f'{curve.min():,.2f}', None),
        ('Equity curve max', f'{curve.max():,.2f}', None),
    ]


def _generated_subtitle(data_range: str) -> str:
    return f"Data {data_range} · Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"


def export_backtest_html(result: BacktestResult, strategy_label: str) -> str:
    """Write the backtest report under exports/ and return its path."""
    def signal_reason(sig: Signal) -> str:
        reasons = [name for name, holds in sig.conditions.items() if holds]
        return ', '.join(reasons) if reasons else 'N/A'

    summary_table = html_table(None, [
        [label, (text, cls) if cls else text] for label, text, cls in summary_rows(result)
    ])

    trade_rows = []
    for t in result.trades:
        roi = t.return_on_investment
        trade_rows.append([
            t.side,
            (f'{roi:+.2f}%', change_class(roi)),
            (fmt_num(t.profit_and_loss), change_class(t.profit_and_loss)),
            fmt_int(t.shares),
            str(t.entry_date),
            fmt_num(t.entry_price),
            signal_reason(t.entry_signal),
            str(t.exit_date),
            fmt_num(t.exit_price),
            signal_reason(t.exit_signal),
        ])
    trades_table = html_table(
        ['Side', 'Return', 'P&L', 'Shares', 'Entry Date', 'Entry', 'Entry Reason',
         'Exit Date', 'Exit', 'Exit Reason'],
        trade_rows,
    )

    body = (
        f'<h2>Performance</h2>\n{summary_table}\n'
        f'<h2>Trades</h2>\n{trades_table}'
    )
    index = result.equity_curve.index
    data_range = f"{index[0].strftime('%Y-%m-%d')} ~ {index[-1].strftime('%Y-%m-%d')}"
    html = html_document(f'{result.ticker} backtest — {strategy_label}', body,
                         subtitle=_generated_subtitle(data_range))
    return write_report(html, f'{result.ticker}_{strategy_label}_backtest')


def export_prices_html(ticker: str, prices: list[dict[str, Any]]) -> str:
    """Write price records (newest first) under exports/ and return the path."""
    rows = []
    for p, cls in zip(prices, price_change_classes(prices)):
        rows.append([
            p.get('date', ''),
            fmt_num(p.get('open_price')),
            fmt_num(p.get('high_price')),
            fmt_num(p.get('low_price')),
            (fmt_num(p.get('close_price')), cls),
            fmt_num(p.get('adjust_close_price')),
            fmt_int(p.get('volume')),
        ])

    table = html_table(['Date', 'Open', 'High', 'Low', 'Close', 'AdjClose', 'Volume'], rows)
    data_range = f"{prices[-1].get('date', '?')} ~ {prices[0].get('date', '?')}"
    html = html_document(f'{ticker} — {len(prices)} records', table,
                         subtitle=_generated_subtitle(data_range))
    return write_report(html, f'{ticker}_prices')
