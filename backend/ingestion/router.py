"""
ingestion/router.py — PDF upload and management endpoints
"""
import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from bson import ObjectId
import aiofiles

from config import get_settings
from database import get_db, ChromaDB
from auth.utils import get_current_user_id
from ingestion.parser import parse_document_streaming
from ingestion.chunker import chunks_to_documents
from ingestion.embedder import embed_and_store

router = APIRouter(prefix="/api/pdf", tags=["pdf"])
settings = get_settings()
logger = logging.getLogger(__name__)


async def _process_pdf_background(
    pdf_path: str,
    doc_id: str,
    user_id: str,
    filename: str,
    db_name: str,
):
    """Background task: parse → chunk → embed → update status."""
    from database import MongoDB
    db = MongoDB.get_db()

    try:
        await db.documents.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"status": "processing", "progress": 0}},
        )

        all_chunks = []
        total_pages = 0

        # Stream-parse the document page by page
        for page_num, total, page_chunks in parse_document_streaming(pdf_path, doc_id):
            all_chunks.extend(page_chunks)
            total_pages = total

            # Update progress in DB every 10 pages
            if page_num % 10 == 0 or page_num == total:
                progress_pct = int((page_num / total) * 50)  # 0–50% for parsing
                await db.documents.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": {"progress": progress_pct, "total_pages": total}},
                )

        # Convert to LangChain documents
        documents = chunks_to_documents(all_chunks, doc_id, user_id, filename)

        # Embed in batches
        def progress_cb(done: int, total: int):
            pass  # async update done after

        total_vectors = await embed_and_store(documents, user_id, doc_id, progress_cb)

        # Final status update
        await db.documents.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$set": {
                    "status": "ready",
                    "progress": 100,
                    "total_pages": total_pages,
                    "total_chunks": len(documents),
                    "total_vectors": total_vectors,
                    "indexed_at": datetime.now(timezone.utc),
                }
            },
        )
        logger.info(f"✅ PDF {doc_id} fully indexed: {total_vectors} vectors")

    except Exception as e:
        logger.error(f"❌ PDF processing failed for {doc_id}: {e}")
        await db.documents.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"status": "error", "error_message": str(e)}},
        )


@router.post("/upload")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    # Validate file type (allow PDF, Word, and Images)
    allowed_extensions = (".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg")
    if not file.filename or not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail="Only PDF, Word (.docx, .doc), and Image (.png, .jpg, .jpeg) files are accepted"
        )

    # Check file size
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_upload_size_mb}MB",
        )

    # Save to disk
    os.makedirs(settings.upload_dir, exist_ok=True)
    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}_{file.filename.replace(' ', '_')}"
    pdf_path = os.path.join(settings.upload_dir, safe_name)

    async with aiofiles.open(pdf_path, "wb") as f:
        await f.write(content)

    # Create DB record
    db = get_db()
    doc_record: dict[str, Any] = {
        "_id": ObjectId(doc_id) if len(doc_id) == 24 else ObjectId(),
        "doc_id": doc_id,
        "user_id": user_id,
        "filename": file.filename,
        "file_path": pdf_path,
        "file_size_bytes": len(content),
        "status": "queued",
        "progress": 0,
        "total_pages": 0,
        "total_chunks": 0,
        "total_vectors": 0,
        "created_at": datetime.now(timezone.utc),
    }
    # Use a proper ObjectId
    new_oid = ObjectId()
    doc_record["_id"] = new_oid
    await db.documents.insert_one(doc_record)
    mongo_doc_id = str(new_oid)

    # Kick off background processing
    background_tasks.add_task(
        _process_pdf_background,
        pdf_path=pdf_path,
        doc_id=mongo_doc_id,
        user_id=user_id,
        filename=file.filename,
        db_name=settings.mongo_db_name,
    )

    return {
        "doc_id": mongo_doc_id,
        "filename": file.filename,
        "status": "queued",
        "message": "PDF uploaded successfully. Indexing in background.",
    }


@router.get("/status/{doc_id}")
async def get_pdf_status(doc_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    doc = await db.documents.find_one({"_id": ObjectId(doc_id), "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "doc_id": doc_id,
        "filename": doc["filename"],
        "status": doc["status"],
        "progress": doc.get("progress", 0),
        "total_pages": doc.get("total_pages", 0),
        "total_chunks": doc.get("total_chunks", 0),
        "total_vectors": doc.get("total_vectors", 0),
        "error_message": doc.get("error_message"),
    }


@router.get("/list")
async def list_pdfs(user_id: str = Depends(get_current_user_id)):
    db = get_db()
    cursor = db.documents.find({"user_id": user_id}).sort("created_at", -1)
    docs = []
    async for doc in cursor:
        docs.append({
            "doc_id": str(doc["_id"]),
            "filename": doc["filename"],
            "status": doc["status"],
            "progress": doc.get("progress", 0),
            "total_pages": doc.get("total_pages", 0),
            "file_size_bytes": doc.get("file_size_bytes", 0),
            "created_at": doc["created_at"].isoformat(),
        })
    return {"documents": docs}


@router.delete("/{doc_id}")
async def delete_pdf(doc_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    doc = await db.documents.find_one({"_id": ObjectId(doc_id), "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove file
    try:
        if os.path.exists(doc["file_path"]):
            os.remove(doc["file_path"])
    except Exception as e:
        logger.warning(f"Could not delete file: {e}")

    # Remove vectors
    ChromaDB.delete_collection(user_id, doc_id)

    # Remove DB record
    await db.documents.delete_one({"_id": ObjectId(doc_id)})

    return {"message": "Document deleted successfully"}
