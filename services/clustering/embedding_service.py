import unicodedata

import numpy as np

from config.settings import EMBEDDING_MODEL
from models.evidence_card import EvidenceCard
from utils.logging_utils import get_logger

_logger = get_logger(__name__)


def _normalize_search_text(text: str, *, max_len: int = 8000) -> str:
    t = " ".join((text or "").strip().split())
    t = unicodedata.normalize("NFKC", t)
    if len(t) > max_len:
        t = t[:max_len]
    return t if t else "(empty)"


class EmbeddingService:
    """Embeddings for coarse clustering: document titles only (no body, keys, or excerpt)."""

    def __init__(self) -> None:
        self._model = None
        self._use_fallback = False
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(EMBEDDING_MODEL)
        except Exception:
            self._use_fallback = True
            _logger.warning(
                "Loading embedding model %r failed; using deterministic hash vectors (clustering + digest search).",
                EMBEDDING_MODEL,
                exc_info=True,
            )

    @staticmethod
    def _title_for_clustering(card: EvidenceCard) -> str:
        t = (card.title or "").strip()
        t = " ".join(t.split())
        t = unicodedata.normalize("NFKC", t)
        return t if t else "(untitled)"

    def embed(self, cards: list[EvidenceCard]) -> np.ndarray:
        if not cards:
            dim = 8 if self._use_fallback else self._model.get_sentence_embedding_dimension()
            return np.zeros((0, dim), dtype=float)
        texts = [self._title_for_clustering(c) for c in cards]
        if self._use_fallback:
            arr = np.zeros((len(cards), 8), dtype=float)
            for idx, text in enumerate(texts):
                arr[idx] = self._hash_embed(text)
            return arr
        return np.asarray(self._model.encode(texts, normalize_embeddings=True))

    def embed_plain_texts(self, texts: list[str]) -> np.ndarray:
        """Dense vectors for arbitrary strings (e.g. digest search). Same dim as ``embed``."""
        dim = 8 if self._use_fallback else self._model.get_sentence_embedding_dimension()
        if not texts:
            return np.zeros((0, dim), dtype=float)
        normed = [_normalize_search_text(t) for t in texts]
        if self._use_fallback:
            arr = np.zeros((len(normed), 8), dtype=float)
            for idx, text in enumerate(normed):
                arr[idx] = self._hash_embed(text)
            return arr
        return np.asarray(self._model.encode(normed, normalize_embeddings=True))

    def embed_query_text(self, text: str) -> np.ndarray:
        """Single query vector; normalized like cluster texts for cosine similarity."""
        return self.embed_plain_texts([text])[0]

    def _hash_embed(self, text: str) -> np.ndarray:
        vec = np.zeros(8, dtype=float)
        for idx, ch in enumerate(text.encode("utf-8")):
            vec[idx % 8] += float(ch)
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec
