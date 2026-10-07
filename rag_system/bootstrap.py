"""The single composition root used by notebook, API, tests and evaluation."""

import json
import os
from pathlib import Path

from .embeddings import LexicalEmbeddings, LocalEmbeddings
from .llm import MockLLM, OpenAILLM
from .models import Document
from .orchestrator import Orchestrator
from .vector_store import VectorStoreManager

ROOT = Path(__file__).resolve().parents[1]


def build_system(mode: str | None = None, embedding_backend: str | None = None) -> Orchestrator:
    mode = mode or os.getenv("RAG_MODE", "mock")
    backend = embedding_backend or os.getenv("EMBEDDING_BACKEND", "fastembed")
    if mode not in ("mock", "live"):
        raise ValueError("RAG_MODE must be mock or live")
    if backend not in ("fastembed", "lexical"):
        raise ValueError("EMBEDDING_BACKEND must be fastembed or lexical")
    llm = OpenAILLM() if mode == "live" else MockLLM()
    embedder = (
        LocalEmbeddings(os.getenv("EMBEDDING_CACHE", str(ROOT / ".cache" / "models")))
        if backend == "fastembed"
        else LexicalEmbeddings()
    )
    documents = [
        Document.model_validate(d)
        for d in json.loads((ROOT / "data" / "knowledge.json").read_text())
    ]
    return Orchestrator(VectorStoreManager(documents, embedder), llm)
