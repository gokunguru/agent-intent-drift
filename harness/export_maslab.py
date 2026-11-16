"""Export a raw MAS-Lab events file into the public run format.

Raw MAS-Lab traces hold full prompts, including the private condition of
condition C, so they stay out of git (traces/ is gitignored). This script keeps
only what the public record needs:

  trajectory.jsonl  one handoff per line: what each agent wrote, and whether the
                    next agent received it verbatim
  meta.json         run metadata, the condition's public record (version,
                    SHA-256, length) and the SHA-256 of the raw trace
  device_state.json copied as is, if given

Usage:
    python -m harness.export_maslab traces/run-001.jsonl runs/run-001 \\
        --condition A --seed 1 --model gemini-3.5-flash-lite
    python -m harness.export_maslab traces/run-002.jsonl runs/run-002 \\
        --condition C --seed 1 --model gemini-3.5-flash-lite \\
        --condition-file conditions/private/v0.txt --condition-version v0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from harness.conditions import AGENTS, CONDITIONS
from harness.trajectory import write_trajectory
from integrations.aurora import ReceiverCondition

ROOT = Path(__file__).resolve().parent.parent
FINAL_RECIPIENT = "next_shift"


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def read_events(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def agent_io(events: list[dict[str, Any]], agents: list[str]) -> dict[str, dict[str, str | None]]:
    """For each agent: the input it received and the final output it wrote."""
    io: dict[str, dict[str, str | None]] = {a: {"input": None, "output": None} for a in agents}
    for e in events:
        agent = e.get("agent_id")
        if agent not in io:
            continue
        if e.get("kind") == "execution_start" and io[agent]["input"] is None:
            io[agent]["input"] = _text(e.get("input"))
        elif e.get("kind") == "llm_call_end":
            io[agent]["output"] = _text(e.get("output"))  # last call wins
    missing = [a for a in agents if io[a]["output"] is None]
    if missing:
        raise ValueError(f"no llm_call_end output for: {', '.join(missing)}")
    return io


def build_trajectory(io: dict[str, dict[str, str | None]], agents: list[str]) -> list[dict[str, Any]]:
    handoffs = []
    for i, sender in enumerate(agents):
        receiver = agents[i + 1] if i + 1 < len(agents) else FINAL_RECIPIENT
        payload = io[sender]["output"] or ""
        received = io[receiver]["input"] if receiver in io else None
        handoffs.append({
            "hop": i + 1,
            "from": sender,
            "to": receiver,
            "payload": payload,
            # None for the last hop: nobody inside the run receives it.
            "delivered_verbatim": None if received is None else received.strip() == payload.strip(),
        })
    return handoffs


def export_run(
    events_path: str | Path,
    out_dir: str | Path,
    *,
    condition: str,
    seed: int | None,
    model: str,
    run_id: str | None = None,
    condition_file: str | Path | None = None,
    condition_version: str | None = None,
    device_state: str | Path | None = None,
    scenario_path: str | Path = ROOT / "scenario" / "change_request.json",
    agents: list[str] = AGENTS,
) -> dict[str, Any]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}")
    needs_private = CONDITIONS[condition].private_condition
    if needs_private and not (condition_file and condition_version):
        raise ValueError("condition C needs --condition-file and --condition-version")
    if not needs_private and condition_file:
        raise ValueError(f"condition {condition} takes no private condition")

    events_path, out_dir = Path(events_path), Path(out_dir)
    io = agent_io(read_events(events_path), agents)
    handoffs = build_trajectory(io, agents)

    scenario = json.loads(Path(scenario_path).read_text())
    meta: dict[str, Any] = {
        "run_id": run_id or out_dir.name,
        "condition": condition,
        "seed": seed,
        "model": model,
        "scenario_version": scenario.get("version"),
        "exported_from": "mas-lab events",
        "raw_trace_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest(),
    }

    if needs_private:
        private = ReceiverCondition.from_file(condition_file, condition_version)
        meta.update(private.public_record())
        # The condition must never reach the public files.
        private.assert_not_in(json.dumps(handoffs, ensure_ascii=False), json.dumps(meta))

    out_dir.mkdir(parents=True, exist_ok=True)
    write_trajectory(out_dir / "trajectory.jsonl", handoffs)
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    if device_state:
        shutil.copyfile(device_state, out_dir / "device_state.json")
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a MAS-Lab events file into runs/<run_id>/.")
    parser.add_argument("events")
    parser.add_argument("out_dir")
    parser.add_argument("--condition", required=True, choices=sorted(CONDITIONS))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--condition-file", help="private condition text (condition C only)")
    parser.add_argument("--condition-version")
    parser.add_argument("--device-state")
    args = parser.parse_args(argv)
    meta = export_run(
        args.events, args.out_dir,
        condition=args.condition, seed=args.seed, model=args.model, run_id=args.run_id,
        condition_file=args.condition_file, condition_version=args.condition_version,
        device_state=args.device_state,
    )
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
