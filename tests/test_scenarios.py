import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from rag_system.api import create_app
from rag_system.bootstrap import build_system
from rag_system.llm import LLMError
from rag_system.models import Claim, Draft, Feedback, Query

SCENARIOS = [
    (
        "What’s the process for deploying a new microservice and what compliance checks are needed?",
        {"technical", "compliance"},
        {"tech-deploy", "comp-deploy"},
    ),
    (
        "How do I troubleshoot API performance issues while following our security policies?",
        {"technical", "compliance"},
        {"tech-performance", "comp-debug"},
    ),
    (
        "What business approvals are required for implementing a new data processing workflow?",
        {"technical", "business", "compliance"},
        {"biz-approvals", "comp-data"},
    ),
]


@pytest.mark.parametrize("query,domains,sources", SCENARIOS)
def test_multi_domain_scenarios(system, query, domains, sources):
    a = system.query(query)
    assert {t.domain for t in a.plan.tasks} == domains
    assert a.status == "answered"
    assert sources <= {e.document.id for e in a.citations}
    assert a.llm_calls == 2 + len(domains)
    for r in a.results:
        assert all(e.document.domain == r.task.domain for e in r.retrieved)


def test_unrelated_and_empty_queries(system):
    assert system.query("Who won the World Cup?").status == "no_evidence"
    for text in ["", "  ", "1234", "x" * 2001]:
        with pytest.raises(ValidationError):
            Query(text=text)


def test_conflict_expands_beyond_top_k_and_authority_wins(system):
    # Even if the informal note is the only retrieved passage, the official policy is inspected.
    agent = system.agents["technical"]
    original = agent.retrieve

    def only_note(task, complexity):
        result = original(task, complexity)
        result.retrieved = [system.store.evidence(system.store.documents["tech-logs"], 0.99)]
        return result

    agent.retrieve = only_note
    system.store.weights["tech-logs@v1#0"] = 1.2
    a = system.query("Explain technical API logs")
    assert a.conflicts[0].selected_source_id == "comp-retention@v1#0"
    assert "90 days" not in a.answer
    assert any(e.document.id == "comp-retention" for e in a.citations)


def test_equal_authority_conflict_is_withheld(system):
    doc = system.store.documents["comp-retention"].model_copy(
        update={
            "id": "comp-retention-alt",
            "value": "60",
            "text": "Production API request logs must be deleted after 60 days under the current approved retention policy.",
        }
    )
    system.upsert(doc)
    a = system.query("How long should we retain production API request logs?")
    assert any(c.selected_source_id is None for c in a.conflicts)
    assert "clarification" in a.answer
    assert not any(e.document.fact_key == "retention-days" for e in a.citations)


def test_different_scope_is_not_conflict(system):
    original = system.store.documents["comp-retention"]
    doc = original.model_copy(
        update={"id": "staging-retention", "scope": "staging-logs", "value": "60"}
    )
    system.upsert(doc)
    a = system.query("How long should we retain production API request logs?")
    assert all(c.scope != "staging-logs" for c in a.conflicts)


def test_update_replaces_vector_version_and_stale_feedback(system):
    a = system.query("How long should we retain production API request logs?")
    old = system.store.documents["comp-retention"]
    new = old.model_copy(
        update={"version": 2, "value": "14", "text": old.text.replace("30 days", "14 days")}
    )
    assert system.upsert(new)
    assert not system.upsert(new)
    with pytest.raises(ValueError):
        system.upsert(old)
    with pytest.raises(ValueError, match="current"):
        system.submit_feedback(
            Feedback(request_id=a.request_id, source_id=old.source_id, helpful=True)
        )
    b = system.query("How long should we retain production API request logs?")
    assert "14 days" in b.answer and "30 days" not in b.answer
    assert all(e.document.source_id != old.source_id for e in b.citations)
    assert any(
        e.document.source_id == old.source_id for e in a.citations
    )  # immutable historical snapshot


def test_failed_embedding_update_is_atomic(system):
    old = system.store.documents["tech-deploy"].model_copy(deep=True)

    def broken(texts):
        raise RuntimeError("embedding failure")

    system.store.embedder.encode = broken
    with pytest.raises(RuntimeError):
        system.upsert(old.model_copy(update={"version": 2, "text": "New procedure"}))
    assert system.store.documents[old.id] == old


def test_feedback_is_bounded_deduplicated_and_affects_ranking(system):
    # Equal texts yield equal similarity: repeated explicit source feedback changes the ranking.
    a = system.store.documents["tech-deploy"]
    system.upsert(a.model_copy(update={"id": "aaa-deploy"}))
    s = system.store
    query = "deploy microservice"
    assert s.search(query, "technical", 2, 0)[0].document.id == "aaa-deploy"
    for _ in range(8):
        answer = system.query("How do I deploy a microservice?")
        feedback = Feedback(request_id=answer.request_id, source_id=a.source_id, helpful=True)
        system.submit_feedback(feedback)
    assert s.weights[a.source_id] == 1.2
    assert s.search(query, "technical", 2, 0)[0].document.id == a.id
    with pytest.raises(ValueError, match="already"):
        system.submit_feedback(feedback)
    with pytest.raises(ValueError):
        system.submit_feedback(feedback.model_copy(update={"source_id": "made-up"}))


