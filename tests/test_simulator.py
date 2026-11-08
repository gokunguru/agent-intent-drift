import json
from datetime import datetime
from pathlib import Path

import pytest

from simulator import SimClock, SimDevice, UnknownOperation

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = json.loads((ROOT / "scenario" / "change_request.json").read_text())
BASELINE = ROOT / "scenario" / "r1_baseline.json"
T = datetime.fromisoformat


def make_device(start="2026-11-10T02:00:00"):
    return SimDevice.from_file(BASELINE, SimClock(T(start)))


def test_clock_cannot_go_backwards():
    clock = SimClock(T("2026-11-10T02:00:00"))
    with pytest.raises(ValueError):
        clock.advance_to(T("2026-11-10T01:00:00"))


def test_change_without_revert_stays_permanent():
    device = make_device()
    device.apply(SCENARIO["expected_change"])
    device.advance_to(T("2026-11-10T04:05:00"))
    assert SCENARIO["expected_change"]["entry"] in device.config()["acls"]["MGMT-IN"]


def test_scheduled_revert_runs_at_its_time():
    device = make_device()
    device.apply(SCENARIO["expected_change"])
    device.schedule(T("2026-11-10T04:00:00"), SCENARIO["expected_revert"])
    device.advance_to(T("2026-11-10T03:59:00"))
    assert SCENARIO["expected_change"]["entry"] in device.config()["acls"]["MGMT-IN"]
    device.advance_to(T("2026-11-10T04:05:00"))
    assert SCENARIO["expected_change"]["entry"] not in device.config()["acls"]["MGMT-IN"]
    assert device.log[-1]["time"] == "2026-11-10T04:00:00"


def test_cancelled_job_does_not_run():
    device = make_device()
    device.apply(SCENARIO["expected_change"])
    job = device.schedule(T("2026-11-10T04:00:00"), SCENARIO["expected_revert"])
    assert device.cancel(job)
    device.advance_to(T("2026-11-10T04:05:00"))
    assert SCENARIO["expected_change"]["entry"] in device.config()["acls"]["MGMT-IN"]


def test_schedule_in_the_past_is_rejected():
    device = make_device()
    with pytest.raises(ValueError):
        device.schedule(T("2026-11-10T01:00:00"), SCENARIO["expected_revert"])


def test_unknown_op_is_rejected():
    device = make_device()
    with pytest.raises(UnknownOperation):
        device.apply({"op": "reload"})


def test_round_trip_keeps_pending_jobs():
    device = make_device()
    device.apply(SCENARIO["expected_change"])
    device.schedule(T("2026-11-10T04:00:00"), SCENARIO["expected_revert"])
    restored = SimDevice.from_dict(json.loads(json.dumps(device.to_dict())))
    restored.advance_to(T("2026-11-10T04:05:00"))
    assert SCENARIO["expected_change"]["entry"] not in restored.config()["acls"]["MGMT-IN"]
