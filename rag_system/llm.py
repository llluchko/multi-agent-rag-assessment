"""Two adapters share one generate() contract: mock or local Ollama."""

import json
import os

import httpx
from pydantic import BaseModel, ValidationError

from .models import Claim, Draft
from .query_classifier import mock_plan


class LLMError(RuntimeError):
    """Safe public failure; provider payloads and credentials are never included."""


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
