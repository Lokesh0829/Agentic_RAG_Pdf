"""
agents/graph.py — LangGraph StateGraph definition
Wires all agent nodes together with conditional routing.
Uses MongoDB for storing conversation state (custom checkpointing via messages store).
"""
import logging
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from agents.state import AgentState
from agents.query_analyzer import query_analyzer_node
from agents.retrieval import retrieval_node
from agents.ocr_table import ocr_table_node
from agents.research import research_node, MAX_ITERATIONS
from agents.answer import answer_node
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# In-process checkpointer — conversation state is persisted in MongoDB via chat/router.py
# The message history is loaded from MongoDB and passed into each invocation
_checkpointer = MemorySaver()


# ─── Routing Functions ──────────────────────────────────────────────────────────

def route_after_retrieval(state: AgentState) -> str:
    """After retrieval, decide if we need specialized OCR/table processing."""
    query_type = state.get("query_type", "factual")
    if query_type in ("table", "image"):
        return "ocr_table"
    elif query_type in ("reasoning", "multi-step"):
        return "research"
    else:
        return "generate_answer"


def route_after_research(state: AgentState) -> str:
    """After research, decide if we need another retrieval iteration."""
    needs_more = state.get("needs_more_retrieval", False)
    iteration = state.get("iteration_count", 0)
    if needs_more and iteration < MAX_ITERATIONS:
        return "retrieval"
    return "generate_answer"


def route_after_ocr_table(state: AgentState) -> str:
    """After OCR/table analysis, go to research for complex types or directly to answer."""
    query_type = state.get("query_type", "factual")
    if query_type == "multi-step":
        return "research"
    return "generate_answer"


# ─── Graph Builder ──────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build and return the compiled LangGraph agent graph."""
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("query_analyzer", query_analyzer_node)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("ocr_table", ocr_table_node)
    builder.add_node("research", research_node)
    builder.add_node("generate_answer", answer_node)

    # Add edges
    builder.add_edge(START, "query_analyzer")
    builder.add_edge("query_analyzer", "retrieval")

    builder.add_conditional_edges(
        "retrieval",
        route_after_retrieval,
        {
            "ocr_table": "ocr_table",
            "research": "research",
            "generate_answer": "generate_answer",
        },
    )

    builder.add_conditional_edges(
        "ocr_table",
        route_after_ocr_table,
        {
            "research": "research",
            "generate_answer": "generate_answer",
        },
    )

    builder.add_conditional_edges(
        "research",
        route_after_research,
        {
            "retrieval": "retrieval",
            "generate_answer": "generate_answer",
        },
    )

    builder.add_edge("generate_answer", END)

    return builder


# Compile graph once at module level with in-memory checkpointer
_graph = None

def get_compiled_graph():
    """
    Get the compiled LangGraph graph.
    Uses MemorySaver for short-term state within a single invocation.
    Long-term memory (conversation history) is handled by loading messages from MongoDB.
    """
    global _graph
    if _graph is None:
        builder = build_graph()
        _graph = builder.compile(checkpointer=_checkpointer)
    return _graph


def get_config(thread_id: str) -> dict:
    """Return LangGraph config for a specific conversation thread."""
    return {"configurable": {"thread_id": thread_id}}