def test_dynamic_retrieval_parameters(system):
    simple = system.query("How do I deploy a microservice?")
    complex_ = system.query(SCENARIOS[0][0])
    assert simple.results[0].top_k < complex_.results[0].top_k
    assert complex_.results[0].top_k < complex_.results[1].top_k


def test_bad_domain_citations_fail_closed(system):
    original = system.llm.generate

    def bad(stage, *args):
        if stage == "domain":
            return Draft(claims=[Claim(text="Unsupported", source_ids=["invented"])])
        return original(stage, *args)

    system.llm.generate = bad
    a = system.query(SCENARIOS[0][0])
    assert a.status == "failed" and not a.citations
    assert all(r.error for r in a.results)


def test_one_domain_failure_returns_partial(system):
    original = system.llm.generate

    def fail(stage, instructions, payload, schema):
        if stage == "domain" and payload["task"]["domain"] == "compliance":
            raise LLMError("compliance: timeout")
        return original(stage, instructions, payload, schema)

    system.llm.generate = fail
    a = system.query(SCENARIOS[0][0])
    assert a.status == "partial"
    assert a.results[1].error
    assert not any(e.document.domain == "compliance" for e in a.citations)


def test_synthesis_failure_is_not_success(system):
    original = system.llm.generate

    def fail(stage, *args):
        if stage == "synthesis":
            raise LLMError("synthesis: timeout")
        return original(stage, *args)

    system.llm.generate = fail
    a = system.query(SCENARIOS[0][0])
    assert a.status == "failed" and not a.citations
    assert system.metrics()["query_completion_rate"] == 0


def test_api_contract_validation_updates_feedback(system):
    with TestClient(create_app(system)) as client:
        assert client.get("/health").json()["mode"] == "mock"
        assert "/query" in client.get("/openapi.json").json()["paths"]
        assert client.post("/query", json={"text": "  "}).status_code == 422
        response = client.post("/query", json={"text": SCENARIOS[0][0]})
        assert response.status_code == 200
        a = response.json()
        source = a["citations"][0]["document"]
        source_id = f"{source['id']}@v{source['version']}#0"
        feedback = {"request_id": a["request_id"], "source_id": source_id, "helpful": True}
        assert client.post("/feedback", json=feedback).status_code == 200
        assert client.post("/feedback", json=feedback).status_code == 409
        source["version"] += 1
        assert client.put("/documents/" + source["id"], json=source).json()["changed"]
        assert client.put("/documents/mismatch", json=source).status_code == 422
        assert client.get("/metrics").json()["queries_total"] == 1


@pytest.mark.semantic
def test_real_semantic_retrieval():
    import os

    if os.getenv("RUN_SEMANTIC") != "1":
        pytest.skip("Set RUN_SEMANTIC=1 to use/download the actual local model")
    system = build_system("mock", "fastembed")
    for query, domains, sources in SCENARIOS:
        a = system.query(query)
        assert a.status == "answered"
        assert sources <= {e.document.id for e in a.citations}


@pytest.mark.live
def test_live_model():
    import os

    if os.getenv("RUN_LIVE_LLM") != "1":
        pytest.skip("Explicit RUN_LIVE_LLM=1 and API key required; incurs provider usage")
    system = build_system("live", "fastembed")
    a = system.query(SCENARIOS[0][0])
    assert a.status == "answered" and a.citations
    assert {"technical", "compliance"} == {t.domain for t in a.plan.tasks}


def test_synthesis_cannot_silently_drop_a_domain(system):
    original = system.llm.generate

    def omit(stage, instructions, payload, schema):
        result = original(stage, instructions, payload, schema)
        if stage == "synthesis":
            result.claims = [
                c for c in result.claims if all(s.startswith("tech-") for s in c.source_ids)
            ]
        return result

    system.llm.generate = omit
    a = system.query(SCENARIOS[0][0])
    assert a.status == "partial"


def test_failed_provider_is_502_with_trace(system):
    def failed(*args):
        raise LLMError("planner: unavailable")

    system.llm.generate = failed
    with TestClient(create_app(system)) as client:
        r = client.post("/query", json={"text": SCENARIOS[0][0]})
        assert r.status_code == 502
        assert r.json()["status"] == "failed"
        assert r.json()["error"] == "planner: unavailable"


def test_source_alias_cannot_mutate_index(system):
    original = system.store.documents["tech-deploy"].model_copy(deep=True)
    new = original.model_copy(update={"version": 2})
    system.upsert(new)
    new.text = "Changed outside the store"
    assert system.store.documents[new.id].text == original.text


def test_feedback_cannot_reduce_weight_below_bound(system):
    for _ in range(12):
        system.store.adjust_weight("tech-deploy@v1#0", False)
    assert system.store.weights["tech-deploy@v1#0"] == 0.8
