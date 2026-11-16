"""Turn the implementer's ACTIONS block into a simulated R1 state.

Tool calls are not usable with the Gemini endpoint yet (thought_signature), so
the implementer ends its output with a small JSON block instead:

    ACTIONS {"apply_at": "02:00", "revert_at": "04:00"}

`revert_at` is null when no revert is planned. The harness applies the block to
the simulator deterministically, after the run, which gives the end-state
measure without any LLM in the loop. The change and the revert themselves come
from the scenario, so only the timing is the implementer's decision.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from simulator import SimClock, SimDevice

ACTIONS_AGENT = "implementer"
HHMM = re.compile(r"^\s*([01]?\d|2[0-3])[:h.]([0-5]\d)\s*$")


class InvalidActions(ValueError):
    pass


def _at(value: str, evening: datetime, night: datetime) -> datetime:
    """HH:MM "tonight": 12:00-23:59 is the evening before, 00:00-11:59 the window day."""
    m = HHMM.match(value)
    if not m:
        raise InvalidActions(f"time not in HH:MM form: {value!r}")
    hour, minute = int(m.group(1)), int(m.group(2))
    day = evening if hour >= 12 else night
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def device_from_actions(actions: dict[str, Any], scenario: dict[str, Any], baseline: dict[str, Any]) -> SimDevice:
    start = datetime.fromisoformat(scenario["simulation"]["start_time"])
    window_day = datetime.fromisoformat(scenario["window"]["start"])
    device = SimDevice(baseline, SimClock(start))

    apply_at = _at(actions["apply_at"], start, window_day) if actions.get("apply_at") else window_day
    if apply_at <= start:
        raise InvalidActions(f"apply_at {apply_at:%H:%M} is before the simulation starts")
    device.schedule(apply_at, scenario["expected_change"])

    if actions.get("revert_at"):
        revert_at = _at(actions["revert_at"], start, window_day)
        if revert_at <= apply_at:
            raise InvalidActions(f"revert_at {revert_at:%H:%M} is not after apply_at {apply_at:%H:%M}")
        device.schedule(revert_at, scenario["expected_revert"])
    return device
