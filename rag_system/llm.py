"""Mock, OpenAI and local Ollama adapters share one generate() contract."""

import json
import os
import time

import httpx
from pydantic import BaseModel, ValidationError

from .models import Claim, Draft
from .query_classifier import mock_plan


class LLMError(RuntimeError):
    """Safe public failure; provider payloads and credentials are never included."""


def quota_error(response: httpx.Response) -> str | None:
    """Billing failures need account action, not an immediate retry."""
    if response.status_code != 429:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    if code == "credit_balance_exhausted":
        return "OpenAI API credit balance exhausted. Add credits in API billing settings."
    limits = (
        "insufficient_quota",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
    )
    if code in limits or error.get("type") == "insufficient_quota":
        return "OpenAI API quota exhausted. Check API billing and spending limits."
    return None


class MockLLM:
    """Extractive simulation exercises real retrieval and coordination without an API key."""

    mode = "mock"
    provider = "mock"

    def __init__(self):
        self.calls = self.input_tokens = self.output_tokens = 0

    def generate(self, stage: str, instructions: str, payload: dict, schema: type[BaseModel]):
        self.calls += 1
        if stage == "plan":
            return mock_plan(payload["query"])
        if stage == "domain":
            return Draft(
                claims=[
                    Claim(text=s["text"], source_ids=[s["source_id"]]) for s in payload["sources"]
                ]
            )
        # De-duplicate shared policy evidence across domain responses.
        claims = {}
        for result in payload["results"]:
            for claim in result["claims"]:
                key = (claim["text"], tuple(claim["source_ids"]))
                claims[key] = Claim.model_validate(claim)
        return Draft(claims=list(claims.values())[:12])


class OpenAILLM:
    """A bounded synchronous adapter, injected transport supports genuine contract tests."""

    mode = "live"
    provider = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "RAG_MODE=live requires OPENAI_API_KEY; use mock explicitly without a key"
            )
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini-2025-04-14")
        self.transport = transport
        self.calls = self.input_tokens = self.output_tokens = 0

    def generate(self, stage: str, instructions: str, payload: dict, schema: type[BaseModel]):
        body = {
            "model": self.model,
            "store": False,
            "max_output_tokens": 3000,
            "instructions": instructions,
            "input": json.dumps(payload),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema.__name__,
                    "strict": True,
                    "schema": schema.model_json_schema(),
                }
            },
        }
        try:
            with httpx.Client(timeout=30, transport=self.transport) as client:
                for attempt in range(2):
                    self.calls += 1
                    response = client.post(
                        "https://api.openai.com/v1/responses",
                        json=body,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                    )
                    quota = quota_error(response)
                    if quota:
                        raise LLMError(f"{stage}: {quota}")
                    if attempt == 0 and (
                        response.status_code == 429 or response.status_code >= 500
                    ):
                        time.sleep(0.2)
                        continue
                    response.raise_for_status()
                    break
            data = response.json()
            usage = data.get("usage") or {}
            self.input_tokens += usage.get("input_tokens", 0)
            self.output_tokens += usage.get("output_tokens", 0)
            if data.get("status") != "completed":
                raise LLMError(f"{stage}: model response incomplete")
            content = [
                part
                for item in data.get("output", [])
                if item.get("type") == "message"
                for part in item.get("content", [])
            ]
            if any(part.get("type") == "refusal" for part in content):
                raise LLMError(f"{stage}: model refused the request")
            output = "".join(p["text"] for p in content if p.get("type") == "output_text")
            return schema.model_validate_json(output)
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                f"{stage}: OpenAI API request failed (HTTP {exc.response.status_code})."
            ) from exc
        except (httpx.RequestError, ValidationError, ValueError, KeyError, TypeError) as exc:
            raise LLMError(f"{stage}: provider unavailable or invalid structured response") from exc


class OllamaLLM:
    """Local generation with JSON Schema; no API key, retries or mock fallback."""

    mode = "live"
    provider = "ollama"

    def __init__(self, model=None, base_url=None, transport=None):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3:4b")
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.transport = transport
        self.calls = self.input_tokens = self.output_tokens = 0

    def generate(self, stage: str, instructions: str, payload: dict, schema: type[BaseModel]):
        self.calls += 1
        output_schema = schema.model_json_schema()
        if payload.get("sources") and "Claim" in output_schema.get("$defs", {}):
            # Small models can alter IDs; constrain decoding to the actual supplied sources.
            output_schema["$defs"]["Claim"]["properties"]["source_ids"]["items"]["enum"] = [
                source["source_id"] for source in payload["sources"]
            ]
        try:
            with httpx.Client(timeout=120, transport=self.transport) as client:
                response = client.post(
                    self.base_url + "/api/chat",
                    json={
                        "model": self.model,
                        "stream": False,
                        "think": False,
                        "format": output_schema,
                        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 3000},
                        "messages": [
                            {"role": "system", "content": instructions},
                            {"role": "user", "content": json.dumps(payload)},
                        ],
                    },
                )
                response.raise_for_status()
            data = response.json()
            self.input_tokens += data.get("prompt_eval_count", 0)
            self.output_tokens += data.get("eval_count", 0)
            if not data.get("done") or data.get("done_reason") == "length":
                raise LLMError(f"{stage}: Ollama response incomplete")
            return schema.model_validate_json(data["message"]["content"])
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                f"{stage}: Ollama HTTP {exc.response.status_code}; check OLLAMA_MODEL is installed."
            ) from exc
        except httpx.RequestError as exc:
            raise LLMError(f"{stage}: cannot reach Ollama; start it and check OLLAMA_URL.") from exc
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            raise LLMError(f"{stage}: Ollama returned invalid structured output") from exc
