"""
agents/ocr_table.py — OCR / Table Specialist Agent Node
Handles queries specifically about tables and image/figure content.
"""
import logging
from langchain_groq import ChatGroq

from agents.state import AgentState
from database import ChromaDB
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_llm = ChatGroq(
    model=settings.model,
    temperature=0,
)

TABLE_SYSTEM = """You are a specialist in analyzing tables and structured data from PDF documents.
When given table content in markdown format, you:
1. Identify key data points relevant to the user's question
2. Perform calculations if needed
3. Summarize findings clearly with specific numbers and values
4. Reference the page number where the table appears

Always be precise with numbers and data."""

IMAGE_SYSTEM = """You are a specialist in analyzing images, figures, charts, and diagrams from PDF documents.
When given OCR-extracted text from images, you:
1. Describe what the image/figure likely contains based on the text
2. Extract key information relevant to the user's question  
3. Note any labels, axes, or annotations visible
4. Reference the page number where the image appears"""


async def ocr_table_node(state: AgentState) -> dict:
    """Specialized processing for table and image content queries (instant filtering)."""
    query_type = state.get("query_type", "table")
    retrieved_docs = state.get("retrieved_docs", [])

    logger.info(f"🖼️ OCR/Table Agent: filtering and prioritizing {query_type} chunks")

    # Prioritize docs that match the specific content type
    typed_docs = [d for d in retrieved_docs if d.get("content_type") == query_type]
    other_docs = [d for d in retrieved_docs if d.get("content_type") != query_type]

    # Re-order so table/image chunks appear first
    ordered_docs = typed_docs + other_docs

    steps = state.get("reasoning_steps", [])
    steps.append(f"Prioritized {len(typed_docs)} specialized {query_type} content chunks")

    return {
        "retrieved_docs": ordered_docs,
        "reasoning_steps": steps,
    }
