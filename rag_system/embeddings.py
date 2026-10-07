"""CPU semantic embeddings and an explicit, download-free lexical test double."""

import hashlib
import re
from pathlib import Path
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    name: str

    def encode(self, texts: list[str]) -> np.ndarray: ...


class LocalEmbeddings:
    """MiniLM through ONNX avoids a GPU and a PyTorch runtime."""

    name = "fastembed:sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, cache_dir: str | Path):
        from fastembed import TextEmbedding
        from huggingface_hub import snapshot_download

        model_path = snapshot_download(
            repo_id="qdrant/all-MiniLM-L6-v2-onnx",
            revision="d13954661f83248295ba75c1ed411eef3b7b936e",
            cache_dir=str(cache_dir),
            allow_patterns=[
                "model.onnx",
                "config.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "special_tokens_map.json",
            ],
        )

        self.model = TextEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            cache_dir=str(cache_dir),
            threads=2,
            specific_model_path=model_path,
            providers=["CPUExecutionProvider"],
        )

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(list(self.model.embed(texts)), dtype=np.float32)


class LexicalEmbeddings:
    """Deterministic hashed bag-of-words for offline tests, NOT semantic embeddings."""

    name = "lexical-test-double"
    stopwords = set("a an the is are what how do i to for and our of in with while new".split())

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), 2048), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                if word in self.stopwords:
                    continue
                index = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big") % 2048
                vectors[row, index] += 1
        return vectors
