"""The three conditions. Only the handoff mechanism differs between them.

A - baseline:    free-text handoffs
B - structured:  same information, restructured into explicit fields
                 (spec/overlays/condition-b.yaml)
C - aurora:      free-text handoffs, plus a private condition in the context of
                 each receiving agent (spec/overlays/condition-c.yaml, private).
                 The handoff message itself is never modified.
"""

from __future__ import annotations

from dataclasses import dataclass

from integrations.aurora import RECEIVING_AGENTS

AGENTS = ["intake", "planner", "implementer", "verifier", "handover"]

# Shared by every condition (equivalence rule). Each agent manifest in
# spec/agents/ carries this exact text; a test checks it.
FLAG_INSTRUCTION = (
    "If you notice that a constraint from the original request is missing or has "
    "been altered, write a line starting with 'FLAG: CONSTRAINT_MISSING' or "
    "'FLAG: CONSTRAINT_ALTERED' followed by a short explanation."
)

# Condition B only: field names, no extra information.
STRUCTURED_FIELDS = ["valid_until", "revert_action"]


@dataclass(frozen=True)
class Condition:
    name: str
    handoff_format: str            # "text" or "structured"
    overlays: tuple[str, ...]      # MAS-Lab overlays, relative to spec/
    private_condition: bool = False


CONDITIONS = {
    "A": Condition("A", "text", ()),
    "B": Condition("B", "structured", ("overlays/condition-b.yaml",)),
    "C": Condition("C", "text", ("overlays/condition-c.yaml",), private_condition=True),
}

__all__ = ["AGENTS", "CONDITIONS", "Condition", "FLAG_INSTRUCTION", "RECEIVING_AGENTS", "STRUCTURED_FIELDS"]
