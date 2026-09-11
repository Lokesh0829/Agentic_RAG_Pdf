"""
ingestion/embedder.py — Batch embedding and vector store insertion
"""
import logging
from typing import Callable
from langchain_core.documents import Document

from database import ChromaDB

logger = logging.getLogger(__name__)

BATCH_SIZE = 50  # Embed 50 docs at a time to avoid memory issues


async def embed_and_store(
    documents: list[Document],
    user_id: str,
    doc_id: str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    """
    Embed documents in batches and store in ChromaDB.
    Returns total number of vectors stored.
    """
    if not documents:
        return 0

    vectorstore = ChromaDB.get_collection(user_id, doc_id)
    total = len(documents)
    stored = 0

    for i in range(0, total, BATCH_SIZE):
        batch = documents[i : i + BATCH_SIZE]
        try:
            vectorstore.add_documents(batch)
            stored += len(batch)
            if progress_callback:
                progress_callback(stored, total)
            logger.debug(f"Embedded batch {i // BATCH_SIZE + 1}: {stored}/{total} docs")
        except Exception as e:
            logger.error(f"Batch embedding failed at index {i}: {e}")
            raise

    logger.info(f"✅ Stored {stored} vectors for doc_id={doc_id}")
    return stored
