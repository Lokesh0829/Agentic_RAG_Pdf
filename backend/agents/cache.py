"""
agents/cache.py — Semantic Cache using MongoDB
Implements prompt caching via cosine similarity on question embeddings.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np
from pymongo import MongoClient
from langchain_community.embeddings import HuggingFaceEmbeddings

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_embeddings: HuggingFaceEmbeddings | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embed_model,
            model_kwargs={"device": "cpu"},
        )
    return _embeddings


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))


class SemanticCache:
    """
    MongoDB-backed semantic cache.
    Caches (question_embedding → answer) pairs per user+document.
    Returns cached answers for semantically similar questions (similarity > threshold).
    """

    def __init__(self):
        self._client: MongoClient | None = None

    def _get_collection(self):
        if self._client is None:
            self._client = MongoClient(settings.mongo_uri)
        db = self._client[settings.mongo_db_name]
        return db.semantic_cache

    async def get_cached(
        self,
        query: str,
        user_id: str,
        doc_id: str,
    ) -> Optional[dict]:
        """
        Check if a semantically similar query is cached.
        Returns the cached answer dict or None.
        """
        try:
            embedder = _get_embeddings()
            query_embedding = embedder.embed_query(query)

            collection = self._get_collection()
            # Fetch recent cache entries for this user+doc
            ttl_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.cache_ttl_days)
            candidates = list(
                collection.find(
                    {"user_id": user_id, "doc_id": doc_id, "created_at": {"$gte": ttl_cutoff}},
                    {"query_embedding": 1, "answer": 1, "citations": 1, "query": 1},
                ).limit(200)
            )

            for candidate in candidates:
                sim = _cosine_similarity(query_embedding, candidate["query_embedding"])
                if sim >= settings.cache_similarity_threshold:
                    logger.info(f"✅ Cache HIT (similarity={sim:.3f}) for '{query[:60]}'")
                    return {
                        "answer": candidate["answer"],
                        "citations": candidate.get("citations", []),
                        "from_cache": True,
                    }

            logger.debug(f"Cache MISS for '{query[:60]}'")
            return None

        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
            return None

    async def store(
        self,
        query: str,
        answer: str,
        citations: list[dict],
        user_id: str,
        doc_id: str,
    ):
        """Store a question-answer pair in the semantic cache."""
        try:
            embedder = _get_embeddings()
            query_embedding = embedder.embed_query(query)

            collection = self._get_collection()
            collection.insert_one({
                "user_id": user_id,
                "doc_id": doc_id,
                "query": query,
                "query_embedding": query_embedding,
                "answer": answer,
                "citations": citations,
                "created_at": datetime.now(timezone.utc),
            })

            # Create TTL index (expires after cache_ttl_days)
            collection.create_index(
                "created_at",
                expireAfterSeconds=settings.cache_ttl_days * 86400,
                background=True,
            )

            logger.debug(f"💾 Cached answer for '{query[:60]}'")

        except Exception as e:
            logger.warning(f"Cache store failed: {e}")


# Singleton
semantic_cache = SemanticCache()
