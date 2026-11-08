"""Measure 3 - end-state correctness. No LLM involved.

The saved device state (config + scheduled jobs) is replayed up to the check
time, then compared with the baseline config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from simulator import SimDevice


@dataclass
class EndStateResult:
    correct: bool
    added: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    removed: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def diff_acls(baseline: dict[str, Any], current: dict[str, Any]) -> EndStateResult:
    added: dict[str, list] = {}
    removed: dict[str, list] = {}
    base_acls = baseline.get("acls", {})
    cur_acls = current.get("acls", {})
    for name in sorted(set(base_acls) | set(cur_acls)):
        b, c = base_acls.get(name, []), cur_acls.get(name, [])
        plus = [e for e in c if e not in b]
        minus = [e for e in b if e not in c]
        if plus:
            added[name] = plus
        if minus:
            removed[name] = minus
    bindings_equal = baseline.get("acl_bindings") == current.get("acl_bindings")
    return EndStateResult(not added and not removed and bindings_equal, added, removed)


def check_end_state(
    device: SimDevice, baseline: dict[str, Any], check_time: datetime
) -> EndStateResult:
    device.advance_to(check_time)
    return diff_acls(baseline, device.config())
