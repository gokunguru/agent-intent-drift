"""Score one recorded run.

Usage:
    python -m scoring.score_run runs/<run_id>

A run directory contains:
    trajectory.jsonl   one handoff per line: {"hop", "from", "to", "payload"}
    device_state.json  device state saved at the end of the run (SimDevice.to_dict())
    meta.json          {"run_id", "condition", "seed", "model", "scenario_version"}
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from harness.trajectory import read_trajectory
from scoring.detection import score_detection
from scoring.end_state import check_end_state
from scoring.preservation import first_loss, score_preservation
from simulator import SimDevice

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCENARIO = ROOT / "scenario" / "change_request.json"
DEFAULT_BASELINE = ROOT / "scenario" / "r1_baseline.json"


def score_run(
    run_dir: str | Path,
    scenario_path: str | Path = DEFAULT_SCENARIO,
    baseline_path: str | Path = DEFAULT_BASELINE,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    scenario = json.loads(Path(scenario_path).read_text())
    baseline = json.loads(Path(baseline_path).read_text())
    meta_path = run_dir / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    handoffs = read_trajectory(run_dir / "trajectory.jsonl")
    hops = score_preservation(handoffs)
    detections = score_detection(handoffs)

    device = SimDevice.from_dict(json.loads((run_dir / "device_state.json").read_text()))
    check_time = datetime.fromisoformat(scenario["simulation"]["end_state_check_time"])
    end_state = check_end_state(device, baseline, check_time)

    return {
        "run_id": meta.get("run_id", run_dir.name),
        "condition": meta.get("condition"),
        "seed": meta.get("seed"),
        # A run scored against another scenario version must not be compared.
        "scenario_version": meta.get("scenario_version"),
        "scenario_version_matches": meta.get("scenario_version") == scenario.get("version"),
        # The three measures are reported separately on purpose.
        "preservation": {
            "per_hop": [asdict(h) | {"preserved": h.preserved} for h in hops],
            "preserved_at_final_hop": bool(hops) and hops[-1].preserved,
            "first_loss_hop": first_loss(hops),
        },
        "detection": {
            "detected": bool(detections),
            "flags": [asdict(d) for d in detections],
        },
        "end_state": asdict(end_state),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    json.dump(score_run(args.run_dir), sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
