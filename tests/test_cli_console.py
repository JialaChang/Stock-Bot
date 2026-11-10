"""Single-key menus and their prompt formatting."""
import builtins
import sys
from datetime import date

import pytest

from src.cli import console as cli_console
from src.cli.cli_database import STALE_AFTER_TRADING_DAYS, trading_days_behind
from src.cli.console import _option_label, choose


class FakeStdin:
    def __init__(self, tty: bool):
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty


@pytest.fixture
def keys(monkeypatch):
    """Feed keypresses to choose() as if typed at a terminal."""
    def feed(*pressed: str):
        queue = list(pressed)
        monkeypatch.setattr(sys, 'stdin', FakeStdin(tty=True))
        monkeypatch.setattr(cli_console.click, 'getchar', lambda: queue.pop(0))
    return feed


@pytest.fixture
def lines(monkeypatch):
    """Feed whole lines to choose(), as from a pipe."""
    def feed(*typed: str):
        queue = list(typed)
        monkeypatch.setattr(sys, 'stdin', FakeStdin(tty=False))
        monkeypatch.setattr(builtins, 'input', lambda *_: queue.pop(0))
    return feed


class TestOptionLabel:
    @pytest.mark.parametrize('key, label, expected', [
        ('t', 'ticker', '[t]icker'),
        ('a', 'all', '[a]ll'),
        ('1', 'RSI', '[1] RSI'),
        ('m', 'more', '[m]ore'),
    ])
    def test_formats(self, key, label, expected):
        assert _option_label(key, label) == expected

    def test_a_digit_key_never_brackets_into_the_label(self):
        # '1mo' starts with its key, but '[1]mo' would read as a different period
        assert _option_label('1', '1mo') == '[1] 1mo'


class TestChoose:
    OPTIONS = {'y': 'yes', 'n': 'no'}

    def test_returns_the_key_pressed(self, keys):
        keys('y')
        assert choose('Export?', self.OPTIONS) == 'y'

    def test_reasks_after_an_invalid_key(self, keys, capsys):
        keys('x', 'n')
        assert choose('Export?', self.OPTIONS) == 'n'
        assert 'Invalid input' in capsys.readouterr().out

    def test_accepts_upper_case(self, keys):
        keys('Y')
        assert choose('Export?', self.OPTIONS) == 'y'

    def test_echoes_the_chosen_label(self, keys, capsys):
        keys('n')
        choose('Export?', self.OPTIONS)
        assert capsys.readouterr().out.rstrip().endswith('no')

    def test_falls_back_to_lines_off_a_terminal(self, lines):
        lines('maybe', 'y')
        assert choose('Export?', self.OPTIONS) == 'y'


class TestTradingDaysBehind:
    def test_same_day_is_current(self):
        assert trading_days_behind('2026-11-09', date(2026, 11, 9)) == 0

    def test_a_weekend_does_not_count(self):
        # Friday's close seen on Monday is one trading day behind, not three days
        assert trading_days_behind('2026-11-06', date(2026, 11, 9)) == 1

    def test_stale_only_past_the_threshold(self):
        today = date(2026, 11, 6)
        assert trading_days_behind('2026-10-30', today) == STALE_AFTER_TRADING_DAYS
        assert trading_days_behind('2026-10-29', today) > STALE_AFTER_TRADING_DAYS
