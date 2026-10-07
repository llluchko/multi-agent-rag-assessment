"""Small diagnostic evaluation: routing, raw retrieval, citations and abstention."""

import json

from .bootstrap import ROOT


def evaluate(system) -> dict:
    """Labels are hand-authored development examples, not a statistical benchmark."""
    cases = json.loads((ROOT / "data" / "evaluation.json").read_text())
    rows = []
    for case in cases:
        answer = system.query(case["query"])
        expected = set(case["relevant_documents"])
        retrieved = {e.document.id for r in answer.results for e in r.retrieved}
        cited = {e.document.id for e in answer.citations}
        routed = {t.domain for t in answer.plan.tasks} if answer.plan else set()
        routing_correct = routed == set(case["domains"])
        retrieval_recall = len(expected & retrieved) / len(expected) if expected else None
        citation_recall = len(expected & cited) / len(expected) if expected else None
        status_correct = (
            answer.status == "answered" if case["answerable"] else answer.status == "no_evidence"
        )
        rows.append(
            {
                "id": case["id"],
                "group": case["group"],
                "routing_correct": routing_correct,
                "retrieval_recall_at_dynamic_k": retrieval_recall,
                "expected_source_recall_in_answer": citation_recall,
                "expected_status": status_correct,
                "status": answer.status,
                "diagnostic_pass": routing_correct
                and status_correct
                and (citation_recall == 1 if expected else not cited),
                "latency_ms": round(answer.timings_ms["total"], 2),
                "llm_calls": answer.llm_calls,
                "retrieved": sorted(retrieved),
                "cited": sorted(cited),
            }
        )
    recalls = [
        r["retrieval_recall_at_dynamic_k"]
        for r in rows
        if r["retrieval_recall_at_dynamic_k"] is not None
    ]
    return {
        "mode": system.llm.mode,
        "embedding_backend": system.store.embedder.name,
        "cases": len(rows),
        "routing_accuracy": sum(r["routing_correct"] for r in rows) / len(rows),
        "mean_retrieval_recall_at_dynamic_k": sum(recalls) / len(recalls),
        "diagnostic_success_rate": sum(r["diagnostic_pass"] for r in rows) / len(rows),
        "definition": "Diagnostic success checks routing, expected sources and abstention. It does not prove claim entailment or answer quality.",
        "rows": rows,
    }
