"""Condition C: a private condition applied to the receiving agent.

Agreed design:
  - The handoff is never modified. The receiving agent gets the original
    message, exactly as the previous agent wrote it.
  - The condition is added to the receiving agent's own context only.
  - The condition text stays private. The public record holds its version,
    SHA-256 hash and length, alongside the original handoff and the receiving
    agent's output.
  - The final condition is frozen alongside scenario-v1.0. Any version used
    during the pilot is hashed too.

With MAS-Lab v0.2, a fixed condition is applied with an overlay
(spec/overlays/condition-c.example.yaml), no plugin needed. A condition
computed from each incoming handoff would need a runtime hook: open question.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

# Agents that receive a handoff. intake receives the original request instead.
RECEIVING_AGENTS = ("planner", "implementer", "verifier", "handover")


class PrivateConditionLeak(RuntimeError):
    """The private condition text was found in data meant for the public record."""


@dataclass(frozen=True)
class ReceiverCondition:
    version: str
    text: str
    applies_to: tuple[str, ...] = RECEIVING_AGENTS

    @classmethod
    def from_file(cls, path: str | Path, version: str) -> "ReceiverCondition":
        return cls(version=version, text=Path(path).read_text(encoding="utf-8").strip())

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def length(self) -> int:
        return len(self.text)

    def public_record(self) -> dict[str, object]:
        """What may be published about the condition: never the text itself."""
        return {
            "condition_version": self.version,
            "condition_sha256": self.sha256,
            "condition_length": self.length,
        }

    def assert_not_in(self, *public_texts: str) -> None:
        """Fail loudly if the condition text leaked into public data."""
        if not self.text:
            return
        for text in public_texts:
            if self.text in text:
                raise PrivateConditionLeak("private condition text found in public data")
