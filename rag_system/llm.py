"""Explicit mock/live adapters. Live uses OpenAI Responses with strict JSON Schema."""

import json
import os
import time

import httpx
from pydantic import BaseModel, ValidationError

from .models import Claim, Draft
from .query_classifier import mock_plan


class LLMError(RuntimeError):
    """Safe public failure; provider payloads and credentials are never included."""


class MockLLM:
    """Extractive simulation exercises real retrieval and coordination without an API key."""

    mode = "mock"

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
        except (httpx.HTTPError, ValidationError, ValueError, KeyError, TypeError) as exc:
            raise LLMError(f"{stage}: provider unavailable or invalid structured response") from exc
