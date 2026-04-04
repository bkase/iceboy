from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class LineNarrativeContext:
    frame: int
    line: int
    dot: int
    scope: str
    first_differing_semantic_event: str
    last_matching_fetch_epoch: int | None
    object_selection_tickets: Sequence[int]
    window_active: bool
    access_outcomes: Sequence[str]
    causal_chain: Sequence[str]


def render_line_narrative(context: LineNarrativeContext) -> str:
    tickets = ", ".join(str(ticket) for ticket in context.object_selection_tickets) or "none"
    outcomes = ", ".join(context.access_outcomes) or "none"
    causes = " -> ".join(context.causal_chain) or "none"
    epoch = "none" if context.last_matching_fetch_epoch is None else str(context.last_matching_fetch_epoch)
    return "\n".join(
        [
            f"PPU divergence at frame {context.frame}, line {context.line}, dot {context.dot} ({context.scope})",
            f"First differing semantic event: {context.first_differing_semantic_event}",
            f"Last matching fetch epoch: {epoch}",
            f"Object selection tickets: {tickets}",
            f"Window active: {'yes' if context.window_active else 'no'}",
            f"Access outcomes around divergence: {outcomes}",
            f"Causal chain: {causes}",
        ]
    )


__all__ = ["LineNarrativeContext", "render_line_narrative"]
