"""Split an agent output into free text and the structured blocks agents may add.

Scoring must not read its own markers as content: a FLAG line that says
"the revert action is missing" mentions "revert", and a HANDOFF field named
`revert_action: none` contains the word too. Both used to count as a preserved
revert. This module removes those blocks from the free text and parses them
separately.

Blocks:
  FLAG: CONSTRAINT_MISSING | CONSTRAINT_ALTERED ...   (any agent, all conditions)
  HANDOFF / valid_until: ... / revert_action: ...      (condition B)
  ACTIONS {"apply_at": "HH:MM", "revert_at": "HH:MM" | null}   (implementer)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

FLAG_LINE = re.compile(r"^\s*\**\s*FLAG:\s*CONSTRAINT_(MISSING|ALTERED)\b.*$", re.IGNORECASE | re.MULTILINE)
HANDOFF_BLOCK = re.compile(
    r"^\s*\**HANDOFF\**\s*:?\s*\n"
    r"(?P<body>(?:^\s*[-*]?\s*\**(?:valid_until|revert_action)\**\s*:.*\n?)+)",
    re.IGNORECASE | re.MULTILINE,
)
HANDOFF_FIELD = re.compile(r"^\s*[-*]?\s*\**(valid_until|revert_action)\**\s*:\s*(.*)$", re.IGNORECASE | re.MULTILINE)
ACTIONS_BLOCK = re.compile(r"^\s*\**ACTIONS\**\s*:?\s*(?:```(?:json)?\s*)?(\{.*?\})\s*(?:```)?", re.IGNORECASE | re.MULTILINE | re.DOTALL)
NONE_VALUES = {"", "none", "null", "n/a", "na", "-", "<none>"}


@dataclass
class ParsedOutput:
    text: str                                  # free text, blocks removed
    flags: list[tuple[str, str]] = field(default_factory=list)   # (type, full line)
    handoff: dict[str, str | None] | None = None
    actions: dict[str, Any] | None = None
    actions_error: str | None = None


def _clean(value: str) -> str | None:
    v = value.strip().strip("*`'\" ").strip()
    return None if v.lower() in NONE_VALUES else v


def parse_output(payload: Any) -> ParsedOutput:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    out = ParsedOutput(text=text)

    out.flags = [(f"constraint_{m.group(1).lower()}", m.group(0).strip()) for m in FLAG_LINE.finditer(text)]
    text = FLAG_LINE.sub("", text)

    m = HANDOFF_BLOCK.search(text)
    if m:
        fields = {k.lower(): _clean(v) for k, v in HANDOFF_FIELD.findall(m.group("body"))}
        out.handoff = {"valid_until": fields.get("valid_until"), "revert_action": fields.get("revert_action")}
        text = text[: m.start()] + text[m.end():]

    m = ACTIONS_BLOCK.search(text)
    if m:
        try:
            data = json.loads(m.group(1))
            if not isinstance(data, dict):
                raise ValueError("ACTIONS is not an object")
            out.actions = {"apply_at": _clean(str(data.get("apply_at") or "")),
                           "revert_at": _clean(str(data.get("revert_at") or ""))}
        except ValueError as exc:  # json.JSONDecodeError is a ValueError
            out.actions_error = f"invalid ACTIONS block: {exc}"
        text = text[: m.start()] + text[m.end():]

    out.text = text
    return out
