"""Interface for an interaction layer applied at agent handoffs (condition C).

Draft contract, open for discussion:
  - `reset(run_id)` is called once at the start of each run.
  - `on_handoff(...)` is called at every handoff, in order, and returns the
    payload actually delivered to the next agent.
  - The layer may keep internal state across the handoffs of one run, but it
    receives no information beyond the handoff payloads themselves (equivalence
    rule: same information as conditions A and B).
  - Its implementation stays independent of this repo; only this interface is
    shared.
"""

from __future__ import annotations

from typing import Any, Protocol, Union

Payload = Union[str, dict[str, Any]]


class HandoffLayer(Protocol):
    name: str

    def reset(self, run_id: str) -> None: ...

    def on_handoff(self, hop: int, from_agent: str, to_agent: str, payload: Payload) -> Payload: ...


class PassthroughLayer:
    """Used by conditions A and B: delivers the payload unchanged."""

    name = "passthrough"

    def reset(self, run_id: str) -> None:
        pass

    def on_handoff(self, hop: int, from_agent: str, to_agent: str, payload: Payload) -> Payload:
        return payload
