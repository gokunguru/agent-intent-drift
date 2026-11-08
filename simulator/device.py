"""Minimal JSON device-state simulator for R1.

The device never reverts anything on its own: a revert only happens if an
agent applied it directly or scheduled it with `schedule()`. That is what
makes end-state correctness a deterministic check.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from simulator.clock import SimClock


class UnknownOperation(ValueError):
    pass


@dataclass
class ScheduledJob:
    job_id: str
    at: datetime
    action: dict[str, Any]


class SimDevice:
    def __init__(self, config: dict[str, Any], clock: SimClock) -> None:
        self._config = copy.deepcopy(config)
        self.clock = clock
        self._jobs: list[ScheduledJob] = []
        self._next_job = 1
        self.log: list[dict[str, Any]] = []

    @classmethod
    def from_file(cls, path: str | Path, clock: SimClock) -> "SimDevice":
        return cls(json.loads(Path(path).read_text()), clock)

    @property
    def hostname(self) -> str:
        return self._config.get("hostname", "")

    def config(self) -> dict[str, Any]:
        return copy.deepcopy(self._config)

    def pending_jobs(self) -> list[ScheduledJob]:
        return list(self._jobs)

    # --- operations -------------------------------------------------------

    def apply(self, action: dict[str, Any]) -> None:
        op = action.get("op")
        acl_name = action.get("acl")
        entry = action.get("entry")
        if op == "add_acl_entry":
            acl = self._config.setdefault("acls", {}).setdefault(acl_name, [])
            if entry not in acl:
                acl.append(copy.deepcopy(entry))
                acl.sort(key=lambda e: e.get("seq", 0))
        elif op == "remove_acl_entry":
            acl = self._config.get("acls", {}).get(acl_name, [])
            if entry in acl:
                acl.remove(entry)
        else:
            raise UnknownOperation(f"unsupported op: {op!r}")
        self.log.append({"time": self.clock.now().isoformat(), "action": copy.deepcopy(action)})

    def schedule(self, at: datetime, action: dict[str, Any]) -> str:
        if at <= self.clock.now():
            raise ValueError("a scheduled job must be in the future")
        if action.get("op") not in {"add_acl_entry", "remove_acl_entry"}:
            raise UnknownOperation(f"unsupported op: {action.get('op')!r}")
        job_id = f"job-{self._next_job}"
        self._next_job += 1
        self._jobs.append(ScheduledJob(job_id, at, copy.deepcopy(action)))
        self._jobs.sort(key=lambda j: j.at)
        return job_id

    def cancel(self, job_id: str) -> bool:
        before = len(self._jobs)
        self._jobs = [j for j in self._jobs if j.job_id != job_id]
        return len(self._jobs) < before

    def advance_to(self, target: datetime) -> None:
        """Move time forward, running each due job at its own scheduled time."""
        while self._jobs and self._jobs[0].at <= target:
            job = self._jobs.pop(0)
            self.clock.advance_to(job.at)
            self.apply(job.action)
        self.clock.advance_to(target)

    # --- persistence (lets scoring replay the end state offline) ----------

    def to_dict(self) -> dict[str, Any]:
        return {
            "now": self.clock.now().isoformat(),
            "config": self.config(),
            "jobs": [
                {"job_id": j.job_id, "at": j.at.isoformat(), "action": copy.deepcopy(j.action)}
                for j in self._jobs
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimDevice":
        device = cls(data["config"], SimClock(datetime.fromisoformat(data["now"])))
        for job in data.get("jobs", []):
            device._jobs.append(
                ScheduledJob(job["job_id"], datetime.fromisoformat(job["at"]), job["action"])
            )
        device._jobs.sort(key=lambda j: j.at)
        device._next_job = len(device._jobs) + 1
        return device
