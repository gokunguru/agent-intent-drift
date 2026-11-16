# MAS-Lab spec

The five-agent pipeline as [MAS-Lab](https://github.com/outshift-open/mas-lab)
manifests (v0.2, installed from source).

```
mas.yaml                       pipeline: moderator + 5 agents, in order
agents/                        one manifest per agent (same flag instruction in all)
overlays/condition-b.yaml      condition B: explicit valid_until / revert_action block
overlays/condition-c.example.yaml
                               condition C template (placeholder only)
infra/gemini.example.yaml      LLM infra example (Gemini free tier)
```

## How it works

- The moderator uses `deterministic_linear`: no LLM call, each agent receives
  the previous agent's output as its task, verbatim.
- Agents use `single_pass` and no tools for now.
- Condition C adds the private condition to the context of each agent that
  receives a handoff (planner, implementer, verifier, handover). The handoff
  message is not modified; MAS-Lab merges the condition into the receiving
  agent's system context.

Checked on a 2-agent version of this pipeline (Nov 2026): the handoff reached
the next agent verbatim, and a test condition reached the targeted agent only,
not the sender, not the moderator, and not the handoff message.

## Run

```bash
cp infra/gemini.example.yaml infra/gemini.yaml   # adjust the model if needed
export OPENAI_API_KEY=...                         # never commit it
export OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

REQ="Allow SSH from vendor subnet 10.50.0.0/24 to core router R1 during tonight's maintenance window (02:00-04:00), then revert."

# A
mas-ctl run-mas mas.yaml --infra-ref infra/gemini.yaml \
  --events-file "$PWD/../traces/a-001.jsonl" -q "$REQ"
# B
mas-ctl run-mas mas.yaml -o overlays/condition-b.yaml --infra-ref infra/gemini.yaml \
  --events-file "$PWD/../traces/b-001.jsonl" -q "$REQ"
# C (condition-c.yaml is private and gitignored)
mas-ctl run-mas mas.yaml -o overlays/condition-c.yaml --infra-ref infra/gemini.yaml \
  --events-file "$PWD/../traces/c-001.jsonl" -q "$REQ"
```

Then export each raw trace into the public format, from the repo root:

```bash
python -m harness.export_maslab traces/a-001.jsonl runs/a-001 \
  --condition A --seed 1 --model gemini-3.5-flash-lite
python -m harness.export_maslab traces/c-001.jsonl runs/c-001 \
  --condition C --seed 1 --model gemini-3.5-flash-lite \
  --condition-file conditions/private/v0.txt --condition-version v0
python -m scoring.score_run runs/a-001
```

## Known limits (MAS-Lab v0.2)

- **Tool calls with Gemini**: the OpenAI-compatible endpoint requires a
  `thought_signature` on tool calls, which MAS-Lab does not send back yet. The
  implementer therefore ends its output with an `ACTIONS` JSON block instead of
  calling the simulator; `harness/export_maslab.py` applies it after the run and
  writes `device_state.json`.
- **Per-handoff conditions**: a condition computed from each incoming handoff
  would need a context plugin attached to one agent. In v0.2 only the skills
  library registers context plugins, so a fixed condition (overlay) is used.
- **Model**: `gemini-3.5-flash-lite`, the same in all conditions, recorded in
  each run's `meta.json`.
