from abc import ABC, abstractmethod
from pandas import DataFrame


class Rule(ABC):
    name: str = ""  # Shown in the HTML report
    required_columns: list[str] = []
    warmup: int = 0
    lookback: int | None = 1  # Rows wanted, today included; None means everything

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Clear per-run state."""

    @abstractmethod
    def bias(self, history: DataFrame) -> float:
        """Which side this rule favours at today's close: -1 short, +1 long, 0 no opinion."""
        ...


class _CrossTracker:
    """Remembers which line was on top when they were last strictly apart.

    Two adjacent rows cannot tell a crossing from a touch that returns to the same side.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._fast_above: bool | None = None

    def seed(self, fast: float, slow: float) -> None:
        """Adopt an earlier bar's ordering, so the run's first bar can see a crossing."""
        if self._fast_above is None and fast != slow:
            self._fast_above = fast > slow

    def update(self, fast: float, slow: float) -> int:
        """+1 when the fast line crossed above on this bar, -1 below, 0 for no crossing."""
        if fast == slow:
            return 0  # A touch is not a reversal

        fast_above = fast > slow
        previous, self._fast_above = self._fast_above, fast_above
        if previous is None or previous == fast_above:
            return 0
        return 1 if fast_above else -1


class CrossRule(Rule):
    """Base for rules that fire on two lines swapping places."""

    lookback = 2  # Only to seed the tracker on the run's first bar
    fast_column: str = ""
    slow_column: str = ""
    # Decimals to compare at, None for exact. Only suits lines quoted in price ticks.
    precision: int | None = 2

    def reset(self) -> None:
        self._tracker = _CrossTracker()

    def _read(self, row) -> tuple[float, float]:
        fast = float(row[self.fast_column])
        slow = float(row[self.slow_column])
        if self.precision is None:
            return fast, slow
        return round(fast, self.precision), round(slow, self.precision)

    def _cross(self, history: DataFrame) -> int:
        """The crossing direction on today's bar. An equal bar must not touch the tracker."""
        fast, slow = self._read(history.iloc[-1])

        if fast == slow:
            return 0

        if len(history) >= 2:
            self._tracker.seed(*self._read(history.iloc[-2]))

        return self._tracker.update(fast, slow)


# ── Combinators ───────────────────────────────────────────────

class Decay(Rule):
    """Hold an event rule's opinion for a few bars, fading it geometrically.

    Lets several event rules agree within `half_life` bars instead of only on the same bar.
    Wrap a rule once and share the wrapper: two wrappers evaluate it twice per bar.
    """

    def __init__(self, rule: Rule, half_life: float = 3.0, floor: float = 0.05) -> None:
        if half_life <= 0:
            raise ValueError("A Decay needs a positive half_life; an opinion cannot fade in no time.")
        self._rule = rule  # Before super(), which calls reset()
        self._factor = 0.5 ** (1.0 / half_life)
        self._floor = floor
        self.name = rule.name
        self.required_columns = rule.required_columns
        self.warmup = rule.warmup
        self.lookback = rule.lookback
        super().__init__()

    def reset(self) -> None:
        self._held = 0.0
        self._rule.reset()

    def bias(self, history: DataFrame) -> float:
        # Called every bar, so a wrapped cross tracker never skips one
        fresh = self._rule.bias(history)
        if fresh != 0.0:
            self._held = fresh
        else:
            self._held *= self._factor
            if abs(self._held) < self._floor:
                self._held = 0.0
        return self._held


# ── Trend rules (gate) ────────────────────────────────────────

class SMATrend(Rule):
    """Distance of the close from a long moving average, graded so the gate does not flicker."""

    def __init__(self, length: int = 60, band: float = 0.05) -> None:
        self.length = length
        self.band = band  # Distance from the average that counts as a full opinion
        self.name = f"SMA {length} trend"
        self.required_columns = ['Close', f'SMA_{length}']
        self.warmup = length
        super().__init__()

    def bias(self, history: DataFrame) -> float:
        curr = history.iloc[-1]
        average = float(curr[f'SMA_{self.length}'])
        if average <= 0:
            return 0.0
        distance = float(curr['Close']) / average - 1
        return max(-1.0, min(1.0, distance / self.band))


