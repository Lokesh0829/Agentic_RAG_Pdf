"""
chat/router.py — Chat and Conversation management endpoints
Uses SSE streaming for real-time answer delivery.
"""
import json
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from bson import ObjectId

from database import get_db
from auth.utils import get_current_user_id
from chat.models import MessageIn, ConversationCreate, ConversationOut, MessageOut, ConversationUpdate
from agents.graph import get_compiled_graph, get_config
from agents.cache import semantic_cache
from agents.answer import answer_stream
from langchain_core.messages import HumanMessage as LCHumanMessage, AIMessage as LCAIMessage

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)


# ─── Conversation CRUD ──────────────────────────────────────────────────────────

@router.get("/conversations")
async def list_conversations(user_id: str = Depends(get_current_user_id)):
    db = get_db()
    cursor = db.conversations.find({"user_id": user_id}).sort("updated_at", -1)
    conversations = []
    async for conv in cursor:
        conversations.append(ConversationOut.from_mongo(conv).model_dump())
    return {"conversations": conversations}


@router.post("/conversations", status_code=201)
async def create_conversation(
    data: ConversationCreate,
    user_id: str = Depends(get_current_user_id),
):
    db = get_db()

    # Fetch doc filename if doc_id provided
    doc_filename = None
    if data.doc_id:
        doc = await db.documents.find_one({"_id": ObjectId(data.doc_id), "user_id": user_id})
        if doc:
            doc_filename = doc.get("filename")

    now = datetime.now(timezone.utc)
    conv_doc = {
        "user_id": user_id,
        "title": data.title,
        "doc_id": data.doc_id,
        "doc_filename": doc_filename,
        "message_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.conversations.insert_one(conv_doc)
    conv_doc["_id"] = result.inserted_id
    return ConversationOut.from_mongo(conv_doc).model_dump()


@router.put("/conversations/{conv_id}", response_model=ConversationOut)
async def update_conversation(
    conv_id: str,
    data: ConversationUpdate,
    user_id: str = Depends(get_current_user_id),
):
    db = get_db()
    # Verify document exists and belongs to user
    doc = await db.documents.find_one({"_id": ObjectId(data.doc_id), "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Update conversation
    result = await db.conversations.update_one(
        {"_id": ObjectId(conv_id), "user_id": user_id},
        {"$set": {"doc_id": data.doc_id, "doc_filename": doc["filename"], "updated_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")

    updated_conv = await db.conversations.find_one({"_id": ObjectId(conv_id)})
    return ConversationOut.from_mongo(updated_conv).model_dump()


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    conv = await db.conversations.find_one({"_id": ObjectId(conv_id), "user_id": user_id})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Delete conversation + all its messages
    await db.conversations.delete_one({"_id": ObjectId(conv_id)})
    await db.messages.delete_many({"conversation_id": conv_id})

    # Also clean up LangGraph checkpoints for this thread
    try:
        await db["checkpoints"].delete_many({"thread_id": conv_id})
        await db["checkpoint_writes"].delete_many({"thread_id": conv_id})
    except Exception as e:
        logger.warning(f"Could not delete checkpoints for {conv_id}: {e}")

    return {"message": "Conversation deleted successfully"}


@router.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    # Verify ownership
    conv = await db.conversations.find_one({"_id": ObjectId(conv_id), "user_id": user_id})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    cursor = db.messages.find({"conversation_id": conv_id}).sort("created_at", 1)
    messages = []
    async for msg in cursor:
        messages.append({
            "id": str(msg["_id"]),
            "role": msg["role"],
            "content": msg["content"],
            "citations": msg.get("citations", []),
            "from_cache": msg.get("from_cache", False),
            "reasoning_steps": msg.get("reasoning_steps", []),
            "created_at": msg["created_at"].isoformat(),
        })
    return {"messages": messages}


# ─── Chat Streaming ─────────────────────────────────────────────────────────────

@router.post("/chat/message")
async def send_message(
    data: MessageIn,
    user_id: str = Depends(get_current_user_id),
):
    """
    Send a message and get a streaming SSE response.
    Flow:
    1. Check semantic cache
    2. If cache miss → run LangGraph pipeline
    3. Stream the answer token by token
    4. Store message in MongoDB
    """
    db = get_db()
    conversation_id = data.conversation_id
    doc_id = data.doc_id
    query = data.content.strip()

    if not query:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Verify conversation belongs to user
    conv = await db.conversations.find_one({"_id": ObjectId(conversation_id), "user_id": user_id})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify document is ready
    doc = await db.documents.find_one({"_id": ObjectId(doc_id), "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.get("status") != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is still being processed (status: {doc.get('status')}). Please wait.",
        )

    # Save user message to DB
    user_msg_doc = {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": "user",
        "content": query,
        "citations": [],
        "from_cache": False,
        "reasoning_steps": [],
        "created_at": datetime.now(timezone.utc),
    }
    await db.messages.insert_one(user_msg_doc)

    async def event_stream():
        full_answer = ""
        citations = []
        reasoning_steps = []
        from_cache = False

        try:
            # 1. Check semantic cache
            cached = await semantic_cache.get_cached(query, user_id, doc_id)
            if cached:
                from_cache = True
                full_answer = cached["answer"]
                citations = cached.get("citations", [])
                reasoning_steps = ["✨ Answer retrieved from semantic cache (instant response)"]

                # Stream cached answer
                yield f"data: {json.dumps({'type': 'token', 'content': full_answer})}\n\n"

            else:
                # 2. Load conversation history from MongoDB (long-term memory)
                history_cursor = db.messages.find(
                    {"conversation_id": conversation_id}
                ).sort("created_at", 1).limit(20)
                lc_messages = []
                async for msg in history_cursor:
                    if msg["role"] == "user":
                        lc_messages.append(LCHumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        lc_messages.append(LCAIMessage(content=msg["content"]))

                # 3. Run LangGraph pipeline
                graph = get_compiled_graph()
                config = get_config(conversation_id)

                initial_state = {
                    "query": query,
                    "user_id": user_id,
                    "doc_id": doc_id,
                    "conversation_id": conversation_id,
                    "messages": lc_messages,  # Inject full history for memory
                    "retrieved_docs": [],
                    "citations": [],
                    "reasoning_steps": [],
                    "iteration_count": 0,
                    "needs_more_retrieval": False,
                    "query_type": "factual",
                    "refined_query": query,
                    "answer": "",
                }

                # Send reasoning step updates
                yield f"data: {json.dumps({'type': 'status', 'content': 'Analyzing your question...'})}\n\n"

                # Run graph up to answer node (non-streaming for agents)
                final_state = await graph.ainvoke(initial_state, config)

                reasoning_steps = final_state.get("reasoning_steps", [])
                retrieved_docs = final_state.get("retrieved_docs", [])

                yield f"data: {json.dumps({'type': 'status', 'content': 'Generating answer...'})}\n\n"

                # Stream the final answer using streaming LLM
                async for token in answer_stream(final_state):
                    full_answer += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                citations = final_state.get("citations", [])

                # Store in semantic cache
                await semantic_cache.store(query, full_answer, citations, user_id, doc_id)

        except GeneratorExit:
            # Triggered when client closes/stops connection mid-stream
            logger.info(f"🔌 Connection closed or stopped by user for {conversation_id}. Saving partial answer.")
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        finally:
            # Guarantee that whatever was generated is saved to database
            if full_answer:
                assistant_msg_doc = {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "role": "assistant",
                    "content": full_answer,
                    "citations": citations,
                    "from_cache": from_cache,
                    "reasoning_steps": reasoning_steps,
                    "created_at": datetime.now(timezone.utc),
                }
                msg_result = await db.messages.insert_one(assistant_msg_doc)

                # Update conversation metadata
                await db.conversations.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {
                        "$set": {"updated_at": datetime.now(timezone.utc)},
                        "$inc": {"message_count": 2},
                    },
                )

                try:
                    # Send completion event with metadata
                    yield f"data: {json.dumps({'type': 'done', 'message_id': str(msg_result.inserted_id), 'citations': citations, 'reasoning_steps': reasoning_steps, 'from_cache': from_cache})}\n\n"
                except GeneratorExit:
                    pass  # Client already disconnected, ignore

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
