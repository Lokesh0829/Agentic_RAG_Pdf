"""
ingestion/chunker.py — Semantic text chunking with metadata enrichment
"""
import logging
from typing import Any
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ingestion.parser import ParsedChunk

logger = logging.getLogger(__name__)

# Chunk sizes tuned for qwen2.5 context window
TEXT_CHUNK_SIZE = 1000
TEXT_CHUNK_OVERLAP = 150
TABLE_CHUNK_SIZE = 2000  # Tables need more context
TABLE_CHUNK_OVERLAP = 100


def chunks_to_documents(
    parsed_chunks: list[ParsedChunk],
    doc_id: str,
    user_id: str,
    filename: str,
) -> list[Document]:
    """
    Convert ParsedChunks into LangChain Documents with rich metadata.
    Tables and images are kept as single chunks; text is split further.
    """
    documents: list[Document] = []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=TEXT_CHUNK_SIZE,
        chunk_overlap=TEXT_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    table_splitter = RecursiveCharacterTextSplitter(
        chunk_size=TABLE_CHUNK_SIZE,
        chunk_overlap=TABLE_CHUNK_OVERLAP,
    )

    for chunk in parsed_chunks:
        base_metadata: dict[str, Any] = {
            "doc_id": doc_id,
            "user_id": user_id,
            "filename": filename,
            "page_num": chunk.page_num,
            "content_type": chunk.content_type,
            **chunk.metadata,
        }

        if chunk.content_type == "text":
            sub_docs = text_splitter.create_documents(
                [chunk.content],
                metadatas=[base_metadata],
            )
            documents.extend(sub_docs)

        elif chunk.content_type == "table":
            # Tables: keep together if small, split if very large
            if len(chunk.content) <= TABLE_CHUNK_SIZE:
                documents.append(Document(
                    page_content=f"[TABLE - Page {chunk.page_num}]\n{chunk.content}",
                    metadata=base_metadata,
                ))
            else:
                sub_docs = table_splitter.create_documents(
                    [chunk.content],
                    metadatas=[base_metadata],
                )
                documents.extend(sub_docs)

        elif chunk.content_type == "image":
            if chunk.content and len(chunk.content) > 10:
                documents.append(Document(
                    page_content=f"[IMAGE OCR - Page {chunk.page_num}]\n{chunk.content}",
                    metadata=base_metadata,
                ))

    logger.info(
        f"📦 Chunked {len(parsed_chunks)} raw chunks → {len(documents)} LangChain documents"
    )
    return documents
