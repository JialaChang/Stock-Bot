"""Snapshot building."""
from datetime import datetime

import pandas as pd
import pytest

from src.data.snapshot import build_snapshot
from src.quant.errors import InsufficientDataError
from tests.conftest import make_ohlcv


LATEST = datetime(2026, 3, 24, 13, 30)


def intraday(closes, *, day, start_minute=9):
    """Minute bars stamped on `day`, standing in for what yfinance returns intraday."""
    index = pd.date_range(f'{day} {start_minute:02d}:00', periods=len(closes), freq='1min')
    return pd.DataFrame({'Close': list(closes)}, index=index)


class TestSnapshotCurrentPrice:
    def test_intraday_wins_when_the_market_has_traded_today(self):
        history = make_ohlcv([100.0, 101.0, 102.0])
        bars = intraday([104.0, 105.5], day=history.index[-1].date())

        snapshot = build_snapshot('X.TW', 'XCo', history, bars, LATEST)

        assert snapshot.current_price == 105.5

    def test_the_last_close_stands_in_when_there_is_no_intraday(self):
        history = make_ohlcv([100.0, 101.0, 102.0])

        snapshot = build_snapshot('X.TW', 'XCo', history, pd.DataFrame(), LATEST)

        assert snapshot.current_price == 102.0


class TestSnapshotPreviousClose:
    def test_the_baseline_is_the_last_close_before_the_current_price(self):
        # The last daily row is today's own close, so it cannot be the baseline
        history = make_ohlcv([100.0, 101.0, 102.0])
        bars = intraday([105.0], day=history.index[-1].date())

        snapshot = build_snapshot('X.TW', 'XCo', history, bars, LATEST)

        assert snapshot.previous_close == 101.0

    def test_a_session_the_daily_rows_have_not_reached_yet_keeps_the_last_close(self):
        # During the session the newest stored close is yesterday's
        history = make_ohlcv([100.0, 101.0, 102.0])
        tomorrow = (history.index[-1] + pd.Timedelta(days=1)).date()
        bars = intraday([105.0], day=tomorrow)

        snapshot = build_snapshot('X.TW', 'XCo', history, bars, LATEST)

        assert snapshot.previous_close == 102.0

    def test_without_intraday_the_baseline_is_the_row_before_last(self):
        history = make_ohlcv([100.0, 101.0, 102.0])

        snapshot = build_snapshot('X.TW', 'XCo', history, pd.DataFrame(), LATEST)

        assert snapshot.previous_close == 101.0

    def test_the_change_percent_is_measured_against_that_baseline(self):
        history = make_ohlcv([100.0, 100.0])
        bars = intraday([110.0], day=history.index[-1].date())

        snapshot = build_snapshot('X.TW', 'XCo', history, bars, LATEST)

        assert snapshot.change_percent == pytest.approx(10.0)


class TestSnapshotFields:
    def test_the_ticker_name_and_time_are_carried_through(self):
        history = make_ohlcv([100.0, 101.0, 102.0])

        snapshot = build_snapshot('2330.TW', '台積電', history, pd.DataFrame(), LATEST)

        assert (snapshot.ticker, snapshot.name, snapshot.latest_time) == ('2330.TW', '台積電', LATEST)

    def test_an_rsi_is_reported_once_there_is_enough_history(self):
        history = make_ohlcv([100 + (i % 5) - (i % 3) for i in range(40)])

        snapshot = build_snapshot('X.TW', 'XCo', history, pd.DataFrame(), LATEST)

        assert snapshot.rsi_value is not None
        assert 0.0 <= snapshot.rsi_value <= 100.0

    def test_an_unusable_rsi_is_reported_as_missing_rather_than_guessed(self):
        # Two rows cannot produce a 14-period RSI; the Embed shows N/A for it.
        history = make_ohlcv([100.0, 101.0])

        snapshot = build_snapshot('X.TW', 'XCo', history, pd.DataFrame(), LATEST)

        assert snapshot.rsi_value is None
        assert snapshot.rsi_str == 'N/A'


class TestSnapshotInputs:
    def test_a_frame_too_short_to_read_is_refused(self):
        history = make_ohlcv([100.0])

        with pytest.raises(InsufficientDataError) as excinfo:
            build_snapshot('X.TW', 'XCo', history, pd.DataFrame(), LATEST)

        assert 'X.TW' in str(excinfo.value)

    def test_neither_frame_is_written_to(self):
        # The chart layer still uses both frames
        history = make_ohlcv([100 + (i % 5) for i in range(40)])
        bars = intraday([105.0], day=history.index[-1].date())
        history_columns, intraday_columns = list(history.columns), list(bars.columns)

        build_snapshot('X.TW', 'XCo', history, bars, LATEST)

        assert list(history.columns) == history_columns
        assert list(bars.columns) == intraday_columns
