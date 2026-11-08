# MAS-Lab spec

Placeholder. The 5-agent pipeline (intake, planner, implementer, verifier,
handover) will be defined here as a MAS-Lab spec, with conditions A/B/C as
variants of the same spec.

To do after the first MAS-Lab test:
- agent definitions and shared prompts (including the flag instruction from `harness/conditions.py`)
- tool binding to `simulator/` (apply / schedule on R1)
- hook calling `HandoffLayer.on_handoff` at each handoff
- export of each run to `runs/<run_id>/` in the format read by `scoring/score_run.py`
