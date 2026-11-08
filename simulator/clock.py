"""Injectable simulated clock. Time only moves when the harness moves it."""

from __future__ import annotations

from datetime import datetime, timedelta


class SimClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance_to(self, target: datetime) -> None:
        if target < self._now:
            raise ValueError(f"clock cannot go backwards ({target} < {self._now})")
        self._now = target

    def advance(self, delta: timedelta) -> None:
        self.advance_to(self._now + delta)
