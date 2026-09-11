"""
agents/state.py — LangGraph agent shared state
"""
from typing import Annotated, Sequence, TypedDict, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Shared state flowing through the LangGraph pipeline."""

    # Conversation messages (auto-merged by LangGraph)
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Current user question
    query: str

    # Classification of the query type
    query_type: str  # "factual" | "table" | "image" | "reasoning" | "multi-step"

    # Rewritten/enhanced query for better retrieval
    refined_query: str

    # Retrieved document chunks
    retrieved_docs: list[dict]

    # Final assembled answer
    answer: str

    # Source citations for the answer
    citations: list[dict]

    # Chain-of-thought reasoning steps
    reasoning_steps: list[str]

    # Number of research iterations (prevents infinite loops)
    iteration_count: int

    # Context IDs
    user_id: str
    doc_id: str
    conversation_id: str

    # Whether retrieval is sufficient
    needs_more_retrieval: bool
