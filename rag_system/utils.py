"""Deterministic conflict policy and source-labelled rendering."""

from .models import Conflict, Draft, Evidence


def resolve_conflict(candidates: list[Evidence]) -> tuple[list[Evidence], Conflict | None]:
    """Compare canonical same-scope values; withhold unresolved equal-authority conflicts."""
    if len({e.document.value for e in candidates}) < 2:
        return candidates, None
    # Feedback/relevance cannot defeat authority. Equal authority uses heuristic confidence.
    authority = max(e.document.authority for e in candidates)
    leaders = sorted(
        [e for e in candidates if e.document.authority == authority],
        key=lambda e: (-e.confidence, e.document.id),
    )
    winner = leaders[0]
    opposition = [e for e in leaders if e.document.value != winner.document.value]
    unresolved = opposition and winner.confidence - opposition[0].confidence < 0.08
    selected = None if unresolved else winner.document.source_id
    reason = (
        "Equal-authority contradictory evidence is too close; clarification required."
        if unresolved
        else "Highest source authority, then heuristic confidence; feedback cannot override authority."
    )
    conflict = Conflict(
        fact_key=winner.document.fact_key,
        scope=winner.document.scope,
        candidates=candidates,
        selected_source_id=selected,
        reason=reason,
    )
    return ([] if unresolved else [winner]), conflict


def render(draft: Draft) -> str:
    return "\n\n".join(f"{c.text} [{', '.join(c.source_ids)}]" for c in draft.claims)
