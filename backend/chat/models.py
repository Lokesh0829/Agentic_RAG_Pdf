"""
chat/models.py — Conversation and message schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MessageIn(BaseModel):
    content: str
    conversation_id: str
    doc_id: str  # The PDF document being chatted about


class ConversationCreate(BaseModel):
    title: str
    doc_id: Optional[str] = None


class ConversationUpdate(BaseModel):
    doc_id: str


class ConversationOut(BaseModel):
    id: str
    title: str
    doc_id: Optional[str]
    doc_filename: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int

    @classmethod
    def from_mongo(cls, doc: dict) -> "ConversationOut":
        return cls(
            id=str(doc["_id"]),
            title=doc["title"],
            doc_id=doc.get("doc_id"),
            doc_filename=doc.get("doc_filename"),
            created_at=doc["created_at"],
            updated_at=doc.get("updated_at", doc["created_at"]),
            message_count=doc.get("message_count", 0),
        )


class MessageOut(BaseModel):
    id: str
    role: str  # "user" | "assistant"
    content: str
    citations: list[dict]
    from_cache: bool
    reasoning_steps: list[str]
    created_at: datetime
