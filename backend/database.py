"""
database.py — MongoDB and ChromaDB client initialization
"""
import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── MongoDB ───────────────────────────────────────────────────────────────────

class MongoDB:
    client: AsyncIOMotorClient | None = None
    sync_client: MongoClient | None = None

    @classmethod
    async def connect(cls):
        cls.client = AsyncIOMotorClient(settings.mongo_uri)
        cls.sync_client = MongoClient(settings.mongo_uri)
        logger.info("✅ Connected to MongoDB")

    @classmethod
    async def disconnect(cls):
        if cls.client:
            cls.client.close()
        if cls.sync_client:
            cls.sync_client.close()
        logger.info("🔌 Disconnected from MongoDB")

    @classmethod
    def get_db(cls):
        return cls.client[settings.mongo_db_name]

    @classmethod
    def get_sync_db(cls):
        return cls.sync_client[settings.mongo_db_name]


def get_db():
    return MongoDB.get_db()


def get_sync_db():
    return MongoDB.get_sync_db()


# ─── ChromaDB ──────────────────────────────────────────────────────────────────

class ChromaDB:
    client = None
    embeddings: HuggingFaceEmbeddings | None = None

    @classmethod
    def initialize(cls):
        os.makedirs(settings.chroma_path, exist_ok=True)
        cls.client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        cls.embeddings = HuggingFaceEmbeddings(
            model_name=settings.embed_model,
            model_kwargs={"device": "cpu"},
        )
        logger.info(f"✅ ChromaDB initialized with local HuggingFaceEmbeddings ({settings.embed_model}) at {settings.chroma_path}")

    @classmethod
    def get_collection(cls, user_id: str, doc_id: str) -> Chroma:
        """Get (or create) a per-document Chroma vector store."""
        collection_name = f"doc_{user_id}_{doc_id}"[:63]  # Chroma limit
        return Chroma(
            client=cls.client,
            collection_name=collection_name,
            embedding_function=cls.embeddings,
        )

    @classmethod
    def delete_collection(cls, user_id: str, doc_id: str):
        """Remove all vectors for a document."""
        collection_name = f"doc_{user_id}_{doc_id}"[:63]
        try:
            cls.client.delete_collection(collection_name)
            logger.info(f"🗑️ Deleted ChromaDB collection: {collection_name}")
        except Exception as e:
            logger.warning(f"Could not delete collection {collection_name}: {e}")

    @classmethod
    def list_user_collections(cls, user_id: str) -> list[str]:
        """List all document collections for a user."""
        all_collections = cls.client.list_collections()
        prefix = f"doc_{user_id}_"
        return [c.name for c in all_collections if c.name.startswith(prefix)]
