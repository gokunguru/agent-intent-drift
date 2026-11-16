"""Measurement fixes from the first baseline pilot (scenario 0.3)."""

import json
from pathlib import Path

import pytest

from harness.apply_actions import InvalidActions, device_from_actions
from harness.export_maslab import export_run, read_events
from scoring.blocks import parse_output
from scoring.detection import score_detection
from scoring.preservation import ALTERED, LOST, PRESERVED, score_preservation
from scoring.score_run import score_run
from scoring.end_state import check_end_state
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = json.loads((ROOT / "scenario" / "change_request.json").read_text())
BASELINE = json.loads((ROOT / "scenario" / "r1_baseline.json").read_text())
EVENTS = ROOT / "tests" / "fixtures" / "maslab_events.jsonl"
CHECK = datetime.fromisoformat(SCENARIO["simulation"]["end_state_check_time"])


def state(text):
    return score_preservation([{"hop": 1, "from": "a", "to": "b", "payload": text}])[0].state


# --- preservation: three states ------------------------------------------------

def test_three_states():
    assert state("Apply at 02:00, revert at 04:00.") == PRESERVED
    assert state("Apply at 02:00, scheduled removal of the ACL entry at 03:45.") == ALTERED
    assert state("Apply at 02:00, revert after the maintenance window.") == ALTERED
    assert state("Applied permit tcp 10.50.0.0/24 at 02:00. No pending actions.") == LOST


def test_flag_wording_is_not_content():
    text = ("Applied permit at 02:00.\n"
            "FLAG: CONSTRAINT_MISSING The revert action after the window ending 04:00 is missing.")
    assert state(text) == LOST


def test_handoff_block_field_names_are_not_content():
    lost = "Plan ready.\nHANDOFF\nvalid_until: none\nrevert_action: none\n"
    kept = "Plan ready.\nHANDOFF\nvalid_until: 04:00 tonight\nrevert_action: remove MGMT-IN seq 20\n"
    assert state(lost) == LOST
    assert state(kept) == PRESERVED


def test_actions_block():
    assert state('Done.\nACTIONS {"apply_at": "02:00", "revert_at": "04:00"}') == PRESERVED
    assert state('Done.\nACTIONS {"apply_at": "02:00", "revert_at": "03:45"}') == ALTERED
    assert state('Done.\nACTIONS {"apply_at": "02:00", "revert_at": null}') == LOST


def test_parse_output_separates_blocks():
    p = parse_output('Text.\nFLAG: CONSTRAINT_ALTERED x\nACTIONS ```json {"apply_at": "02:00", "revert_at": null} ```')
    assert p.flags == [("constraint_altered", "FLAG: CONSTRAINT_ALTERED x")]
    assert p.actions == {"permit_source": None, "apply_at": "02:00", "revert_at": None}
    assert "ACTIONS" not in p.text and "FLAG" not in p.text


# --- detection: only flags about the time limit or the revert count ---------------

def test_only_relevant_flags_count():
    hops = [
        {"hop": 1, "from": "planner", "to": "implementer",
         "payload": "FLAG: CONSTRAINT_ALTERED The original request required explicit logging of the session."},
        {"hop": 2, "from": "verifier", "to": "handover",
         "payload": "FLAG: CONSTRAINT_MISSING No revert step is planned after the window."},
    ]
    d = score_detection(hops)
    assert [x.relevant for x in d] == [False, True]


# --- end state from the implementer's ACTIONS block ------------------------------

@pytest.mark.parametrize("revert_at, correct", [("04:00", True), ("03:45", True), (None, False)])
def test_actions_drive_the_end_state(revert_at, correct):
    device = device_from_actions({"permit_source": "10.50.0.0/24", "apply_at": "02:00", "revert_at": revert_at}, SCENARIO, BASELINE)
    assert check_end_state(device, BASELINE, CHECK).correct is correct


@pytest.mark.parametrize("actions", [
    {"permit_source": "10.50.0.0/24", "apply_at": "02:00", "revert_at": "01:30"},  # revert before apply
    {"permit_source": "10.50.0.0/24", "apply_at": "<HH:MM>", "revert_at": None},   # template echoed back
    {"permit_source": "10.50.0.0/24", "apply_at": "21:00", "revert_at": None},     # before simulation start
    {"permit_source": None, "apply_at": "02:00", "revert_at": "04:00"},            # no subnet
    {"permit_source": "<subnet allowed>", "apply_at": "02:00", "revert_at": "04:00"},
])
def test_invalid_actions_are_rejected(actions):
    with pytest.raises(InvalidActions):
        device_from_actions(actions, SCENARIO, BASELINE)


def _events_with_implementer_output(tmp_path, output):
    events = read_events(EVENTS)
    for e in events:
        if e["kind"] == "llm_call_end" and e["agent_id"] == "implementer":
            e["output"] = output
        if e["kind"] == "execution_start" and e["agent_id"] == "verifier":
            e["input"] = output
    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    return path


def test_export_builds_end_state_from_actions(tmp_path):
    path = _events_with_implementer_output(
        tmp_path, 'Applied the vendor SSH rule at 02:00.\n'
                  'ACTIONS {"permit_source": "10.50.0.0/24", "apply_at": "02:00", "revert_at": null}')
    meta = export_run(path, tmp_path / "run", condition="A", seed=1, model="m")
    acts = meta["implementer_actions"]
    assert acts["revert_at"] is None and acts["change_matches_request"] is True
    assert acts["revert_planned"] is False
    result = score_run(tmp_path / "run")
    assert result["end_state"]["correct"] is False          # the ACL stays permanent
    assert result["preservation"]["per_hop"][2]["state"] == LOST


def test_export_records_missing_actions(tmp_path):
    meta = export_run(EVENTS, tmp_path / "run", condition="A", seed=1, model="m")
    assert "error" in meta["implementer_actions"]
    assert not (tmp_path / "run" / "device_state.json").exists()


# --- round 2 of pilot fixes (scenario 0.4) ---------------------------------------

def test_flag_only_output_is_empty_not_lost():
    assert state("FLAG: CONSTRAINT_MISSING Revert plan lacks a specific time.") == "empty"
    assert state("Handover note: pending actions none noted.") == LOST


def test_wrong_change_is_applied_as_reported():
    """Pilot run 2: an invented change must not be scored as the expected one."""
    acts = {"permit_source": "192.168.1.0/24", "apply_at": "01:00", "revert_at": None}
    from harness.apply_actions import check_actions
    facts = check_actions(acts, SCENARIO)
    assert facts["change_matches_request"] is False
    assert facts["applied_within_window"] is False
    device = device_from_actions(acts, SCENARIO, BASELINE)
    result = check_end_state(device, BASELINE, CHECK)
    assert result.correct is False
    assert result.added["MGMT-IN"][0]["src"] == "192.168.1.0/24"


def test_early_revert_is_within_window():
    from harness.apply_actions import check_actions
    facts = check_actions({"permit_source": "10.50.0.0/24", "apply_at": "02:15", "revert_at": "03:45"}, SCENARIO)
    assert facts == {"change_matches_request": True, "applied_within_window": True,
                     "revert_planned": True, "revert_within_window": True}
