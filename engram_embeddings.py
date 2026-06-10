"""Embedding generation with support for sentence-transformers and Ollama backends."""

import sys
import os
from typing import List
import numpy as np


class EmbeddingGenerator:
    def __init__(self, config: dict):
        self.backend = config.get('backend', 'sentence-transformers')
        self.model_name = config.get('model', 'sentence-transformers/all-MiniLM-L6-v2')
        self.device = config.get('device', 'cpu')
        self.ollama_url = config.get('ollama_url', 'http://localhost:11434')
        self.ollama_model = config.get('ollama_model', 'nomic-embed-text')
        self.dimensions = config.get(
            'ollama_dimensions' if self.backend == 'ollama' else 'dimensions', 384
        )
        self._model = None

    @property
    def model(self):
        if self._model is None and self.backend == 'sentence-transformers':
            print(f"Loading embedding model: {self.model_name}", file=sys.stderr, flush=True)
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, device=self.device)
            finally:
                sys.stdout.close()
                sys.stderr.close()
                sys.stdout, sys.stderr = old_stdout, old_stderr
            print("Model loaded.", file=sys.stderr, flush=True)
        return self._model

    def generate_embedding(self, text: str) -> np.ndarray:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        if self.backend == 'ollama':
            return self._ollama_embed(text)
        return self.model.encode(text, convert_to_numpy=True)

    def batch_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        if not texts:
            return []
        valid = [t for t in texts if t and t.strip()]
        if not valid:
            raise ValueError("All texts are empty")
        if self.backend == 'ollama':
            return [self._ollama_embed(t) for t in valid]
        embeddings = self.model.encode(valid, convert_to_numpy=True, show_progress_bar=len(valid) > 10)
        return list(embeddings)

    def _ollama_embed(self, text: str) -> np.ndarray:
        import httpx
        resp = httpx.post(
            f"{self.ollama_url}/api/embeddings",
            json={"model": self.ollama_model, "prompt": text},
            timeout=30.0
        )
        resp.raise_for_status()
        return np.array(resp.json()["embedding"], dtype=np.float32)
