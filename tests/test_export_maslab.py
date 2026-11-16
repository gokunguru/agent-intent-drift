import json
from pathlib import Path

import pytest

from harness.conditions import AGENTS, FLAG_INSTRUCTION
from harness.export_maslab import FailedRun, export_run, read_events
from harness.trajectory import read_trajectory
from integrations.aurora import RECEIVING_AGENTS, PrivateConditionLeak, ReceiverCondition
from scoring.score_run import score_run

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
EVENTS = FIXTURES / "maslab_events.jsonl"
CONDITION_TEXT = "TEST-ONLY condition text."


def test_export_builds_one_hop_per_agent(tmp_path):
    export_run(EVENTS, tmp_path / "run", condition="A", seed=1, model="test-model")
    hops = read_trajectory(tmp_path / "run" / "trajectory.jsonl")
    assert [h["from"] for h in hops] == AGENTS
    assert hops[-1]["to"] == "next_shift"
    assert all(h["delivered_verbatim"] for h in hops[:-1])
    assert hops[-1]["delivered_verbatim"] is None


def test_export_detects_a_modified_handoff(tmp_path):
    events = read_events(EVENTS)
    for e in events:
        if e["kind"] == "execution_start" and e["agent_id"] == "planner":
            e["input"] += " (edited in transit)"
    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    export_run(path, tmp_path / "run", condition="A", seed=1, model="test-model")
    hops = read_trajectory(tmp_path / "run" / "trajectory.jsonl")
    assert hops[0]["delivered_verbatim"] is False


def test_exported_run_is_scored(tmp_path):
    run = tmp_path / "run"
    export_run(EVENTS, run, condition="A", seed=1, model="test-model",
               device_state=FIXTURES / "run_drift" / "device_state.json")
    result = score_run(run)
    assert result["preservation"]["first_loss_hop"] == 3
    assert result["end_state"]["correct"] is False
    assert result["scenario_version_matches"] is True


def test_exported_run_without_simulator_has_no_end_state(tmp_path):
    export_run(EVENTS, tmp_path / "run", condition="A", seed=1, model="test-model")
    assert score_run(tmp_path / "run")["end_state"] is None


def test_condition_c_publishes_hash_not_text(tmp_path):
    cond = tmp_path / "condition.txt"
    cond.write_text(CONDITION_TEXT)
    meta = export_run(EVENTS, tmp_path / "run", condition="C", seed=1, model="test-model",
                      condition_file=cond, condition_version="v0")
    expected = ReceiverCondition("v0", CONDITION_TEXT).public_record()
    assert {k: meta[k] for k in expected} == expected
    for f in (tmp_path / "run").iterdir():
        assert CONDITION_TEXT not in f.read_text()


def test_condition_leak_is_refused(tmp_path):
    cond = tmp_path / "condition.txt"
    cond.write_text("revert at 04:00")  # appears in an agent output
    with pytest.raises(PrivateConditionLeak):
        export_run(EVENTS, tmp_path / "run", condition="C", seed=1, model="test-model",
                   condition_file=cond, condition_version="v0")
    assert not (tmp_path / "run").exists()


def test_condition_arguments_match_the_condition(tmp_path):
    cond = tmp_path / "condition.txt"
    cond.write_text(CONDITION_TEXT)
    with pytest.raises(ValueError):
        export_run(EVENTS, tmp_path / "a", condition="C", seed=1, model="m")
    with pytest.raises(ValueError):
        export_run(EVENTS, tmp_path / "b", condition="A", seed=1, model="m",
                   condition_file=cond, condition_version="v0")


def test_failed_llm_call_is_not_a_lost_constraint(tmp_path):
    events = read_events(EVENTS)
    for e in events:
        if e["kind"] == "llm_call_end" and e["agent_id"] == "intake":
            e["output"] = "LLM request failed: HTTP 401 (authentication/authorization): API key not valid."
    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    with pytest.raises(FailedRun):
        export_run(path, tmp_path / "run", condition="A", seed=1, model="test-model")
    assert not (tmp_path / "run").exists()


# --- spec/ stays consistent with the equivalence rule -------------------------

def test_every_agent_gets_the_same_flag_instruction():
    for agent in AGENTS:
        text = (ROOT / "spec" / "agents" / f"{agent}.yaml").read_text()
        assert FLAG_INSTRUCTION in text, agent


def test_condition_c_targets_receiving_agents_only():
    text = (ROOT / "spec" / "overlays" / "condition-c.example.yaml").read_text()
    for agent in RECEIVING_AGENTS:
        assert f"      {agent}:\n" in text
    assert "      intake:\n" not in text
    assert "<PRIVATE CONDITION" in text


def test_private_files_are_gitignored():
    ignored = (ROOT / ".gitignore").read_text().splitlines()
    for entry in ("traces/", "conditions/private/", "spec/overlays/condition-c.yaml"):
        assert entry in ignored