class MACDZeroLine(Rule):
    """How far the MACD line sits from zero, in its own standard deviations."""

    name = "MACD zero line"
    required_columns = ['MACD_z']
    warmup = 85  # 26 rows for the MACD line, then the 60-row scale window

    def __init__(self, full: float = 2.0) -> None:
        self.full = full  # Standard deviations that count as a full opinion
        super().__init__()

    def bias(self, history: DataFrame) -> float:
        z = float(history['MACD_z'].iloc[-1])
        return max(-1.0, min(1.0, z / self.full))


# ── Entry rules (trigger) ─────────────────────────────────────

class RSIReversal(Rule):
    """Oversold favours a bounce, overbought a pullback."""

    name = "RSI reversal"
    required_columns = ['RSI']
    warmup = 14

    def __init__(self, oversold: float = 35, overbought: float = 70) -> None:
        self.oversold = oversold
        self.overbought = overbought
        super().__init__()

    def bias(self, history: DataFrame) -> float:
        rsi = round(float(history['RSI'].iloc[-1]), 2)
        if rsi < self.oversold:
            return 1.0
        if rsi > self.overbought:
            return -1.0
        return 0.0


class StochCross(CrossRule):
    """A K/D crossing, counted only at the extremes: golden cross at lows, death cross at highs."""

    name = "KD cross"
    required_columns = ['STOCH_K', 'STOCH_D']
    warmup = 13  # A 9-bar range, then two 3-bar smoothings
    fast_column = 'STOCH_K'
    slow_column = 'STOCH_D'

    def __init__(self, low: float = 30, high: float = 70) -> None:
        self.low = low
        self.high = high
        super().__init__()

    def bias(self, history: DataFrame) -> float:
        direction = self._cross(history)
        if direction == 0:
            return 0.0

        k = float(history['STOCH_K'].iloc[-1])
        if direction > 0 and k < self.low:
            return 1.0
        if direction < 0 and k > self.high:
            return -1.0
        return 0.0


class EMACross(CrossRule):
    """Fast/slow EMA crossing."""

    def __init__(self, fast: int = 5, slow: int = 20) -> None:
        self.fast_column = f'EMA_{fast}'
        self.slow_column = f'EMA_{slow}'
        self.name = f"EMA {fast}x{slow} cross"
        self.required_columns = [self.fast_column, self.slow_column]
        self.warmup = slow
        super().__init__()

    def bias(self, history: DataFrame) -> float:
        return float(self._cross(history))


# ── Exit rules ────────────────────────────────────────────────

class BollingerBand(Rule):
    """Reaching a band is a stretched move and a reason to exit."""

    name = "Bollinger band"
    required_columns = ['Close', 'BB_U', 'BB_L']
    warmup = 20

    def bias(self, history: DataFrame) -> float:
        curr = history.iloc[-1]
        close = float(curr['Close'])
        if close >= float(curr['BB_U']):
            return -1.0
        if close <= float(curr['BB_L']):
            return 1.0
        return 0.0


class MACDSignalCross(CrossRule):
    """The MACD line crossing its signal line.

    An event rather than the histogram's sign, which holds every bar and would outvote
    `BollingerBand` in the same bucket.
    """

    name = "MACD signal cross"
    required_columns = ['MACD_dif', 'MACD_dem']
    warmup = 34  # The slow EMA, then the 9-bar signal line
    fast_column = 'MACD_dif'
    slow_column = 'MACD_dem'
    precision = None  # Both lines scale with the price

    def bias(self, history: DataFrame) -> float:
        return float(self._cross(history))
