"""
main.py — FastAPI application entry point
"""
import os
import warnings
import logging
from contextlib import asynccontextmanager

# Disable ChromaDB telemetry to prevent posthog errors
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
warnings.filterwarnings("ignore")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import get_settings
from database import MongoDB, ChromaDB
from auth.router import router as auth_router
from ingestion.router import router as ingestion_router
from chat.router import router as chat_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    logger.info("🚀 Starting Agentic RAG PDF Chatbot...")
    # Set Groq API key in environment for LangChain ChatGroq
    if settings.groq_key:
        os.environ["GROQ_API_KEY"] = settings.groq_key
    await MongoDB.connect()
    ChromaDB.initialize()

    # Create upload directory
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Create MongoDB indexes
    db = MongoDB.get_db()
    await db.users.create_index("email", unique=True)
    await db.documents.create_index([("user_id", 1), ("created_at", -1)])
    await db.conversations.create_index([("user_id", 1), ("updated_at", -1)])
    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])
    await db.semantic_cache.create_index([("user_id", 1), ("doc_id", 1)])

    logger.info("✅ All services initialized")
    yield

    # Shutdown
    logger.info("🔌 Shutting down...")
    await MongoDB.disconnect()


app = FastAPI(
    title="Agentic RAG PDF Chatbot",
    description="Multi-agent PDF Q&A system with LangGraph, ChromaDB, and MongoDB",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — supports localhost, 127.0.0.1 and any dev port
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(ingestion_router)
app.include_router(chat_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model": settings.model,
        "groq_enabled": bool(settings.groq_key),
        "embed_model": settings.embed_model,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
