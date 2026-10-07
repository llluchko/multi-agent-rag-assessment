"""Exact cosine search over a tiny, domain-filtered corpus with atomic upserts."""

import numpy as np

from .embeddings import Embedder
from .models import Document, Domain, Evidence


class VectorStoreManager:
    """Owns document snapshots, vectors and bounded per-source feedback weights."""

    def __init__(self, documents: list[Document], embedder: Embedder):
        self.embedder = embedder
        self.documents: dict[str, Document] = {}
        self.vectors: dict[str, np.ndarray] = {}
        self.weights: dict[str, float] = {}
        if len({d.id for d in documents}) != len(documents):
            raise ValueError("Duplicate document IDs")
        vectors = self._encode([f"{d.title}. {d.text}" for d in documents])
        for doc, vector in zip(documents, vectors, strict=True):
            self.documents[doc.id] = doc.model_copy(deep=True)
            self.vectors[doc.id] = vector

    def _encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        vectors = self.embedder.encode(texts)
        if vectors.ndim != 2 or len(vectors) != len(texts) or not np.isfinite(vectors).all():
            raise ValueError("Invalid embedding output")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.maximum(norms, 1e-12)

    def evidence(self, doc: Document, similarity: float) -> Evidence:
        weight = self.weights.get(doc.source_id, 1.0)
        # An explainable heuristic, not a calibrated probability of correctness.
        confidence = np.clip(
            0.6 * max(0, similarity) + 0.3 * doc.authority + 0.1 * weight / 1.2, 0, 1
        )
        return Evidence(
            document=doc.model_copy(deep=True),
            similarity=round(similarity, 6),
            confidence=round(float(confidence), 6),
            feedback_weight=weight,
        )

    def search(
        self, query: str, domain: Domain, top_k: int, min_similarity: float
    ) -> list[Evidence]:
        vector = self._encode([query])[0]
        hits = [
            self.evidence(d, float(vector @ self.vectors[d.id]))
            for d in self.documents.values()
            if d.domain == domain
        ]
        hits = [h for h in hits if h.similarity >= min_similarity]
        return sorted(hits, key=lambda h: (-h.similarity * h.feedback_weight, h.document.id))[
            :top_k
        ]

    def peers(self, doc: Document, query: str) -> list[Evidence]:
        """Inspect all same-scope facts so top-k cannot hide a contradictory policy."""
        vector = self._encode([query])[0]
        return [
            self.evidence(d, float(vector @ self.vectors[d.id]))
            for d in self.documents.values()
            if d.fact == doc.fact
        ]

    def upsert(self, doc: Document) -> bool:
        """Idempotent retry; a changed document needs a strictly newer version."""
        previous = self.documents.get(doc.id)
        if previous == doc:
            return False
        if previous and doc.version <= previous.version:
            raise ValueError("Changed document requires a higher version")
        vector = self._encode([f"{doc.title}. {doc.text}"])[0]
        if self.vectors and vector.shape != next(iter(self.vectors.values())).shape:
            raise ValueError("Embedding dimensions changed")
        # Compute first: failed encoding leaves the previous document intact.
        self.documents[doc.id] = doc.model_copy(deep=True)
        self.vectors[doc.id] = vector
        if previous:
            self.weights.pop(previous.source_id, None)
        return True

    def adjust_weight(self, source_id: str, helpful: bool) -> float:
        weight = self.weights.get(source_id, 1.0)
        weight = round(float(np.clip(weight + (0.05 if helpful else -0.05), 0.8, 1.2)), 2)
        self.weights[source_id] = weight
        return weight
