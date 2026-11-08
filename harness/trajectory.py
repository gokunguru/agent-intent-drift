"""Read/write handoff trajectories as JSONL (one handoff per line)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_KEYS = {"hop", "from", "to", "payload"}


def write_trajectory(path: str | Path, handoffs: list[dict[str, Any]]) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        for h in handoffs:
            missing = REQUIRED_KEYS - h.keys()
            if missing:
                raise ValueError(f"handoff {h.get('hop')} missing keys: {sorted(missing)}")
            f.write(json.dumps(h, ensure_ascii=False) + "\n")


def read_trajectory(path: str | Path) -> list[dict[str, Any]]:
    handoffs = []
    with Path(path).open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            h = json.loads(line)
            missing = REQUIRED_KEYS - h.keys()
            if missing:
                raise ValueError(f"line {line_no}: missing keys {sorted(missing)}")
            handoffs.append(h)
    return sorted(handoffs, key=lambda h: h["hop"])
