"""Ollama HTTP contracts; live scenario tests are separate and opt-in."""

import json

import httpx
import pytest

from rag_system.bootstrap import build_system
from rag_system.llm import LLMError, OllamaLLM
from rag_system.models import Draft


def test_ollama_structured_output_and_usage():
    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert "authorization" not in request.headers
        assert body["stream"] is False and body["think"] is False
        assert body["format"] == Draft.model_json_schema()
        assert json.loads(body["messages"][1]["content"]) == {"query": "example"}
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "message": {"content": '{"claims":[]}'},
                "prompt_eval_count": 12,
                "eval_count": 4,
            },
        )

    llm = OllamaLLM(transport=httpx.MockTransport(handler))
    assert llm.generate("domain", "instructions", {"query": "example"}, Draft).claims == []
    assert (llm.calls, llm.input_tokens, llm.output_tokens) == (1, 12, 4)


def test_ollama_limits_citations_to_current_request_sources():
    observed = []

    def handler(request):
        schema = json.loads(request.content)["format"]
        observed.append(schema["$defs"]["Claim"]["properties"]["source_ids"]["items"]["enum"])
        return httpx.Response(200, json={"done": True, "message": {"content": '{"claims":[]}'}})

    llm = OllamaLLM(transport=httpx.MockTransport(handler))
    for source_id in ("first@v1#0", "second@v2#0"):
        llm.generate("domain", "instructions", {"sources": [{"source_id": source_id}]}, Draft)
    assert observed == [["first@v1#0"], ["second@v2#0"]]
    assert (
        "enum"
        not in Draft.model_json_schema()["$defs"]["Claim"]["properties"]["source_ids"]["items"]
    )


@pytest.mark.parametrize(
    "data",
    [
        {"done": True, "done_reason": "length", "message": {"content": '{"claims":[]}'}},
        {"done": False, "message": {"content": '{"claims":[]}'}},
        {"done": True, "message": {"content": "not JSON"}},
        {"done": True, "message": {"content": '{"claims":[{"text":"No sources"}]}'}},
    ],
)
def test_ollama_invalid_or_truncated_output_fails(data):
    llm = OllamaLLM(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=data)))
    with pytest.raises(LLMError):
        llm.generate("domain", "instructions", {}, Draft)
    assert llm.calls == 1


def test_ollama_unavailable_does_not_fall_back():
    def offline(request):
        raise httpx.ConnectError("offline", request=request)

    llm = OllamaLLM(transport=httpx.MockTransport(offline))
    with pytest.raises(LLMError, match="start it and check OLLAMA_URL"):
        llm.generate("plan", "instructions", {}, Draft)


def test_ollama_missing_model_has_actionable_error():
    llm = OllamaLLM(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    with pytest.raises(LLMError, match="OLLAMA_MODEL is installed"):
        llm.generate("plan", "instructions", {}, Draft)


def test_local_provider_needs_no_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert isinstance(build_system("live", "lexical").llm, OllamaLLM)
    monkeypatch.setenv("LLM_PROVIDER", "typo")
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        build_system("live", "lexical")
