"""The three conditions. Only the handoff mechanism differs between them.

A - baseline:    free-text handoff, passthrough layer
B - structured:  same information, restructured into explicit fields
C - aurora:      free-text handoff, Aurora ISL layer applied at each handoff
"""

from __future__ import annotations

from dataclasses import dataclass

from integrations.aurora import HandoffLayer, PassthroughLayer

AGENTS = ["intake", "planner", "implementer", "verifier", "handover"]

# Shared by every condition (equivalence rule).
FLAG_INSTRUCTION = (
    "If you notice that a constraint from the original request is missing or has "
    "been altered, write a line starting with 'FLAG: CONSTRAINT_MISSING' or "
    "'FLAG: CONSTRAINT_ALTERED' followed by a short explanation."
)

# Condition B only: field names, no extra information.
STRUCTURED_FIELDS = ["summary", "change", "valid_until", "revert_action", "flags"]


@dataclass(frozen=True)
class Condition:
    name: str
    handoff_format: str  # "text" or "structured"
    layer_factory: type


def build_layer(condition: Condition) -> HandoffLayer:
    return condition.layer_factory()


CONDITIONS = {
    "A": Condition("A", "text", PassthroughLayer),
    "B": Condition("B", "structured", PassthroughLayer),
    # Replace PassthroughLayer with the Aurora ISL implementation once available.
    "C": Condition("C", "text", PassthroughLayer),
}
