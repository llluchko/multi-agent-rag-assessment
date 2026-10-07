import json

import httpx
import pytest

from rag_system.llm import LLMError, OpenAILLM
from rag_system.models import Draft


def response(content, status="completed"):
    return {
        "status": status,
        "usage": {"input_tokens": 5, "output_tokens": 3},
        "output": [{"type": "message", "content": content}],
    }


def test_responses_request_and_validation():
    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/v1/responses"
        assert body["store"] is False and body["text"]["format"]["strict"] is True
        assert body["text"]["format"]["schema"]["additionalProperties"] is False
        return httpx.Response(
            200, json=response([{"type": "output_text", "text": '{"claims":[]}'}])
        )

    llm = OpenAILLM(api_key="test-only", transport=httpx.MockTransport(handler))
    assert llm.generate("domain", "instructions", {}, Draft).claims == []
    assert (llm.calls, llm.input_tokens, llm.output_tokens) == (1, 5, 3)


@pytest.mark.parametrize(
    "data",
    [
        response([{"type": "refusal", "refusal": "No"}]),
        response([{"type": "output_text", "text": "{}"}]),
        response([{"type": "output_text", "text": '{"claims":[]}'}], status="incomplete"),
        response([]),
    ],
)
def test_invalid_provider_response_is_explicit(data):
    llm = OpenAILLM(
        api_key="test-only", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=data))
    )
    with pytest.raises(LLMError):
        llm.generate("domain", "instructions", {}, Draft)


def test_retry_is_bounded_and_errors_do_not_leak_key():
    llm = OpenAILLM(
        api_key="private-test-value", transport=httpx.MockTransport(lambda r: httpx.Response(503))
    )
    with pytest.raises(LLMError) as error:
        llm.generate("plan", "instructions", {}, Draft)
    assert llm.calls == 2
    assert "private-test-value" not in str(error.value)


def test_no_implicit_mock_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="requires OPENAI_API_KEY"):
        OpenAILLM()
