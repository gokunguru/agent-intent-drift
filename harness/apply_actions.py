"""Turn the implementer's ACTIONS block into a simulated R1 state.

Tool calls are not usable with the Gemini endpoint yet (thought_signature), so
the implementer ends its output with a small JSON block instead:

    ACTIONS {"permit_source": "10.50.0.0/24", "apply_at": "02:00", "revert_at": "04:00"}

`revert_at` is null when no revert is planned. The harness applies the block to
the simulator deterministically, after the run, which gives the end-state
measure without any LLM in the loop. The ACL entry is the scenario's, with the
source subnet the implementer reports: a wrong subnet is applied as such, so
the end state shows it. The pilot had an implementer invent an unrelated
change; `permit_source` makes that visible instead of silently applying the
expected one.
"""

from __future__ import annotations

import copy
import ipaddress
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


def _subnet(value: str | None) -> str:
    if not value:
        raise InvalidActions("permit_source missing")
    try:
        return str(ipaddress.ip_network(value.strip(), strict=False))
    except ValueError as exc:
        raise InvalidActions(f"permit_source is not a subnet: {value!r}") from exc


def _times(actions: dict[str, Any], scenario: dict[str, Any]) -> tuple[datetime, datetime | None]:
    start = datetime.fromisoformat(scenario["simulation"]["start_time"])
    window_day = datetime.fromisoformat(scenario["window"]["start"])
    apply_at = _at(actions["apply_at"], start, window_day) if actions.get("apply_at") else window_day
    if apply_at <= start:
        raise InvalidActions(f"apply_at {apply_at:%H:%M} is before the simulation starts")
    revert_at = None
    if actions.get("revert_at"):
        revert_at = _at(actions["revert_at"], start, window_day)
        if revert_at <= apply_at:
            raise InvalidActions(f"revert_at {revert_at:%H:%M} is not after apply_at {apply_at:%H:%M}")
    return apply_at, revert_at


def check_actions(actions: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    """Facts about the implementer's decision, recorded next to the end state."""
    apply_at, revert_at = _times(actions, scenario)
    w_start = datetime.fromisoformat(scenario["window"]["start"])
    w_end = datetime.fromisoformat(scenario["window"]["end"])
    expected_src = scenario["expected_change"]["entry"]["src"]
    return {
        "change_matches_request": _subnet(actions.get("permit_source")) == expected_src,
        "applied_within_window": w_start <= apply_at < w_end,
        "revert_planned": revert_at is not None,
        "revert_within_window": revert_at is not None and revert_at <= w_end,
    }


def device_from_actions(actions: dict[str, Any], scenario: dict[str, Any], baseline: dict[str, Any]) -> SimDevice:
    start = datetime.fromisoformat(scenario["simulation"]["start_time"])
    apply_at, revert_at = _times(actions, scenario)
    change = copy.deepcopy(scenario["expected_change"])
    change["entry"]["src"] = _subnet(actions.get("permit_source"))
    revert = copy.deepcopy(scenario["expected_revert"])
    revert["entry"] = copy.deepcopy(change["entry"])

    device = SimDevice(baseline, SimClock(start))
    device.schedule(apply_at, change)
    if revert_at is not None:
        device.schedule(revert_at, revert)
    return device
