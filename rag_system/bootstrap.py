"""The single composition root used by notebook, API, tests and evaluation."""

import json
import os
from pathlib import Path

from dotenv import dotenv_values

from .embeddings import LexicalEmbeddings, LocalEmbeddings
from .llm import MockLLM, OllamaLLM
from .models import Document
from .orchestrator import Orchestrator
from .vector_store import VectorStoreManager

ROOT = Path(__file__).resolve().parents[1]


def build_system(provider: str | None = None, embedding_backend: str | None = None) -> Orchestrator:
    """Read .env each time; explicit arguments and environment variables take precedence."""
    config = {**dotenv_values(ROOT / ".env"), **os.environ}
    provider = provider or config.get("LLM_PROVIDER", "mock")
    backend = embedding_backend or config.get("EMBEDDING_BACKEND", "fastembed")
    if provider not in ("mock", "ollama"):
        raise ValueError("LLM_PROVIDER must be mock or ollama")
    if backend not in ("fastembed", "lexical"):
        raise ValueError("EMBEDDING_BACKEND must be fastembed or lexical")
    llm = (
        MockLLM()
        if provider == "mock"
        else OllamaLLM(
            model=config.get("OLLAMA_MODEL", "qwen3:4b"),
            base_url=config.get("OLLAMA_URL", "http://localhost:11434"),
        )
    )
    embedder = (
        LocalEmbeddings(config.get("EMBEDDING_CACHE", str(ROOT / ".cache" / "models")))
        if backend == "fastembed"
        else LexicalEmbeddings()
    )
    documents = [
        Document.model_validate(d)
        for d in json.loads((ROOT / "data" / "knowledge.json").read_text())
    ]
    return Orchestrator(VectorStoreManager(documents, embedder), llm)
