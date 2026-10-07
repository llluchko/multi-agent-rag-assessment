"""Deterministic conflict policy and source-labelled rendering."""

from .models import AgentResult, AnswerStatus, Claim, Conflict, Draft, Evidence


def cited_source_ids(claims: list[Claim]) -> set[str]:
    """Collect unique source IDs without repeatedly scanning the same claims."""
    source_ids = set()
    for claim in claims:
        source_ids.update(claim.source_ids)
    return source_ids


def answer_status(
    results: list[AgentResult], draft: Draft, conflicts: list[Conflict], error: str | None
) -> AnswerStatus:
    """Failure → no evidence → partial coverage → complete coverage, in that order.

    Coverage means the final draft cites at least one source from every routed
    domain's claims. It does not measure whether those claims are factually correct.
    """
    if error or (results and all(result.error for result in results)):
        return "failed"
    if not draft.claims:
        return "no_evidence"
    if any(conflict.selected_source_id is None for conflict in conflicts):
        return "partial"

    final_sources = cited_source_ids(draft.claims)
    for result in results:
        domain_sources = cited_source_ids(result.claims)
        if result.error or not final_sources.intersection(domain_sources):
            return "partial"
    return "answered"


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
