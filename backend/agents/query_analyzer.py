"""
agents/query_analyzer.py — Query Analyzer Agent Node
Fast rule-based query classifier for optimal RAG performance.
"""
import logging
from agents.state import AgentState

logger = logging.getLogger(__name__)


async def query_analyzer_node(state: AgentState) -> dict:
    """Classify and refine the user query instantly without unnecessary LLM overhead."""
    query = state["query"]
    logger.info(f"🔍 QueryAnalyzer: analyzing '{query[:80]}...'")

    q_lower = query.lower()

    # Fast rule-based classification
    if any(w in q_lower for w in ["table", "csv", "data", "row", "column", "stat", "metric", "number"]):
        query_type = "table"
    elif any(w in q_lower for w in ["image", "chart", "diagram", "figure", "picture", "photo"]):
        query_type = "image"
    elif any(w in q_lower for w in ["why", "how", "compare", "contrast", "explain", "reason", "difference"]):
        query_type = "reasoning"
    else:
        query_type = "factual"

    refined_query = query.strip()
    logger.info(f"✅ Query classified as: {query_type} (instant)")

    return {
        "query_type": query_type,
        "refined_query": refined_query,
        "reasoning_steps": [f"Query classified as: {query_type}"],
        "iteration_count": 0,
        "needs_more_retrieval": False,
    }
